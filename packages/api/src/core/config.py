# This project was developed with assistance from AI tools.
"""
Application configuration.

All settings read from environment variables with sensible local dev defaults.
Group related settings together; each group becomes a section future PRs extend.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root .env regardless of CWD (matches inference/config.py approach)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings -- single source of truth for env-driven config."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- App --
    APP_NAME: str = "mortgage-ai"
    COMPANY_NAME: str = "Acme FinTech Company"
    AGENT_NAME: str = ""
    DEBUG: bool = False

    # -- Kagenti / A2A --
    KAGENTI_ENABLED: bool = Field(
        default=False,
        description="Enable A2A protocol servers for Kagenti agent discovery.",
    )
    KAGENTI_SERVICE_NAME: str = Field(
        default="mortgage-ai-api",
        description="Kubernetes Service name used in A2A agent card URLs.",
    )

    # -- CORS --
    ALLOWED_HOSTS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # -- Database --
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5433/mortgage-ai",
        description="Async SQLAlchemy connection string (asyncpg driver).",
    )
    COMPLIANCE_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://compliance_app:compliance_pass@localhost:5433/mortgage-ai",
        description="Async connection string for compliance_app role (HMDA schema access).",
    )

    # -- Auth --
    AUTH_DISABLED: bool = Field(
        default=False,
        description="Bypass JWT validation. Set True for tests and local dev without Keycloak.",
    )
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_ISSUER: str = Field(
        default="",
        description="JWT issuer URL if different from KEYCLOAK_URL (e.g. external route).",
    )
    KEYCLOAK_REALM: str = "mortgage-ai"
    KEYCLOAK_CLIENT_ID: str = "mortgage-ai-ui"
    JWKS_CACHE_TTL: int = Field(
        default=300,
        description="JWKS cache lifetime in seconds (default 5 minutes).",
    )

    # -- Admin panel --
    SQLADMIN_USER: str = Field(
        default="admin",
        description="Username for SQLAdmin login (ignored when AUTH_DISABLED=true).",
    )
    SQLADMIN_PASSWORD: str = Field(
        default="admin",
        description="Password for SQLAdmin login (ignored when AUTH_DISABLED=true).",
    )
    SQLADMIN_SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Secret key for SQLAdmin session cookies. Must be stable across restarts.",
    )

    # -- Safety / NeMo Guardrails --
    NEMO_GUARDRAILS_ENDPOINT: str | None = Field(
        default=None,
        description="NeMo Guardrails server endpoint. When set, safety shields are active.",
    )

    # -- LLM --
    # These env vars are consumed by config/models.yaml via ${VAR:-default}
    # substitution (see inference/config.py).  Settings here provide defaults
    # that pydantic-settings exposes; the YAML loader reads os.environ directly.
    LLM_API_KEY: str = Field(
        default="not-needed",
        description="API key for OpenAI-compatible LLM endpoint.",
    )
    LLM_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible LLM endpoint.",
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Model name for the primary LLM.",
    )

    # -- Vision model (optional, falls back to main LLM when unset) --
    VISION_MODEL: str | None = Field(
        default=None,
        description="Vision-capable model name. Defaults to LLM_MODEL if not set.",
    )
    VISION_BASE_URL: str | None = Field(
        default=None,
        description="Vision model endpoint. Defaults to LLM_BASE_URL if not set.",
    )
    VISION_API_KEY: str | None = Field(
        default=None,
        description="Vision model API key. Defaults to LLM_API_KEY if not set.",
    )

    # -- Storage (S3 / MinIO) --
    S3_ENDPOINT: str = "http://localhost:9090"
    S3_ACCESS_KEY: str = "minio"
    S3_SECRET_KEY: str = "miniosecret"
    S3_BUCKET: str = "documents"
    S3_REGION: str = "us-east-1"
    UPLOAD_MAX_SIZE_MB: int = 50

    # -- MCP --
    MCP_RISK_SERVER_URL: str = Field(
        default="http://localhost:8081/mcp",
        description="URL of the MCP risk assessment server (Streamable HTTP endpoint).",
    )
    PREDICTIVE_MODEL_MCP_URL: str | None = Field(
        default=None,
        description="URL of external predictive model MCP server. When set, predictive loan approval tool is available.",
        validate_default=True,
    )

    @field_validator("PREDICTIVE_MODEL_MCP_URL", mode="before")
    @classmethod
    def _empty_predictive_url_to_none(cls, v: str | None) -> str | None:
        """Treat empty string as unset so deleting the value disables the feature."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    # -- Observability (MLFlow) --
    MLFLOW_TRACKING_URI: str | None = Field(
        default=None,
        description="MLFlow tracking server URI. When set, tracing is active.",
    )
    MLFLOW_EXPERIMENT_NAME: str = Field(
        default="mortgage-ai",
        description="MLFlow experiment name for grouping traces.",
    )
    MLFLOW_TRACKING_AUTH: str | None = Field(
        default=None,
        description=(
            "MLflow auth mode. Set to 'kubernetes' on RHOAI 3.4+ to use the "
            "Kubernetes auth plugin -- reads the mounted ServiceAccount token "
            "and derives the workspace from the pod namespace automatically."
        ),
    )
    MLFLOW_TRACKING_TOKEN: str | None = Field(
        default=None,
        description=(
            "Bearer token for MLFlow authentication. "
            "Not needed when MLFLOW_TRACKING_AUTH=kubernetes."
        ),
    )
    MLFLOW_WORKSPACE: str | None = Field(
        default=None,
        description="MLFlow workspace name for multi-tenant deployments.",
    )
    MLFLOW_TRACKING_INSECURE_TLS: bool = Field(
        default=False,
        description="Skip TLS verification for MLFlow tracking server.",
    )


settings = Settings()
