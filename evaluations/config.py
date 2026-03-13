# This project was developed with assistance from AI tools.
"""MLflow evaluation configuration.

All configuration is read from environment variables with no hardcoded defaults.
Required environment variables must be set before running evaluations.
"""

import os
from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Configuration for MLflow GenAI evaluation.

    All values are read from environment variables. No hardcoded defaults
    are provided for URLs or sensitive configuration.
    """

    mlflow_tracking_uri: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_TRACKING_URI", "")
    )
    mlflow_experiment_name: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_EXPERIMENT_NAME", "")
    )
    mlflow_workspace: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_WORKSPACE", "")
    )
    mlflow_tracking_token: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_TRACKING_TOKEN", "")
    )
    mlflow_tracking_insecure_tls: bool = field(
        default_factory=lambda: os.environ.get(
            "MLFLOW_TRACKING_INSECURE_TLS", ""
        ).lower() in ("true", "1", "yes")
    )

    # LLM judge configuration (for built-in scorers)
    judge_model: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_JUDGE_MODEL", "")
    )
    judge_endpoint: str = field(
        default_factory=lambda: os.environ.get("LLM_BASE_URL", "")
    )

    def __post_init__(self):
        """Validate required configuration."""
        missing = []
        if not self.mlflow_tracking_uri:
            missing.append("MLFLOW_TRACKING_URI")
        if not self.mlflow_experiment_name:
            missing.append("MLFLOW_EXPERIMENT_NAME")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Ensure your .env file is loaded or environment variables are set."
            )

    @property
    def eval_experiment_name(self) -> str:
        """Get experiment name with -eval suffix."""
        name = self.mlflow_experiment_name
        if not name.endswith("-eval") and not name.endswith("-evaluation"):
            return f"{name}-eval"
        return name


def get_eval_config() -> EvalConfig:
    """Get evaluation configuration from environment.

    Returns:
        EvalConfig instance populated from environment variables.

    Raises:
        ValueError: If required environment variables are not set.
    """
    return EvalConfig()
