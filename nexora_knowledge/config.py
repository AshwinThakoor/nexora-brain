from __future__ import annotations

from functools import lru_cache
from os import environ

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = "sqlite:///./nexora_brain.db"


class Settings(BaseSettings):
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices("DATABASE_URL", "NEXORA_DATABASE_URL"),
    )
    chunk_size: int = 1200
    chunk_overlap: int = 180
    chunk_strategy: str = Field(
        default="structural",
        validation_alias=AliasChoices(
            "CHUNK_STRATEGY",
            "NEXORA_CHUNK_STRATEGY",
        ),
    )
    chunk_target_size: int = Field(
        default=1200,
        gt=0,
        le=1_000_000,
        validation_alias=AliasChoices(
            "CHUNK_TARGET_SIZE",
            "NEXORA_CHUNK_TARGET_SIZE",
        ),
    )
    chunk_maximum_size: int = Field(
        default=1800,
        gt=0,
        le=1_000_000,
        validation_alias=AliasChoices(
            "CHUNK_MAXIMUM_SIZE",
            "NEXORA_CHUNK_MAXIMUM_SIZE",
        ),
    )
    chunk_minimum_size: int = Field(
        default=200,
        ge=0,
        le=1_000_000,
        validation_alias=AliasChoices(
            "CHUNK_MINIMUM_SIZE",
            "NEXORA_CHUNK_MINIMUM_SIZE",
        ),
    )
    chunk_overlap_size: int = Field(
        default=150,
        ge=0,
        le=1_000_000,
        validation_alias=AliasChoices(
            "CHUNK_OVERLAP_SIZE",
            "NEXORA_CHUNK_OVERLAP_SIZE",
        ),
    )
    ingestion_retry_limit: int = Field(default=3, ge=0, le=100)
    max_upload_size: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        validation_alias=AliasChoices(
            "MAX_UPLOAD_SIZE",
            "NEXORA_MAX_UPLOAD_SIZE",
        ),
    )
    allowed_extensions: str = Field(
        default="pdf,docx,txt,csv,md,markdown,html,htm,json",
        validation_alias=AliasChoices(
            "ALLOWED_EXTENSIONS",
            "NEXORA_ALLOWED_EXTENSIONS",
        ),
    )
    allowed_mime_types: str = Field(
        default=(
            "application/pdf,"
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document,"
            "text/plain,text/csv,text/markdown,text/x-markdown,"
            "text/html,application/xhtml+xml,application/json"
        ),
        validation_alias=AliasChoices(
            "ALLOWED_MIME_TYPES",
            "NEXORA_ALLOWED_MIME_TYPES",
        ),
    )
    default_storage_provider: str = Field(
        default="local",
        validation_alias=AliasChoices(
            "DEFAULT_STORAGE_PROVIDER",
            "NEXORA_DEFAULT_STORAGE_PROVIDER",
        ),
    )
    local_storage_root: str = Field(
        default="./storage/uploads",
        validation_alias=AliasChoices(
            "LOCAL_STORAGE_ROOT",
            "NEXORA_LOCAL_STORAGE_ROOT",
        ),
    )
    upload_session_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        validation_alias=AliasChoices(
            "UPLOAD_SESSION_TTL_SECONDS",
            "NEXORA_UPLOAD_SESSION_TTL_SECONDS",
        ),
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEXORA_",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_url(explicit_url: str | None = None) -> str:
    """Return the database URL used by both the application and Alembic."""
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()

    for variable_name in ("DATABASE_URL", "NEXORA_DATABASE_URL"):
        value = environ.get(variable_name)
        if value and value.strip():
            return value.strip()

    return get_settings().database_url
