"""Tests for startup hardening and global exception handlers."""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.config import Settings
from backend.main import create_app

if TYPE_CHECKING:
    from pathlib import Path


class TestGlobalExceptionHandlers:
    """Global exception handlers return structured JSON instead of crashing."""

    @pytest.mark.asyncio
    async def test_runtime_error_returns_502(self, tmp_path: Path) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
            frontend_dir=tmp_path / "no-frontend",
        )
        app = create_app(settings)

        @app.get("/test-runtime-error")
        async def _raise_runtime_error() -> None:
            raise RuntimeError("pandoc failed")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/test-runtime-error")
        assert resp.status_code == 502
        assert resp.json()["detail"] == "Rendering service unavailable"

    @pytest.mark.asyncio
    async def test_os_error_returns_500(self, tmp_path: Path) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
            frontend_dir=tmp_path / "no-frontend",
        )
        app = create_app(settings)

        @app.get("/test-os-error")
        async def _raise_os_error() -> None:
            raise OSError("disk full")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/test-os-error")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Storage operation failed"

    @pytest.mark.asyncio
    async def test_yaml_error_returns_422(self, tmp_path: Path) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
            frontend_dir=tmp_path / "no-frontend",
        )
        app = create_app(settings)

        @app.get("/test-yaml-error")
        async def _raise_yaml_error() -> None:
            raise yaml.YAMLError("invalid yaml")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/test-yaml-error")
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Invalid content format"

    @pytest.mark.asyncio
    async def test_json_decode_error_returns_500(self, tmp_path: Path) -> None:
        settings = Settings(
            secret_key="test-secret-key-min-32-characters-long",
            admin_password="testpassword",
            debug=True,
            frontend_dir=tmp_path / "no-frontend",
        )
        app = create_app(settings)

        @app.get("/test-json-error")
        async def _raise_json_error() -> None:
            json.loads("not valid json {")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/test-json-error")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Data integrity error"


class TestStaleLockFile:
    """H7: stale lock file is cleaned up."""

    def test_stale_lock_removed(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test-key.json"
        lock_path = key_path.with_name(f".{key_path.name}.lock")
        # Create a stale lock (older than 30 seconds)
        lock_path.write_text("")
        old_time = time.time() - 60
        os.utime(lock_path, (old_time, old_time))

        from backend.crosspost.atproto_oauth import load_or_create_keypair

        private_key, _jwk = load_or_create_keypair(key_path)
        assert private_key is not None
        assert not lock_path.exists()

    def test_corrupted_keypair_with_stale_lock(self, tmp_path: Path) -> None:
        key_path = tmp_path / "test-key.json"
        lock_path = key_path.with_name(f".{key_path.name}.lock")
        # Create a stale lock (older than 30 seconds)
        lock_path.write_text("")
        old_time = time.time() - 60
        os.utime(lock_path, (old_time, old_time))
        # Create a corrupted keypair file
        key_path.write_text("not valid json")

        from backend.crosspost.atproto_oauth import load_or_create_keypair

        # Should regenerate despite corruption
        private_key, _jwk = load_or_create_keypair(key_path)
        assert private_key is not None
