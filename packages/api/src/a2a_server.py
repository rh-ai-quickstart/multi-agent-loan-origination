# This project was developed with assistance from AI tools.
"""A2A protocol server for Kagenti integration.

Exposes each LangGraph agent as an A2A-compatible endpoint so Kagenti
can discover, authenticate, and invoke them.  Feature-gated by the
KAGENTI_ENABLED environment variable.
"""

import asyncio
import base64
import json
import logging
import os

import uvicorn
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers.default_request_handler import LegacyRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Message,
    Part,
)
from a2a.utils.errors import InvalidParamsError, UnsupportedOperationError
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from starlette.applications import Starlette

from .agents.registry import get_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SPIRE identity (read once at startup, tagged onto MLflow traces)
# ---------------------------------------------------------------------------

_SVID_DIR = os.environ.get("SPIFFE_SVID_DIR", "/spiffe")
_JWT_SVID_PATH = os.path.join(_SVID_DIR, "jwt_svid.token")
_X509_SVID_PATH = os.path.join(_SVID_DIR, "svid.pem")


def _load_spire_identity() -> dict[str, str]:
    """Read SPIRE SVID files and extract identity claims."""
    identity: dict[str, str] = {}
    try:
        if os.path.isfile(_JWT_SVID_PATH):
            with open(_JWT_SVID_PATH) as f:
                jwt_token = f.read().strip()
            parts = jwt_token.split(".")
            if len(parts) >= 2:
                padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded))
                identity["spiffe.id"] = payload.get("sub", "")
                identity["spiffe.audience"] = str(payload.get("aud", ""))
                identity["spiffe.issuer"] = payload.get("iss", "")
                identity["spiffe.expiry"] = str(payload.get("exp", ""))
            identity["spiffe.jwt_svid"] = jwt_token[:80] + "..."
    except Exception as exc:
        logger.debug("Failed to read JWT SVID: %s", exc)
    try:
        if os.path.isfile(_X509_SVID_PATH):
            with open(_X509_SVID_PATH) as f:
                cert_pem = f.read().strip()
            identity["spiffe.x509_svid"] = cert_pem[:120] + "..."
    except Exception as exc:
        logger.debug("Failed to read X.509 SVID: %s", exc)
    return identity


_spire_identity: dict[str, str] = {}


def _get_spire_identity() -> dict[str, str]:
    """Return cached SPIRE identity, loading lazily on first call.

    The spiffe-helper sidecar may not have written SVID files by the time
    this module is imported, so we defer loading until first use.
    """
    global _spire_identity  # noqa: PLW0603
    if not _spire_identity:
        _spire_identity = _load_spire_identity()
        if _spire_identity:
            logger.info("SPIRE identity loaded: %s", _spire_identity.get("spiffe.id", "unknown"))
    return _spire_identity


def tag_trace_with_spire() -> None:
    """Tag the latest MLflow trace with SPIRE identity metadata."""
    identity = _get_spire_identity()
    logger.info("[spire] identity keys: %s", list(identity.keys()) if identity else "empty")
    try:
        from .observability import _autolog_enabled

        if not _autolog_enabled:
            logger.info("[spire] autolog not enabled, skipping trace tagging")
            return

        import mlflow

        from .core.config import settings

        client = mlflow.MlflowClient()
        experiment = client.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
        if not experiment:
            logger.info("[spire] experiment '%s' not found", settings.MLFLOW_EXPERIMENT_NAME)
            return
        traces = client.search_traces(
            experiment_ids=[experiment.experiment_id],
            max_results=1,
        )
        logger.info(
            "[spire] found %d traces in experiment %s", len(traces), experiment.experiment_id
        )
        if traces:
            request_id = traces[0].info.request_id
            if identity:
                for key, value in identity.items():
                    client.set_trace_tag(request_id, key, value)
                logger.info("[spire] tagged trace %s with SPIRE identity", request_id)
    except Exception as exc:
        logger.warning("Failed to tag trace with SPIRE identity: %s", exc)


# ---------------------------------------------------------------------------
# Agent A2A configuration: name -> (port, display_name, description, skills)
# ---------------------------------------------------------------------------

