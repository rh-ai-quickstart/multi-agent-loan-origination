#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
"""MLflow GenAI evaluation runner for multi-agent loan origination system.

This module runs agent evaluations and logs results to MLflow.

Usage:
    # From project root:
    uv run python -m evaluations.runner

    # Or evaluate a single agent:
    uv run python -m evaluations.runner --agent public-assistant

Environment variables required (from .env):
    MLFLOW_TRACKING_URI: MLflow server URL
    MLFLOW_EXPERIMENT_NAME: Experiment name
    MLFLOW_TRACKING_TOKEN: Authentication token
    MLFLOW_WORKSPACE: Workspace name (for RHOAI)
    MLFLOW_TRACKING_INSECURE_TLS: Set to 'true' for self-signed certs
"""

import argparse
import logging
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

# Suppress warnings before other imports
warnings.filterwarnings("ignore")

# Load environment before importing MLflow
# Use override=False so shell env vars (like fresh MLFLOW_TRACKING_TOKEN
# from `oc whoami --show-token`) take precedence over stale .env values
from dotenv import load_dotenv

load_dotenv(override=False)

# Suppress MLflow autolog context warnings
logging.getLogger("mlflow").setLevel(logging.ERROR)
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.CRITICAL)

import mlflow

from .config import EvalConfig, get_eval_config
from .datasets import (
    BORROWER_ASSISTANT_DATASET,
    CEO_ASSISTANT_DATASET,
    LOAN_OFFICER_ASSISTANT_DATASET,
    PUBLIC_ASSISTANT_DATASET,
    PUBLIC_ASSISTANT_SIMPLE_DATASET,
    UNDERWRITER_ASSISTANT_DATASET,
)
from .predictors import get_predictor
from .scorers.builtin_scorers import get_builtin_scorers, get_persona_guidelines_scorer
from .scorers.custom_scorers import (
    avoids_forbidden,
    contains_expected,
    has_numeric_result,
    mentions_expected_topics,
    professional_tone,
    response_length,
    response_length_appropriate,
    tool_calls_match,
)

logger = logging.getLogger(__name__)

# Agent name -> dataset mapping (full datasets)
AGENT_DATASETS = {
    "public-assistant": PUBLIC_ASSISTANT_DATASET,
    "borrower-assistant": BORROWER_ASSISTANT_DATASET,
    "loan-officer-assistant": LOAN_OFFICER_ASSISTANT_DATASET,
    "underwriter-assistant": UNDERWRITER_ASSISTANT_DATASET,
    "ceo-assistant": CEO_ASSISTANT_DATASET,
}

# Simple datasets for baseline evaluation
SIMPLE_DATASETS = {
    "public-assistant": PUBLIC_ASSISTANT_SIMPLE_DATASET,
}


def setup_mlflow(config: EvalConfig) -> None:
    """Configure MLflow tracking for evaluation.

    Follows the pattern from .tests/evaluate_agent.py that works with RHOAI.

    Args:
        config: Evaluation configuration
    """
    # Set tracking URI
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)

    # Set experiment with -eval suffix
    experiment_name = config.eval_experiment_name
    try:
        mlflow.set_experiment(experiment_name)
    except Exception as e:
        print(f"Warning: Could not set experiment '{experiment_name}': {e}")
        # Fall back to default name
        mlflow.set_experiment("agent-evaluation")

    # Enable autolog for tracing during evaluation
    try:
        mlflow.langchain.autolog()
    except Exception as e:
        logger.debug("Note: autolog setup: %s", e)

    logger.info(
        "MLflow configured: uri=%s, experiment=%s",
        config.mlflow_tracking_uri,
        experiment_name,
    )


