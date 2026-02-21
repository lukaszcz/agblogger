"""Tests for application configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from backend.config import Settings

if TYPE_CHECKING:
    from pathlib import Path


class TestSettings:
    def test_default_settings(self) -> None:
        s = Settings(_env_file=None)
        assert s.secret_key == "change-me-in-production"
        assert s.debug is False
        assert s.port == 8000

    def test_custom_settings(self, tmp_path: Path) -> None:
        s = Settings(
            secret_key="my-secret",
            debug=True,
            content_dir=tmp_path / "content",
            database_url="sqlite+aiosqlite:///test.db",
        )
        assert s.secret_key == "my-secret"
        assert s.debug is True
        assert s.content_dir == tmp_path / "content"

    def test_settings_from_fixture(self, test_settings: Settings) -> None:
        assert test_settings.secret_key == "test-secret-key"
        assert test_settings.debug is True
        assert test_settings.content_dir.exists()


class TestCliEntry:
    def test_cli_entry_uses_app_settings(self) -> None:
        """cli_entry() should use the global app's settings, not create a new Settings()."""
        from backend.main import app, cli_entry

        original_settings = getattr(app.state, "settings", None)
        app.state.settings = Settings(_env_file=None, host="127.0.0.1", port=9999, debug=True)

        try:
            with patch("uvicorn.run") as mock_run:
                cli_entry()

            mock_run.assert_called_once_with(
                "backend.main:app",
                host="127.0.0.1",
                port=9999,
                reload=True,
            )
        finally:
            if original_settings is None:
                del app.state.settings
            else:
                app.state.settings = original_settings