AGENT_A2A_CONFIG: dict[str, dict] = {
    "public-assistant": {
        "port": 8080,
        "default_role": "prospect",
        "display_name": "Mortgage AI - Public Assistant",
        "description": (
            "AI assistant for prospective mortgage borrowers.  Answers questions "
            "about products, rates, and provides affordability estimates."
        ),
        "skills": [
            AgentSkill(
                id="general_inquiry",
                name="General Inquiry",
                description="Answer questions about mortgage products, rates, and services",
                tags=["mortgage", "products", "rates", "FAQ"],
                examples=["What mortgage products do you offer?"],
            ),
            AgentSkill(
                id="affordability",
                name="Affordability Calculator",
                description="Estimate mortgage affordability based on income and expenses",
                tags=["affordability", "calculator", "pre-qualification"],
                examples=["Can I afford a $400k home on $85k salary?"],
            ),
        ],
    },
    "borrower-assistant": {
        "port": 8081,
        "default_role": "borrower",
        "display_name": "Mortgage AI - Borrower Assistant",
        "description": (
            "Guides authenticated borrowers through the mortgage application process, "
            "document management, and conditions clearing."
        ),
        "skills": [
            AgentSkill(
                id="application_intake",
                name="Application Intake",
                description="Guide through mortgage application and collect financial information",
                tags=["application", "intake", "financial"],
                examples=["I want to start a mortgage application"],
            ),
            AgentSkill(
                id="document_management",
                name="Document Management",
                description="Upload, track, and manage loan documents",
                tags=["documents", "upload", "tracking"],
                examples=["What documents do I need to submit?"],
            ),
            AgentSkill(
                id="conditions_clearing",
                name="Conditions Clearing",
                description="Clear underwriting conditions and provide status updates",
                tags=["conditions", "status", "underwriting"],
                examples=["What conditions are still outstanding?"],
            ),
        ],
    },
    "loan-officer-assistant": {
        "port": 8082,
        "default_role": "loan_officer",
        "display_name": "Mortgage AI - Loan Officer Assistant",
        "description": (
            "Pipeline management for loan officers: track applications, review "
            "documents, and submit packages for underwriting."
        ),
        "skills": [
            AgentSkill(
                id="pipeline_management",
                name="Pipeline Management",
                description="View and manage active loan pipeline",
                tags=["pipeline", "applications", "management"],
                examples=["Show me my active loan pipeline"],
            ),
            AgentSkill(
                id="document_review",
                name="Document Review",
                description="Review and validate borrower-submitted documents",
                tags=["documents", "review", "validation"],
                examples=["Review documents for application 12345"],
            ),
            AgentSkill(
                id="underwriting_submission",
                name="Underwriting Submission",
                description="Package and submit applications for underwriting review",
                tags=["underwriting", "submission", "packaging"],
                examples=["Submit application 12345 for underwriting"],
            ),
        ],
    },
    "underwriter-assistant": {
        "port": 8083,
        "default_role": "underwriter",
        "display_name": "Mortgage AI - Underwriter Assistant",
        "description": (
            "Risk assessment and compliance verification for mortgage underwriters.  "
            "Evaluates DTI, LTV, credit risk, and regulatory compliance."
        ),
        "skills": [
            AgentSkill(
                id="risk_assessment",
                name="Risk Assessment",
                description="Evaluate DTI, LTV, credit risk, and income stability",
                tags=["risk", "DTI", "LTV", "credit", "assessment"],
                examples=["Run risk assessment for application 12345"],
            ),
            AgentSkill(
                id="compliance_verification",
                name="Compliance Verification",
                description="HMDA, ECOA, and TRID regulatory compliance checks",
                tags=["compliance", "HMDA", "ECOA", "TRID", "regulatory"],
                examples=["Check HMDA compliance for this application"],
            ),
            AgentSkill(
                id="decision_making",
                name="Decision Making",
                description="Approve, deny, or set conditions for loan applications",
                tags=["decision", "approval", "denial", "conditions"],
                examples=["What is the recommendation for application 12345?"],
            ),
        ],
    },
    "ceo-assistant": {
        "port": 8084,
        "default_role": "ceo",
        "display_name": "Mortgage AI - CEO Dashboard Assistant",
        "description": (
            "Executive analytics and oversight: portfolio metrics, denial trends, "
            "audit trails, and AI model fairness monitoring."
        ),
        "skills": [
            AgentSkill(
                id="portfolio_analytics",
                name="Portfolio Analytics",
                description="Pipeline metrics, denial trends, and loan officer performance",
                tags=["analytics", "portfolio", "metrics", "performance"],
                examples=["Show me this month's pipeline summary"],
            ),
            AgentSkill(
                id="audit_trail",
                name="Audit Trail",
                description="Review audit events with tamper detection",
                tags=["audit", "compliance", "tamper-detection"],
                examples=["Show recent audit events for underwriting decisions"],
            ),
            AgentSkill(
                id="model_monitoring",
                name="Model Monitoring",
                description="AI model fairness metrics and performance tracking",
                tags=["model", "fairness", "SPD", "DIR", "monitoring"],
                examples=["Show fairness metrics for the approval model"],
            ),
        ],
    },
}