def get_scorers(agent_name: str | None = None, simple: bool = False) -> list:
    """Get the list of scorers to use for evaluation.

    Args:
        agent_name: Optional agent name for persona-specific scorers
        simple: If True, use simplified scorers for baseline evaluation

    Returns:
        List of scorer instances (custom + built-in)
    """
    from mlflow.genai.scorers import ToolCallCorrectness, ToolCallEfficiency

    if simple:
        # Simplified scorers for baseline evaluation
        # Note: ToolCallCorrectness/ToolCallEfficiency require LLM judge config
        return [
            contains_expected,
            has_numeric_result,
            response_length,
        ]

    # Full custom scorers (lightweight, no LLM calls)
    scorers = [
        contains_expected,
        avoids_forbidden,
        mentions_expected_topics,
        response_length_appropriate,
        professional_tone,
        ToolCallCorrectness(),
        ToolCallEfficiency(),
    ]

    # Built-in LLM judge scorers (require judge model config)
    builtin = get_builtin_scorers()
    scorers.extend(builtin)

    # Persona-specific guidelines scorer
    if agent_name:
        guidelines_scorer = get_persona_guidelines_scorer(agent_name)
        if guidelines_scorer:
            scorers.append(guidelines_scorer)

    return scorers


def evaluate_agent(
    agent_name: str,
    dataset: list[dict[str, Any]] | None = None,
    scorers: list | None = None,
    simple: bool = False,
) -> Any:
    """Run evaluation for a single agent.

    Args:
        agent_name: The agent identifier (e.g., 'public-assistant')
        dataset: Optional evaluation dataset. If not provided, uses default.
        scorers: Optional list of scorers. If not provided, uses defaults.
        simple: If True, use simple dataset and scorers for baseline.

    Returns:
        MLflow evaluation result object
    """
    if dataset is None:
        if simple and agent_name in SIMPLE_DATASETS:
            dataset = SIMPLE_DATASETS[agent_name]
        else:
            dataset = AGENT_DATASETS.get(agent_name)
        if dataset is None:
            raise ValueError(f"No dataset found for agent: {agent_name}")

    if scorers is None:
        scorers = get_scorers(agent_name, simple=simple)

    predict_fn = get_predictor(agent_name)

    logger.info(
        "Starting evaluation for %s with %d examples and %d scorers (simple=%s)",
        agent_name,
        len(dataset),
        len(scorers),
        simple,
    )

    # Run MLflow evaluation
    result = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=scorers,
    )

    return result


def print_results(agent_name: str, result: Any) -> None:
    """Print evaluation results summary.

    Args:
        agent_name: The agent identifier
        result: MLflow evaluation result object
    """
    print(f"\n{'=' * 60}")
    print(f"Results for: {agent_name}")
    print("=" * 60)

    if hasattr(result, "metrics") and result.metrics:
        print("\nAggregated Metrics:")
        print("-" * 40)
        for metric, value in sorted(result.metrics.items()):
            if isinstance(value, float):
                print(f"  {metric}: {value:.2%}")
            else:
                print(f"  {metric}: {value}")

    # Print per-example results if available
    if hasattr(result, "tables") and result.tables:
        table_name = list(result.tables.keys())[0] if result.tables else None
        if table_name:
            df = result.tables[table_name]
            print(f"\nPer-Example Results ({len(df)} examples):")
            print("-" * 60)

            for i, row in df.iterrows():
                # Get request/response (MLflow GenAI uses these column names)
                request = row.get("request", {})
                response = row.get("response", "")
                state = row.get("state", "")
                expected = row.get("expected_answer/value", "")

                # Extract user message from request
                if isinstance(request, dict):
                    user_msg = request.get("user_message", str(request)[:60])
                else:
                    user_msg = str(request)[:60]

                # Extract actual response text from trace structure
                response_text = ""
                if isinstance(response, str):
                    response_text = response
                elif isinstance(response, dict):
                    # Response might be nested in messages
                    messages = response.get("messages", [])
                    if messages:
                        # Get last AI message content
                        for msg in reversed(messages):
                            if isinstance(msg, dict):
                                if msg.get("type") == "ai" and msg.get("content"):
                                    response_text = msg.get("content", "")
                                    break
                            elif hasattr(msg, "content") and hasattr(msg, "type"):
                                if msg.type == "ai" and msg.content:
                                    response_text = msg.content
                                    break

                # Truncate response for display
                response_display = (
                    response_text[:150] + "..."
                    if len(response_text) > 150
                    else response_text
                ) if response_text else "(no response)"

                print(f"\n[{i+1}] {user_msg}")
                print(f"    Expected: {expected} | State: {state}")
                print(f"    Response: {response_display}")

    print()


