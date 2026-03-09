# This project was developed with assistance from AI tools.
"""Database configuration via pydantic-settings.

Replaces os.environ.get() calls in database.py with a typed settings class.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings -- reads from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5433/mortgage-ai"
    COMPLIANCE_DATABASE_URL: str = (
        "postgresql+asyncpg://compliance_app:compliance_pass@localhost:5433/mortgage-ai"
    )
    SQL_ECHO: bool = False


db_settings = DatabaseSettings()
