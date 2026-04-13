# This project was developed with assistance from AI tools.
"""Shared WebSocket chat helpers used by public and borrower chat endpoints.

Extracts the streaming loop and WebSocket authentication so both chat.py and
borrower_chat.py share identical event handling + audit writing logic.
"""

import asyncio
import json
import logging
import re
import uuid

import jwt as pyjwt
from db.enums import UserRole
from fastapi import APIRouter, Depends, Query, WebSocket
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from ..agents.registry import get_agent
from ..core.auth import build_data_scope
from ..core.config import settings
from ..core.metrics import active_chat_sessions, chat_messages_total
from ..middleware.auth import CurrentUser, _decode_token, _resolve_role, require_roles
from ..middleware.pii import _mask_pii_recursive
from ..observability import set_trace_context
from ..schemas.auth import UserContext
from ..schemas.conversation import ConversationHistoryResponse
from ..services.audit import write_audit_event
from ..services.conversation import ConversationService, get_conversation_service

logger = logging.getLogger(__name__)


async def authenticate_websocket(
    ws: WebSocket,
    required_role: UserRole | None = None,
) -> UserContext | None:
    """Validate JWT from ``?token=<jwt>`` query param on an already-accepted WebSocket.

    When ``AUTH_DISABLED=true``: returns a dev user whose role matches *required_role*
    (or ADMIN if no role is required).

    Returns ``None`` (and closes the WS) when authentication or authorization fails.
    """
    if settings.AUTH_DISABLED:
        role = required_role or UserRole.ADMIN
        user_id = ws.query_params.get("dev_user_id", "dev-user")
        return UserContext(
            user_id=user_id,
            role=role,
            email=ws.query_params.get("dev_email", "dev@example.com"),
            name=ws.query_params.get("dev_name", "Dev User"),
            data_scope=build_data_scope(role, user_id),
        )

    token = ws.query_params.get("token")

    if not token:
        if required_role is not None:
            await ws.close(code=4001, reason="Missing authentication token")
            return None
        # Unauthenticated endpoints (public chat) -- return None to let caller decide
        return None

    try:
        payload = await _decode_token(token)
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError) as exc:
        logger.warning("WebSocket auth failed: %s", exc)
        await ws.close(code=4001, reason="Invalid or expired token")
        return None

    try:
        role = _resolve_role(payload)
    except ValueError:
        await ws.close(code=4003, reason="No recognized role assigned")
        return None

    if required_role is not None and role != required_role:
        logger.warning(
            "WebSocket RBAC denied: user=%s role=%s required=%s",
            payload.sub,
            role.value,
            required_role.value,
        )
        await ws.close(code=4003, reason="Insufficient permissions")
        return None

    data_scope = build_data_scope(role, payload.sub)
    return UserContext(
        user_id=payload.sub,
        role=role,
        email=payload.email,
        name=payload.name or payload.preferred_username,
        data_scope=data_scope,
    )