def _build_agent_card(agent_name: str, host: str, port: int) -> AgentCard:
    """Build an A2A AgentCard for the given agent.

    Kagenti's backend fetches the agent card from port 8080 (its default
    discovery port).  When building the card for that port we return a
    combined card with all skills so the Kagenti UI shows the full catalog.
    """
    from .core.config import settings

    config = AGENT_A2A_CONFIG[agent_name]
    service_name = settings.KAGENTI_SERVICE_NAME
    endpoint = (
        os.getenv(
            "AGENT_ENDPOINT",
            f"http://{service_name}:{port}",
        ).rstrip("/")
        + "/"
    )

    is_discovery_port = port == AGENT_A2A_CONFIG["public-assistant"]["port"]
    if is_discovery_port:
        all_skills = []
        for cfg in AGENT_A2A_CONFIG.values():
            all_skills.extend(cfg["skills"])
        return AgentCard(
            name=f"{settings.COMPANY_NAME} - Mortgage AI Agents",
            description=(
                "Multi-agent mortgage lending system with 5 specialized agents: "
                "Public Assistant, Borrower Assistant, Loan Officer, Underwriter, "
                "and CEO Dashboard."
            ),
            supported_interfaces=[
                AgentInterface(url=endpoint, protocol_binding="JSONRPC"),
            ],
            version="1.0.0",
            default_input_modes=["text", "text/plain"],
            default_output_modes=["text", "text/plain"],
            capabilities=AgentCapabilities(streaming=True),
            skills=all_skills,
        )

    return AgentCard(
        name=config["display_name"],
        description=config["description"],
        supported_interfaces=[
            AgentInterface(url=endpoint, protocol_binding="JSONRPC"),
        ],
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=config["skills"],
    )


class LoanAgentExecutor(AgentExecutor):
    """Bridges A2A requests to an existing LangGraph agent graph."""

    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name
        self._checkpointer = MemorySaver()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        if not query:
            raise InvalidParamsError()

        task_id = context.task_id
        context_id = context.context_id
        updater = TaskUpdater(event_queue, task_id, context_id)

        graph = get_agent(self._agent_name, checkpointer=self._checkpointer)
        config = {"configurable": {"thread_id": context_id}}

        try:
            state = graph.get_state(config)
            has_interrupt = bool(state.values.get("__interrupt__"))
        except Exception:
            has_interrupt = False

        default_role = AGENT_A2A_CONFIG[self._agent_name].get("default_role", "prospect")

        if has_interrupt:
            inputs = Command(resume=query)
        else:
            inputs = {
                "messages": [HumanMessage(content=query)],
                "user_role": default_role,
            }

        try:
            await updater.start_work(
                Message(
                    role="ROLE_AGENT",
                    parts=[Part(text="Processing your request...")],
                    context_id=context_id,
                    task_id=task_id,
                ),
            )

            result = await graph.ainvoke(inputs, config)

            tag_trace_with_spire()

            interrupt_values = []
            for item in result.get("__interrupt__", []) or []:
                interrupt_values.append(getattr(item, "value", item))

            if interrupt_values:
                interrupt_data = interrupt_values[0]
                if isinstance(interrupt_data, dict):
                    prompt = str(interrupt_data.get("prompt", ""))
                else:
                    prompt = str(interrupt_data)
                await updater.requires_input(
                    Message(
                        role="ROLE_AGENT",
                        parts=[Part(text=prompt or "Could you provide more information?")],
                        context_id=context_id,
                        task_id=task_id,
                    ),
                )
                return

            response_text = self._extract_response(result)
            await updater.add_artifact(
                [Part(text=response_text)],
                name="agent_response",
            )
            await updater.complete()

        except Exception as exc:
            logger.exception("Graph execution error for %s: %s", self._agent_name, exc)
            await updater.failed(
                Message(
                    role="ROLE_AGENT",
                    parts=[Part(text="An error occurred processing your request.")],
                    context_id=context_id,
                    task_id=task_id,
                ),
            )

    @staticmethod
    def _extract_response(result: dict) -> str:
        """Extract the last meaningful agent response from graph result."""
        for msg in reversed(result.get("messages", []) or []):
            if isinstance(msg, ToolMessage):
                continue
            role = getattr(msg, "type", "") or getattr(msg, "name", "")
            if role == "human":
                continue
            content = getattr(msg, "content", "") or ""
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            if not content or content.startswith("Routing to"):
                continue
            return content
        return "I wasn't able to generate a response. Please try again."

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise UnsupportedOperationError()


async def run_a2a_server(
    agent_name: str,
    host: str = "0.0.0.0",
    port: int | None = None,
) -> None:
    """Start a single A2A server for the named agent."""
    if port is None:
        port = AGENT_A2A_CONFIG[agent_name]["port"]

    agent_card = _build_agent_card(agent_name, host, port)
    executor = LoanAgentExecutor(agent_name)
    request_handler = LegacyRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = create_agent_card_routes(agent_card) + create_jsonrpc_routes(
        request_handler, rpc_url="/", enable_v0_3_compat=True
    )
    app = Starlette(routes=routes)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("A2A server for %s listening on http://%s:%d", agent_name, host, port)
    await server.serve()


async def run_all_a2a_servers(host: str = "0.0.0.0") -> None:
    """Start A2A servers for all configured agents concurrently."""
    tasks = []
    for agent_name, config in AGENT_A2A_CONFIG.items():
        tasks.append(
            asyncio.create_task(
                run_a2a_server(agent_name, host, config["port"]),
                name=f"a2a-{agent_name}",
            )
        )
    logger.info(
        "Starting %d A2A servers on ports %s",
        len(tasks),
        ", ".join(str(c["port"]) for c in AGENT_A2A_CONFIG.values()),
    )
    await asyncio.gather(*tasks)
