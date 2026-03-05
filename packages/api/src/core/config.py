# This project was developed with assistance from AI tools.
"""
Application configuration.

All settings read from environment variables with sensible local dev defaults.
Group related settings together; each group becomes a section future PRs extend.
"""

from pathlib import Path

from pydantic import Field
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
    APP_NAME: str = "summit-cap"
    DEBUG: bool = False

    # -- CORS --
    ALLOWED_HOSTS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # -- Database --
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5433/summit-cap",
        description="Async SQLAlchemy connection string (asyncpg driver).",
    )
    COMPLIANCE_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://compliance_app:compliance_pass@localhost:5433/summit-cap",
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
    KEYCLOAK_REALM: str = "summit-cap"
    KEYCLOAK_CLIENT_ID: str = "summit-cap-ui"
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

    # -- Safety / Shields --
    SAFETY_MODEL: str | None = Field(
        default=None,
        description="Llama Guard model name. When set, safety shields are active.",
    )
    SAFETY_ENDPOINT: str | None = Field(
        default=None,
        description="Safety model endpoint. Defaults to LLM_BASE_URL if not set.",
    )
    SAFETY_API_KEY: str | None = Field(
        default=None,
        description="Safety model API key. Defaults to LLM_API_KEY if not set.",
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
    LLM_MODEL_FAST: str = Field(
        default="gpt-4o-mini",
        description="Model name for the fast_small tier (simple queries).",
    )
    LLM_MODEL_CAPABLE: str = Field(
        default="gpt-4o-mini",
        description="Model name for the capable_large tier (complex reasoning + tools).",
    )

    # -- Storage (S3 / MinIO) --
    S3_ENDPOINT: str = "http://localhost:9090"
    S3_ACCESS_KEY: str = "minio"
    S3_SECRET_KEY: str = "miniosecret"
    S3_BUCKET: str = "documents"
    S3_REGION: str = "us-east-1"
    UPLOAD_MAX_SIZE_MB: int = 50

    # -- Observability (LangFuse) --
    LANGFUSE_PUBLIC_KEY: str | None = Field(
        default=None,
        description="LangFuse public key. When set (with secret key), tracing is active.",
    )
    LANGFUSE_SECRET_KEY: str | None = Field(
        default=None,
        description="LangFuse secret key.",
    )
    LANGFUSE_HOST: str | None = Field(
        default=None,
        description="LangFuse server URL (e.g. http://localhost:3001).",
    )


settings = Settings()
