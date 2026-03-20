# This project was developed with assistance from AI tools.
"""Agent-level evaluation with configurable scorers.

This script evaluates the full agent behavior with two modes:
- simple: Lightweight deterministic checks (no LLM calls, fast)
- llm-judge: Full LLM-as-a-judge evaluation (slower, more thorough)

Usage:
    # Simple mode (fast, no LLM judge calls):
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode simple

    # LLM-as-a-judge mode (full evaluation):
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode llm-judge

    # Default is llm-judge mode:
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval

Environment variables (all read from .env):
    MLFLOW_TRACKING_URI: MLflow server URL (required)
    MLFLOW_EXPERIMENT_NAME: Experiment name (required)
    MLFLOW_TRACKING_TOKEN: Authentication token (required)
    LLM_BASE_URL: LLM endpoint URL (required for llm-judge mode)
    LLM_API_KEY: API key for LLM endpoint
    LLM_MODEL_CAPABLE: Model to use for judge (required for llm-judge mode)
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


def configure_judge_model() -> str:
    """Configure the LLM judge model for MLflow scorers.

    MLflow's LLM judges need OpenAI-compatible endpoints.
    All values are read from environment variables.

    Returns:
        Model string in MLflow format (e.g., "openai:/model-name")

    Raises:
        ValueError: If required environment variables are not set.
    """
    # Check for explicit judge model config
    judge_model = os.environ.get("EVAL_JUDGE_MODEL")
    if judge_model:
        return judge_model

    # Read from environment
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY", os.environ.get("MAAS_API_KEY", ""))
    model = os.environ.get("LLM_MODEL_CAPABLE")

    if not base_url:
        raise ValueError(
            "LLM_BASE_URL is required for llm-judge mode. "
            "Set it in your .env file or use --mode simple."
        )
    if not model:
        raise ValueError(
            "LLM_MODEL_CAPABLE is required for llm-judge mode. "
            "Set it in your .env file or use --mode simple."
        )

    # Set OpenAI env vars for MLflow's judge to use
    os.environ["OPENAI_API_BASE"] = base_url
    os.environ["OPENAI_BASE_URL"] = base_url
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    # MLflow format: "openai:/model-name"
    return f"openai:/{model}"


def setup_mlflow() -> None:
    """Configure MLflow tracking.

    Raises:
        ValueError: If required environment variables are not set.
    """
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        raise ValueError(
            "MLFLOW_TRACKING_URI is required. Set it in your .env file."
        )

    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME")
    if not experiment_name:
        raise ValueError(
            "MLFLOW_EXPERIMENT_NAME is required. Set it in your .env file."
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


def get_simple_scorers() -> list:
    """Get lightweight scorers for simple evaluation (no LLM calls).

    Returns:
        List of deterministic scorers that run fast without LLM calls.
    """
    print("Using simple scorers (no LLM judge)")
    return [
        contains_expected,
        has_numeric_result,
        response_length,
    ]


def get_llm_judge_scorers(judge_model: str | None = None) -> list:
    """Get full LLM-as-a-judge scorers for agent-level evaluation.

    Args:
        judge_model: LLM judge model to use. If None, uses default config.

    Returns:
        List of scorers including LLM judges and custom scorers.
    """
    model = judge_model or configure_judge_model()
    print(f"Using LLM judge model: {model}")

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
        ToolCallCorrectness(
            model=model,
            should_exact_match=True,
        ),
        ToolCallEfficiency(model=model),
        RelevanceToQuery(model=model),
        Safety(model=model),
        guidelines,
    ]

    return scorers


def get_agent_scorers(mode: str = "llm-judge", judge_model: str | None = None) -> list:
    """Get scorers based on evaluation mode.

    Args:
        mode: Evaluation mode - "simple" or "llm-judge"
        judge_model: LLM judge model (only used in llm-judge mode)

    Returns:
        List of scorers for the specified mode.
    """
    if mode == "simple":
        return get_simple_scorers()
    else:
        return get_llm_judge_scorers(judge_model)


def run_agent_evaluation(
    agent_name: str = "public-assistant",
    dataset: list | None = None,
    mode: str = "llm-judge",
    judge_model: str | None = None,
) -> None:
    """Run agent evaluation with configurable mode.

    Args:
        agent_name: Agent to evaluate
        dataset: Evaluation dataset (uses default if None)
        mode: Evaluation mode - "simple" or "llm-judge"
        judge_model: LLM judge model (only used in llm-judge mode)
    """
    if dataset is None:
        dataset = PUBLIC_ASSISTANT_SIMPLE_DATASET

    predict_fn = get_predictor(agent_name)
    scorers = get_agent_scorers(mode=mode, judge_model=judge_model)

    llm_judge_count = len([s for s in scorers if hasattr(s, 'model')])
    mode_label = "Simple (no LLM)" if mode == "simple" else "LLM-as-a-Judge"

    print(f"\n{'=' * 60}")
    print(f"Agent Evaluation: {agent_name}")
    print(f"Mode: {mode_label}")
    print(f"{'=' * 60}")
    print(f"Dataset: {len(dataset)} examples")
    print(f"Scorers: {len(scorers)} ({llm_judge_count} LLM judges)")
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
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
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
        "--mode", "-m",
        type=str,
        choices=["simple", "llm-judge"],
        default="llm-judge",
        help="Evaluation mode: 'simple' (fast, no LLM) or 'llm-judge' (full evaluation)"
    )
    parser.add_argument(
        "--judge-model", "-j",
        type=str,
        default=None,
        help="LLM judge model (e.g., 'openai:/gpt-4.1-mini') - only used with llm-judge mode"
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

    try:
        setup_mlflow()
        run_agent_evaluation(
            agent_name=args.agent,
            mode=args.mode,
            judge_model=args.judge_model,
        )
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("\nMake sure your .env file contains:")
        print("  MLFLOW_TRACKING_URI=<your-mlflow-server>")
        print("  MLFLOW_EXPERIMENT_NAME=<experiment-name>")
        if args.mode == "llm-judge":
            print("  LLM_BASE_URL=<llm-endpoint>")
            print("  LLM_MODEL_CAPABLE=<model-name>")
        sys.exit(1)


if __name__ == "__main__":
    main()
