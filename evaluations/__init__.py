# This project was developed with assistance from AI tools.
"""MLflow GenAI evaluation framework for multi-agent loan origination system.

This module provides evaluation capabilities using MLflow's GenAI framework:
- Evaluation datasets with ground truth for 5 agent personas
- Custom domain-specific scorers for mortgage workflows
- Integration with MLflow's built-in LLM judges

Usage:
    # From project root:
    uv run python -m evaluations.runner

    # Or evaluate a single agent:
    uv run python -m evaluations.runner --agent public-assistant

Environment variables required:
    MLFLOW_TRACKING_URI: MLflow server URL
    MLFLOW_EXPERIMENT_NAME: Experiment name
    MLFLOW_TRACKING_TOKEN: Authentication token
    MLFLOW_WORKSPACE: Workspace name (for RHOAI)
"""

from .config import EvalConfig, get_eval_config
from .runner import evaluate_agent, run_all_evaluations

__all__ = [
    "EvalConfig",
    "get_eval_config",
    "run_all_evaluations",
    "evaluate_agent",
]
