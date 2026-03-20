# This project was developed with assistance from AI tools.
"""Agent-level evaluation with LLM-as-a-judge scorers.

This script evaluates the full agent behavior, not just response quality:
- Tool call correctness (did it call the right tools?)
- Tool call efficiency (minimal tool calls?)
- Response quality (is the answer correct?)

Usage:
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval

Environment variables:
    MLFLOW_TRACKING_URI: MLflow server URL
    MLFLOW_EXPERIMENT_NAME: Experiment name
    MLFLOW_TRACKING_TOKEN: Authentication token
    LLM_BASE_URL: Judge model endpoint (uses MaaS by default)
    LLM_API_KEY: API key for judge model
"""

import logging
import os
import sys
import warnings
from pathlib import Path

# Suppress warnings before other imports
warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv(override=False)

# Suppress MLflow autolog warnings
logging.getLogger("mlflow").setLevel(logging.ERROR)
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.CRITICAL)

import mlflow
from mlflow.genai.scorers import (
    Guidelines,
    RelevanceToQuery,
    Safety,
    ToolCallCorrectness,
    ToolCallEfficiency,
)

# Add packages/api to path
_api_path = Path(__file__).parent.parent / "packages" / "api"
if str(_api_path) not in sys.path:
    sys.path.insert(0, str(_api_path))

from .datasets import PUBLIC_ASSISTANT_SIMPLE_DATASET
from .predictors import get_predictor
from .scorers.custom_scorers import (
    contains_expected,
    has_numeric_result,
    response_length,
)

logger = logging.getLogger(__name__)


# Agent-specific guidelines will be created with judge model in get_agent_scorers()


def configure_judge_model() -> str:
    """Configure the LLM judge model for MLflow scorers.

    MLflow's LLM judges need OpenAI-compatible endpoints.
    We configure this via environment variables that MLflow reads.

    Returns:
        Model string in MLflow format (e.g., "openai:/model-name")
    """
    # Check for explicit judge model config
    judge_model = os.environ.get("EVAL_JUDGE_MODEL")
    if judge_model:
        return judge_model

    # Configure OpenAI client to use MaaS endpoint
    base_url = os.environ.get("LLM_BASE_URL", "https://litellm-prod.apps.maas.redhatworkshops.io/v1")
    api_key = os.environ.get("LLM_API_KEY", os.environ.get("MAAS_API_KEY", ""))
    model = os.environ.get("LLM_MODEL_CAPABLE", "qwen3-14b")

    # Set OpenAI env vars for MLflow's judge to use
    os.environ["OPENAI_API_BASE"] = base_url
    os.environ["OPENAI_BASE_URL"] = base_url
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    # MLflow format: "openai:/model-name"
    return f"openai:/{model}"


def setup_mlflow() -> None:
    """Configure MLflow tracking."""
    tracking_uri = os.environ.get(
        "MLFLOW_TRACKING_URI",
        "https://rh-ai.apps.cluster-csrmt.csrmt.sandbox1244.opentlc.com/mlflow"
    )
    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = os.environ.get(
        "MLFLOW_EXPERIMENT_NAME",
        "multi-agent-loan-origination"
    )
    if not experiment_name.endswith("-eval"):
        experiment_name = f"{experiment_name}-eval"

    try:
        mlflow.set_experiment(experiment_name)
    except Exception as e:
        print(f"Warning: Could not set experiment '{experiment_name}': {e}")
        mlflow.set_experiment("agent-evaluation")

    # Enable langchain autolog for tracing
    try:
        mlflow.langchain.autolog()
    except Exception as e:
        logger.debug(f"Autolog setup: {e}")

    print(f"MLflow configured: {tracking_uri}")
    print(f"Experiment: {experiment_name}")


def get_agent_scorers(judge_model: str | None = None) -> list:
    """Get scorers for agent-level evaluation.

    Args:
        judge_model: LLM judge model to use. If None, uses default config.

    Returns:
        List of scorers including LLM judges and custom scorers.
    """
    model = judge_model or configure_judge_model()
    print(f"Using judge model: {model}")

    # Create guidelines scorer with model
    guidelines = Guidelines(
        name="public_assistant_guidelines",
        guidelines=[
            "The response should be helpful and informative about mortgage products",
            "The response should NOT promise specific rates or pre-approval",
            "The response should use professional, clear language",
        ],
        model=model,
    )

    scorers = [
        # Custom lightweight scorers (no LLM calls)
        contains_expected,
        has_numeric_result,
        response_length,

        # LLM-as-a-judge scorers for agent behavior
        # ToolCallCorrectness with should_exact_match=True does deterministic matching
        # when expected_tools are provided in expectations
        ToolCallCorrectness(
            model=model,
            should_exact_match=True,  # Fail if expected_tools != actual tools
        ),
        ToolCallEfficiency(model=model),  # Check for minimal/efficient tool usage
        RelevanceToQuery(model=model),
        Safety(model=model),
        guidelines,
    ]

    return scorers


def run_agent_evaluation(
    agent_name: str = "public-assistant",
    dataset: list | None = None,
    judge_model: str | None = None,
) -> None:
    """Run full agent evaluation with LLM judges.

    Args:
        agent_name: Agent to evaluate
        dataset: Evaluation dataset (uses default if None)
        judge_model: LLM judge model (uses default if None)
    """
    if dataset is None:
        dataset = PUBLIC_ASSISTANT_SIMPLE_DATASET

    predict_fn = get_predictor(agent_name)
    scorers = get_agent_scorers(judge_model)

    print(f"\n{'=' * 60}")
    print(f"Agent Evaluation: {agent_name}")
    print(f"{'=' * 60}")
    print(f"Dataset: {len(dataset)} examples")
    print(f"Scorers: {len(scorers)} ({len([s for s in scorers if hasattr(s, 'model')])} LLM judges)")
    print()

    # Run evaluation
    result = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=scorers,
    )

    # Print results
    print(f"\n{'=' * 60}")
    print("EVALUATION RESULTS")
    print(f"{'=' * 60}")

    if hasattr(result, "metrics") and result.metrics:
        print("\nAggregated Metrics:")
        print("-" * 40)
        for metric, value in sorted(result.metrics.items()):
            if isinstance(value, float):
                print(f"  {metric}: {value:.2%}")
            else:
                print(f"  {metric}: {value}")

    # Print MLflow link
    tracking_uri = os.environ.get(
        "MLFLOW_TRACKING_URI",
        "https://rh-ai.apps.cluster-csrmt.csrmt.sandbox1244.opentlc.com/mlflow"
    )
    print(f"\nView results in MLflow UI:")
    print(f"  {tracking_uri}/#/experiments")
    print("\nClick on your run, then enable 'All Assessments' in the Columns dropdown")
    print("to see per-trace LLM judge scores.")

    return result


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run agent-level evaluation with LLM judges"
    )
    parser.add_argument(
        "--agent", "-a",
        type=str,
        default="public-assistant",
        help="Agent to evaluate (default: public-assistant)"
    )
    parser.add_argument(
        "--judge-model", "-j",
        type=str,
        default=None,
        help="LLM judge model (e.g., 'openai:/gpt-4.1-mini')"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Validate token
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        print("Warning: MLFLOW_TRACKING_TOKEN not set.")
        print("Run: export MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token)")

    setup_mlflow()
    run_agent_evaluation(
        agent_name=args.agent,
        judge_model=args.judge_model,
    )


if __name__ == "__main__":
    main()
