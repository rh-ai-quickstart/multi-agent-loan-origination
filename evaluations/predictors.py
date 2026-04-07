# This project was developed with assistance from AI tools.
"""Agent predictors for MLflow GenAI evaluation.

The predictor wraps the agent's async invocation in a synchronous function
compatible with mlflow.genai.evaluate()'s predict_fn interface.

Usage:
    from evaluations.predictors import get_predictor
    predict_fn = get_predictor("public-assistant")
    result = predict_fn("What loan products do you offer?")
"""

import asyncio
import logging
import sys
from collections.abc import Callable
from pathlib import Path

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

from langchain_core.messages import HumanMessage

from src.agents.registry import get_agent

logger = logging.getLogger(__name__)


def create_predict_fn(agent_name: str = "public-assistant") -> Callable[[str], str]:
    """Create a predict_fn for the public-assistant agent.

    Args:
        agent_name: The agent identifier (default: public-assistant)

    Returns:
        A synchronous predict_fn compatible with mlflow.genai.evaluate()
    """

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
                graph = get_agent(agent_name, checkpointer=None)

                initial_state = {
                    "messages": [HumanMessage(content=user_message)],
                    "user_role": "prospect",
                    "user_id": "eval-user-001",
                    "user_email": "evaluator@example.com",
                    "user_name": "Evaluation User",
                    "safety_blocked": False,
                    "tool_allowed_roles": {},
                    "decision_proposals": {},
                }

                result = await graph.ainvoke(initial_state)
                messages = result.get("messages", [])

                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, "content"):
                        return str(last_message.content)
                    return str(last_message)

                return "Error: No response from agent"

            except Exception as e:
                logger.exception("Error invoking agent %s: %s", agent_name, e)
                return f"Error: {type(e).__name__}: {str(e)}"

        with mlflow.start_span(name=f"{agent_name}-eval") as span:
            span.set_inputs({"user_message": user_message})
            result = asyncio.run(_invoke())
            span.set_outputs({"response": result})
            return result

    return predict_fn


def get_predictor(agent_name: str = "public-assistant") -> Callable[[str], str]:
    """Get a predictor function for the specified agent.

    Args:
        agent_name: The agent identifier (default: public-assistant)

    Returns:
        A predict_fn for use with mlflow.genai.evaluate()
    """
    return create_predict_fn(agent_name)
