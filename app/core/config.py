"""Typed environment-based application configuration."""

from enum import StrEnum
from functools import lru_cache

from pydantic import PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings loaded from IELTS-prefixed environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IELTS_",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        """Require a structurally valid PostgreSQL connection URL."""
        PostgresDsn(value.get_secret_value())
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per application process."""
    return Settings()