def run_all_evaluations(agents: list[str] | None = None) -> dict[str, Any]:
    """Run evaluations for all (or specified) agents.

    Args:
        agents: Optional list of agent names to evaluate.
                If not provided, evaluates all agents.

    Returns:
        Dict mapping agent name to evaluation result
    """
    if agents is None:
        agents = list(AGENT_DATASETS.keys())

    results = {}
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("MLflow GenAI Evaluation - Multi-Agent Loan Origination")
    print("=" * 60)
    print(f"Started: {start_time.isoformat()}")
    print(f"Agents to evaluate: {', '.join(agents)}")
    print()

    for agent_name in agents:
        print(f"\n{'=' * 60}")
        print(f"Evaluating: {agent_name}")
        print("=" * 60)

        try:
            result = evaluate_agent(agent_name)
            results[agent_name] = result
            print_results(agent_name, result)
        except Exception as e:
            logger.exception("Error evaluating %s: %s", agent_name, e)
            print(f"ERROR evaluating {agent_name}: {e}")
            results[agent_name] = {"error": str(e)}

    # Print summary
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Duration: {duration}")
    print(f"Agents evaluated: {len(results)}")

    for agent_name, result in results.items():
        if isinstance(result, dict) and "error" in result:
            print(f"  {agent_name}: FAILED - {result['error']}")
        elif hasattr(result, "metrics"):
            metrics = result.metrics
            contains = metrics.get("contains_expected/mean", "N/A")
            if isinstance(contains, float):
                print(f"  {agent_name}: contains_expected={contains:.1%}")
            else:
                print(f"  {agent_name}: completed")
        else:
            print(f"  {agent_name}: completed")

    # Print MLflow UI link
    config = get_eval_config()
    print(f"\nView results in MLflow UI:")
    print(f"  {config.mlflow_tracking_uri}/#/experiments")
    print(f"  Look for experiment: '{config.eval_experiment_name}'")
    print("  The evaluation results will appear in the 'Evaluation' tab.")

    print()
    return results


def main():
    """CLI entry point for evaluation runner."""
    parser = argparse.ArgumentParser(
        description="Run MLflow GenAI evaluation for mortgage agents"
    )
    parser.add_argument(
        "--agent",
        "-a",
        type=str,
        choices=list(AGENT_DATASETS.keys()),
        help="Evaluate a specific agent (default: all agents)",
    )
    parser.add_argument(
        "--simple",
        "-s",
        action="store_true",
        help="Use simplified dataset and scorers for baseline evaluation",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Validate configuration (will raise if missing required env vars)
    try:
        config = get_eval_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nEnsure you have set the required environment variables:")
        print("  - MLFLOW_TRACKING_URI")
        print("  - MLFLOW_EXPERIMENT_NAME")
        print("  - MLFLOW_TRACKING_TOKEN")
        print("\nYou can set these in your .env file or export them directly.")
        sys.exit(1)

    # Setup MLflow
    setup_mlflow(config)

    # Run evaluation
    if args.agent:
        result = evaluate_agent(args.agent, simple=args.simple)
        print_results(args.agent, result)

        # Print MLflow link
        print(f"\nView results in MLflow UI:")
        print(f"  {config.mlflow_tracking_uri}/#/experiments")
    else:
        if args.simple:
            # Only run simple evaluation for public-assistant
            result = evaluate_agent("public-assistant", simple=True)
            print_results("public-assistant", result)
            print(f"\nView results in MLflow UI:")
            print(f"  {config.mlflow_tracking_uri}/#/experiments")
        else:
            run_all_evaluations()


if __name__ == "__main__":
    main()
