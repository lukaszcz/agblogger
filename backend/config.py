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
    expose_docs: bool = False

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
    trusted_hosts: list[str] = Field(default_factory=list)
    trusted_proxy_ips: list[str] = Field(default_factory=list)

    # Auth
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    auth_self_registration: bool = False
    auth_invites_enabled: bool = True
    auth_invite_expire_days: int = Field(default=7, ge=1, le=90)
    auth_login_max_failures: int = Field(default=5, ge=1)
    auth_refresh_max_failures: int = Field(default=10, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=300, ge=1)
    auth_enforce_login_origin: bool = True

    # Admin bootstrap
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Response hardening
    security_headers_enabled: bool = True
    content_security_policy: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' https: data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    def validate_runtime_security(self) -> None:
        """Validate security-critical production settings."""
        if self.debug:
            return

        violations: list[str] = []
        if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
            violations.append(
                "SECRET_KEY must be overridden with a high-entropy value (>=32 chars)"
            )
        if self.admin_password == "admin" or len(self.admin_password) < 12:
            violations.append("ADMIN_PASSWORD must be overridden with a strong value (>=12 chars)")
        if not self.trusted_hosts:
            violations.append("TRUSTED_HOSTS must be configured in production")

        if violations:
            joined = "; ".join(violations)
            raise ValueError(f"Insecure production configuration: {joined}")
