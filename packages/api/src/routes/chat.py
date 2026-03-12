# This project was developed with assistance from AI tools.
"""WebSocket chat endpoint for public assistant (unauthenticated prospects).

Protocol:
  Client sends:  {"type": "message", "content": "user text"}
  Server sends:  {"type": "done", "content": "..."} (complete response after safety check)
                 {"type": "error", "content": "..."} (on failure)

Audit events are written with the same session_id used for LangFuse traces,
enabling trace-to-audit correlation (S-1-F18-03).
"""

import logging
import uuid

from fastapi import APIRouter, WebSocket

from ..agents.registry import get_agent
from ..services.conversation import get_conversation_service
from ._chat_handler import run_agent_stream

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/chat")
async def chat_websocket(ws: WebSocket):
    """WebSocket endpoint for public assistant chat."""
    await ws.accept()

    # Resolve checkpointer for conversation persistence
    conversation_service = get_conversation_service()
    use_checkpointer = conversation_service.is_initialized
    checkpointer = conversation_service.checkpointer if use_checkpointer else None

    try:
        graph = get_agent("public-assistant", checkpointer=checkpointer)
    except Exception:
        logger.exception("Failed to load public-assistant agent")
        await ws.send_json(
            {"type": "error", "content": "Our chat assistant is temporarily unavailable."}
        )
        await ws.close()
        return

    session_id = str(uuid.uuid4())
    user_role = "prospect"
    user_id = session_id

    # Prospects get ephemeral thread_id (never resumed); authenticated users (F3)
    # use ConversationService.get_thread_id() for deterministic persistence.
    thread_id = str(uuid.uuid4())

    # Fallback: local message list when checkpointer is unavailable
    messages_fallback: list | None = [] if not use_checkpointer else None

    await run_agent_stream(
        ws,
        graph,
        thread_id=thread_id,
        session_id=session_id,
        user_role=user_role,
        user_id=user_id,
        use_checkpointer=use_checkpointer,
        messages_fallback=messages_fallback,
    )