async def run_agent_stream(
    ws: WebSocket,
    graph,
    *,
    thread_id: str,
    session_id: str,
    user_role: str,
    user_id: str,
    user_email: str = "",
    user_name: str = "",
    use_checkpointer: bool,
    messages_fallback: list | None,
    pii_mask: bool = False,
    system_context: str = "",
) -> None:
    """Run the agent streaming loop over an accepted WebSocket.

    Handles message receive, event streaming, and audit writing.
    Both public chat and borrower chat call this.

    Args:
        ws: The accepted WebSocket connection.
        graph: A compiled LangGraph graph.
        thread_id: The checkpoint thread ID.
        session_id: Session ID for audit + LangFuse correlation.
        user_role: Role string for the agent state.
        user_id: User ID string for the agent state.
        use_checkpointer: Whether checkpoint persistence is active.
        messages_fallback: Mutable list for local message tracking when
            checkpointer is unavailable. Pass ``None`` when using checkpointer.
        system_context: Optional context string injected as a system message
            before the first user message (e.g. application IDs).
    """
    from db.database import SessionLocal

    # Track active session for metrics
    persona = user_role or "public"
    active_chat_sessions.labels(persona=persona).inc()

    async def _send(msg: dict) -> None:
        """Send a JSON message over WebSocket, applying PII masking if needed."""
        if pii_mask:
            msg = _mask_pii_recursive(msg)
        await ws.send_json(msg)

    async def _audit(event_type: str, event_data: dict | None = None) -> None:
        try:
            async with SessionLocal() as db_session:
                await write_audit_event(
                    db_session,
                    event_type=event_type,
                    session_id=session_id,
                    user_id=user_id,
                    user_role=user_role,
                    event_data=event_data,
                )
                await db_session.commit()
        except Exception:
            logger.warning("Failed to write audit event %s", event_type, exc_info=True)

    # Track the current agent task so we can cancel it on WS disconnect
    agent_task: asyncio.Task | None = None

    async def _run_agent(user_text: str, input_messages: list) -> str:
        """Run the agent graph, buffering until the output shield completes.

        No messages are sent to the client from here -- the caller handles
        cleanup and sends a single ``done`` message with the final content.

        Returns the raw response text (caller applies cleanup).
        """
        # Set MLFlow trace context for correlation (autolog handles callbacks)
        set_trace_context(session_id=session_id, user_id=user_id)
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,
        }

        full_response = ""
        safety_blocked = False
        safety_override_content = ""
        async for event in graph.astream_events(
            {
                "messages": input_messages,
                "user_role": user_role,
                "user_id": user_id,
                "user_email": user_email,
                "user_name": user_name,
            },
            config=config,
            version="v2",
        ):
            kind = event.get("event")
            node = event.get("metadata", {}).get("langgraph_node")

            if kind == "on_chat_model_stream" and node in (
                "agent",
                "agent_fast",
                "agent_capable",
            ):
                chunk = event.get("data", {}).get("chunk")
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    full_response += chunk.content

            elif kind == "on_chain_end" and node == "input_shield":
                output = event.get("data", {}).get("output")
                if isinstance(output, dict) and output.get("safety_blocked"):
                    for msg in output.get("messages", []):
                        if hasattr(msg, "content") and msg.content:
                            full_response = msg.content
                    await _audit("safety_block", {"shield": "input", "blocked": True})

            elif kind == "on_chain_end" and node == "tool_auth":
                output = event.get("data", {}).get("output")
                if isinstance(output, dict):
                    auth_msgs = output.get("messages", [])
                    if auth_msgs:
                        logger.info("Tool auth denied for session %s", session_id)
                        await _audit(
                            "tool_auth_denied",
                            {
                                "message": auth_msgs[-1].content
                                if hasattr(auth_msgs[-1], "content")
                                else str(auth_msgs[-1]),
                            },
                        )

            elif kind == "on_tool_end":
                tool_output = event.get("data", {}).get("output")
                tool_name = event.get("name", "unknown")
                await _audit(
                    "agent_tool_called",
                    {
                        "tool_name": tool_name,
                        "result_length": len(str(tool_output)) if tool_output else 0,
                    },
                )

            elif kind == "on_chain_end" and node == "output_shield":
                output = event.get("data", {}).get("output")
                if isinstance(output, dict):
                    shield_msgs = output.get("messages", [])
                    if shield_msgs:
                        safety_blocked = True
                        safety_override_content = shield_msgs[-1].content
                        await _audit(
                            "safety_block",
                            {"shield": "output", "blocked": True},
                        )

        if safety_blocked:
            full_response = safety_override_content

        return full_response

    async def _wait_disconnect() -> None:
        """Block until the WebSocket client disconnects.

        Consumes incoming messages while the agent is streaming so the
        disconnect exception surfaces promptly.  Any messages received
        during agent execution are silently dropped (the protocol only
        supports one exchange at a time).
        """
        from fastapi import WebSocketDisconnect

        try:
            while True:
                await ws.receive_text()
        except (WebSocketDisconnect, RuntimeError):
            return

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send({"type": "error", "content": "Invalid JSON"})
                continue

            if data.get("type") != "message" or not data.get("content"):
                await _send({"type": "error", "content": "Expected {type: message, content: ...}"})
                continue

            user_text = data["content"]

            # Record inbound message metric
            chat_messages_total.labels(persona=persona, direction="inbound").inc()

            # Inject system context once on the first message of the conversation
            context_msgs: list = []
            if system_context:
                context_msgs = [SystemMessage(content=system_context)]
                system_context = ""  # Only inject once

            if use_checkpointer:
                input_messages = context_msgs + [HumanMessage(content=user_text)]
            else:
                messages_fallback.extend(context_msgs)
                messages_fallback.append(HumanMessage(content=user_text))
                input_messages = messages_fallback

            # Race the agent against a disconnect sentinel.
            # If the client disconnects while the agent is streaming,
            # the agent task is cancelled immediately -- freeing the LLM slot.
            agent_task = asyncio.create_task(_run_agent(user_text, input_messages))
            disconnect_task = asyncio.create_task(_wait_disconnect())

            done, pending = await asyncio.wait(
                {agent_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if disconnect_task in done:
                # Client disconnected while agent was running -- cancel agent
                agent_task.cancel()
                try:
                    await agent_task
                except (asyncio.CancelledError, Exception):
                    pass
                logger.debug(
                    "Agent cancelled for session %s (client disconnected mid-stream)",
                    session_id,
                )
                return

            # Agent finished -- cancel the disconnect watcher
            disconnect_task.cancel()
            try:
                await disconnect_task
            except (asyncio.CancelledError, Exception):
                pass

            try:
                full_response = agent_task.result()
            except Exception:
                logger.exception("Agent invocation failed")
                await _send(
                    {
                        "type": "error",
                        "content": "Our chat assistant is temporarily unavailable. "
                        "Please try again later.",
                    }
                )
                continue

            # Strip think tags, markdown bold markers, and stray tool-call
            # text that small models (e.g. Llama) sometimes emit inline
            # instead of using the structured tool-calling format.
            full_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL)
            full_response = full_response.replace("**", "")
            full_response = re.sub(r"\[[^\]]*\w+\(.*?\)[^\]]*\]", "", full_response)
            full_response = full_response.strip()

            # Without checkpointer, manually track history for this session
            if not use_checkpointer and full_response:
                messages_fallback.append(AIMessage(content=full_response))

            await _send({"type": "done", "content": full_response})

            # Record outbound message metric
            chat_messages_total.labels(persona=persona, direction="outbound").inc()

    except Exception as exc:
        from fastapi import WebSocketDisconnect

        if isinstance(exc, WebSocketDisconnect):
            logger.debug("Client disconnected from chat")
        else:
            logger.error("Unexpected error in chat handler", exc_info=True)
            raise
    finally:
        # Decrement active session counter
        active_chat_sessions.labels(persona=persona).dec()


async def _build_application_context(user: UserContext) -> str:
    """Look up the user's applications and return a context string for the agent."""
    from db.database import SessionLocal

    from ..services.application import list_applications

    try:
        async with SessionLocal() as session:
            apps, total = await list_applications(session, user, limit=5)
    except Exception:
        logger.warning("Failed to load application context for %s", user.user_id)
        return ""

    if not apps:
        return ""

    # Only borrowers need dynamic app-ID injection; LOs/UWs/CEOs specify IDs themselves
    if user.role != UserRole.BORROWER:
        return ""

    primary = apps[0]
    stage = primary.stage.value.replace("_", " ").title()
    loan = f"${primary.loan_amount:,.0f}" if primary.loan_amount else "amount not set"
    addr = primary.property_address or "no address"

    return (
        f"[System context] The user's primary application is #{primary.id} "
        f"({stage}, {loan}, {addr}). "
        f"Use application_id={primary.id} for all tool calls. "
        "Do NOT ask the user for their application ID."
    )


def create_authenticated_chat_router(
    role: UserRole,
    agent_name: str,
    ws_path: str,
    history_path: str,
) -> APIRouter:
    """Create a chat router with WebSocket endpoint and history GET.

    Factory function to eliminate code duplication across borrower, loan officer,
    and underwriter chat endpoints.

    Args:
        role: Required role for authentication.
        agent_name: Agent name for registry lookup.
        ws_path: WebSocket path (e.g., "/borrower/chat").
        history_path: History endpoint path (e.g., "/borrower/conversations/history").

    Returns:
        Configured APIRouter with WebSocket and history endpoints.
    """
    router = APIRouter()

    @router.websocket(ws_path)
    async def chat_websocket(ws: WebSocket):
        """Authenticated WebSocket endpoint for agent chat."""
        await ws.accept()

        user = await authenticate_websocket(ws, required_role=role)
        if user is None:
            return  # WS closed by authenticate_websocket

        # Resolve checkpointer for conversation persistence
        service = get_conversation_service()
        use_checkpointer = service.is_initialized
        checkpointer = service.checkpointer if use_checkpointer else None

        try:
            graph = get_agent(agent_name, checkpointer=checkpointer)
        except Exception:
            logger.exception("Failed to load %s agent", agent_name)
            await ws.send_json(
                {"type": "error", "content": "Our chat assistant is temporarily unavailable."}
            )
            await ws.close()
            return

        # Per-app threads for roles that manage multiple applications
        app_id_param = ws.query_params.get("app_id")
        app_id: int | None = None
        if app_id_param:
            try:
                app_id = int(app_id_param)
            except (ValueError, OverflowError):
                await ws.send_json({"type": "error", "content": "Invalid app_id parameter."})
                await ws.close(code=4000)
                return
        thread_id = ConversationService.get_thread_id(user.user_id, agent_name, app_id)
        ConversationService.verify_thread_ownership(thread_id, user.user_id)
        session_id = str(uuid.uuid4())

        # Always use checkpointer when available; fallback to local list
        messages_fallback: list | None = [] if not use_checkpointer else None

        # Build application context for authenticated agents
        system_context = await _build_application_context(user)

        await run_agent_stream(
            ws,
            graph,
            thread_id=thread_id,
            session_id=session_id,
            user_role=user.role.value,
            user_id=user.user_id,
            user_email=user.email or "",
            user_name=user.name or "",
            use_checkpointer=use_checkpointer,
            messages_fallback=messages_fallback,
            pii_mask=getattr(user.data_scope, "pii_mask", False),
            system_context=system_context,
        )

    @router.get(
        history_path,
        response_model=ConversationHistoryResponse,
        dependencies=[Depends(require_roles(role, UserRole.ADMIN))],
    )
    async def get_conversation_history_endpoint(
        user: CurrentUser,
        app_id: int | None = Query(default=None),
    ) -> ConversationHistoryResponse:
        """Return prior conversation messages for the authenticated user.

        Used by the frontend to render chat history when the chat window opens.
        Pass app_id for per-application conversation threads (LO/UW).
        """
        service = get_conversation_service()
        thread_id = ConversationService.get_thread_id(user.user_id, agent_name, app_id)
        ConversationService.verify_thread_ownership(thread_id, user.user_id)
        messages = await service.get_conversation_history(thread_id)
        return ConversationHistoryResponse(data=messages)

    @router.delete(
        history_path,
        status_code=204,
        dependencies=[Depends(require_roles(role, UserRole.ADMIN))],
    )
    async def clear_conversation_history_endpoint(
        user: CurrentUser,
        app_id: int | None = Query(default=None),
    ) -> None:
        """Clear conversation history for the authenticated user.

        Deletes checkpoint data so the next session starts fresh.
        Pass app_id for per-application conversation threads (LO/UW).
        """
        service = get_conversation_service()
        thread_id = ConversationService.get_thread_id(user.user_id, agent_name, app_id)
        ConversationService.verify_thread_ownership(thread_id, user.user_id)
        await service.clear_conversation(thread_id)

    return router
