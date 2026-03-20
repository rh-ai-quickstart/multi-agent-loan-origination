# This project was developed with assistance from AI tools.
"""Agent predictors for MLflow GenAI evaluation.

Each predictor wraps an agent's async invocation in a synchronous function
compatible with mlflow.genai.evaluate()'s predict_fn interface.

The predict_fn signature expected by MLflow:
    def predict_fn(user_message: str) -> str

Where user_message is the input from the dataset.

The predictors use mock database responses for evaluation, allowing agents
to be evaluated on behavior without requiring a running database. The public
assistant (prospect persona) doesn't need database access and runs without mocks.

Tool Call Tracking:
    The predictor tracks which tools were called during agent execution.
    Tool names are stored in a thread-local variable `_last_tool_calls`
    which can be accessed by scorers to validate tool usage.
"""

import asyncio
import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import mlflow

# Allow nested event loops for MLflow compatibility
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# Add packages/api to path for imports
_api_path = Path(__file__).parent.parent / "packages" / "api"
if str(_api_path) not in sys.path:
    sys.path.insert(0, str(_api_path))

from langchain_core.messages import HumanMessage, ToolMessage

from src.agents.registry import get_agent

from .mock_db import mock_application, mock_documents, mock_conditions

logger = logging.getLogger(__name__)

# Thread-local storage for tool call tracking
_tool_call_storage = threading.local()


def get_last_tool_calls() -> list[str]:
    """Get the list of tool names called in the last prediction.

    Returns:
        List of tool names that were called, or empty list if none.
    """
    return getattr(_tool_call_storage, "tool_calls", [])


def _extract_tool_calls(messages: list[Any]) -> list[str]:
    """Extract tool names from message history.

    Args:
        messages: List of LangChain messages from agent execution.

    Returns:
        List of unique tool names that were called.
    """
    tool_names = []
    for msg in messages:
        # Check for AIMessage with tool_calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if isinstance(tc, dict) and "name" in tc:
                    tool_names.append(tc["name"])
                elif hasattr(tc, "name"):
                    tool_names.append(tc.name)
        # Also check ToolMessage for the tool name
        if isinstance(msg, ToolMessage) and hasattr(msg, "name"):
            if msg.name and msg.name not in tool_names:
                tool_names.append(msg.name)
    return tool_names

# Role mapping for each agent persona
AGENT_ROLES = {
    "public-assistant": "prospect",
    "borrower-assistant": "borrower",
    "loan-officer-assistant": "loan_officer",
    "underwriter-assistant": "underwriter",
    "ceo-assistant": "ceo",
}


def _create_mock_session():
    """Create a mock database session for evaluation."""
    session = AsyncMock()
    mock_result = MagicMock()

    # Set up return values for common query patterns
    mock_result.scalar.return_value = 1
    mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_application()]
    mock_result.unique.return_value.scalar_one_or_none.return_value = mock_application()

    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    # Return an async context manager
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def create_predict_fn(agent_name: str) -> Callable[[str], str]:
    """Factory to create a predict_fn for a specific agent.

    Args:
        agent_name: The agent identifier (e.g., 'public-assistant')

    Returns:
        A synchronous predict_fn compatible with mlflow.genai.evaluate()

    Note:
        For authenticated personas (borrower, loan officer, underwriter, CEO),
        this patches SessionLocal to return mock data so evaluation can run
        without a database. The public-assistant doesn't need database access.

        Uses mlflow.trace() context manager to ensure traces are captured
        when using asyncio.run() with async agents.
    """
    user_role = AGENT_ROLES.get(agent_name, "prospect")
    needs_db_mock = agent_name != "public-assistant"

    def predict_fn(user_message: str) -> str:
        """Synchronous wrapper for async agent invocation with MLflow tracing.

        Args:
            user_message: The user's message text

        Returns:
            The agent's response text
        """
        if not user_message:
            return "Error: No user_message provided"

        async def _invoke() -> str:
            try:
                # Get agent graph (no checkpointer for eval - stateless)
                graph = get_agent(agent_name, checkpointer=None)

                # Build initial state
                initial_state = {
                    "messages": [HumanMessage(content=user_message)],
                    "user_role": user_role,
                    "user_id": "eval-user-001",
                    "user_email": "evaluator@example.com",
                    "user_name": "Evaluation User",
                    "model_tier": "fast_small",
                    "safety_blocked": False,
                    "escalated": False,
                    "tool_allowed_roles": {},
                    "decision_proposals": {},
                }

                # Use async invoke
                result = await graph.ainvoke(initial_state)

                # Extract the final AI message and tool calls
                messages = result.get("messages", [])

                # Track tool calls for scoring
                tool_calls = _extract_tool_calls(messages)
                _tool_call_storage.tool_calls = tool_calls

                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        return str(last_message.content)
                    return str(last_message)

                return "Error: No response from agent"

            except Exception as e:
                logger.exception("Error invoking agent %s: %s", agent_name, e)
                return f"Error: {type(e).__name__}: {str(e)}"

        # Wrap execution in MLflow trace context for proper trace capture
        with mlflow.start_span(name=f"{agent_name}-eval") as span:
            span.set_inputs({"user_message": user_message})
            if needs_db_mock:
                with patch("db.database.SessionLocal", side_effect=_create_mock_session):
                    result = asyncio.run(_invoke())
            else:
                result = asyncio.run(_invoke())
            span.set_outputs({"response": result})
            return result

    return predict_fn


# Pre-built predictors for all agents
PREDICTORS: dict[str, Callable[[str], str]] = {
    "public-assistant": create_predict_fn("public-assistant"),
    "borrower-assistant": create_predict_fn("borrower-assistant"),
    "loan-officer-assistant": create_predict_fn("loan-officer-assistant"),
    "underwriter-assistant": create_predict_fn("underwriter-assistant"),
    "ceo-assistant": create_predict_fn("ceo-assistant"),
}


def get_predictor(agent_name: str) -> Callable[[str], str]:
    """Get a predictor function for the specified agent.

    Args:
        agent_name: The agent identifier

    Returns:
        A predict_fn for use with mlflow.genai.evaluate()

    Raises:
        KeyError: If agent_name is not recognized
    """
    if agent_name not in PREDICTORS:
        raise KeyError(
            f"Unknown agent: {agent_name}. "
            f"Available: {list(PREDICTORS.keys())}"
        )
    return PREDICTORS[agent_name]
