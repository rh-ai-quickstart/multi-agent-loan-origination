# This project was developed with assistance from AI tools.
"""MLflow GenAI evaluation framework for multi-agent loan origination system.

Usage:
    # Simple mode (fast, no LLM judge):
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode simple

    # LLM-as-a-judge mode (full evaluation):
    MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode llm-judge

Environment variables:
    MLFLOW_TRACKING_URI: MLflow server URL
    MLFLOW_EXPERIMENT_NAME: Experiment name
    MLFLOW_TRACKING_TOKEN: Authentication token
    LLM_BASE_URL: Judge model endpoint
    LLM_API_KEY: API key for judge model
"""

from .run_agent_eval import run_agent_evaluation

__all__ = [
    "run_agent_evaluation",
]
