"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AgBlogger application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    secret_key: str = "change-me-in-production"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///data/db/agblogger.db"

    # Paths
    content_dir: Path = Path("./content")
    frontend_dir: Path = Path("./frontend/dist")

    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # CORS
    cors_origins: list[str] = Field(default_factory=list)

    # Auth
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Admin bootstrap
    admin_username: str = "admin"
    admin_password: str = "admin"
