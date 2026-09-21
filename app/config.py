from typing import Literal
from uuid import UUID

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPACE_CORP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    environment: Literal["development", "test", "production"] = "development"
    application_name: str = "Agentic AI Operations Platform"
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: PostgresDsn | None = None
    migration_database_url: PostgresDsn | None = None
    default_workspace_id: UUID | None = None

    llm_model_id: str | None = Field(default=None, min_length=1, pattern=r"\S")
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
