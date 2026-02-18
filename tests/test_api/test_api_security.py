"""API-level tests for security fixes (Issues 3, 6, 13)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import Settings
from backend.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@pytest.fixture
def app_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    """Create settings for test app."""
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "hello.md").write_text(
        "---\ncreated_at: 2026-02-02 22:21:29.975359+00\n"
        "author: Admin\nlabels: ['#swe']\n---\n# Hello World\n\nTest content.\n"
    )
    (tmp_content_dir / "labels.toml").write_text(
        "[labels]\n[labels.swe]\nnames = ['software engineering']\n"
    )
    # Write an about page
    (tmp_content_dir / "about.md").write_text("# About\n\nThis is the about page.\n")
    (tmp_content_dir / "index.toml").write_text(
        '[site]\ntitle = "Test Blog"\ntimezone = "UTC"\n\n'
        '[[pages]]\nid = "timeline"\ntitle = "Posts"\n\n'
        '[[pages]]\nid = "about"\ntitle = "About"\nfile = "about.md"\n'
    )
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
        admin_username="admin",
        admin_password="admin123",
    )


@pytest.fixture
async def client(app_settings: Settings) -> AsyncGenerator[AsyncClient]:
    """Create test HTTP client with lifespan triggered."""
    app = create_app(app_settings)

    from backend.database import create_engine as create_db_engine
    from backend.filesystem.content_manager import ContentManager
    from backend.models.base import Base
    from backend.services.auth_service import ensure_admin_user
    from backend.services.cache_service import rebuild_cache

    engine, session_factory = create_db_engine(app_settings)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = app_settings

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy import text

    async with session_factory() as session:
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
                "title, excerpt, content, content='posts_cache', content_rowid='id')"
            )
        )
        await session.commit()

    content_manager = ContentManager(content_dir=app_settings.content_dir)
    app.state.content_manager = content_manager

    async with session_factory() as session:
        await ensure_admin_user(session, app_settings)

    async with session_factory() as session:
        await rebuild_cache(session, content_manager)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    await engine.dispose()


class TestPageIdValidation:
    """Issue 3: Page ID must be validated against path traversal."""

    @pytest.mark.asyncio
    async def test_valid_page_id(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/about")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/../../etc/passwd")
        # FastAPI routing may return 404 due to path params, but the pattern check
        # should prevent directory traversal on valid-looking IDs
        assert resp.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_dots_in_page_id_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/test..page")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_slash_in_page_id_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/test/page")
        # This would be routed differently by FastAPI, likely 404
        assert resp.status_code in (400, 404, 405)

    @pytest.mark.asyncio
    async def test_special_chars_rejected(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages/test%20page")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_hyphen_underscore_allowed(self, client: AsyncClient) -> None:
        # This page doesn't exist but the ID is valid format
        resp = await client.get("/api/pages/my-page_1")
        assert resp.status_code == 404  # Valid ID, but page not found


class TestCrosspostHistoryAuth:
    """Issue 6: Crosspost history endpoint should require authentication."""

    @pytest.mark.asyncio
    async def test_history_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/crosspost/history/posts/hello.md")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_history_with_auth_works(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/crosspost/history/posts/hello.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestAuthTokenValidation:
    """Issue 13: Invalid JWT sub values should not crash the server."""

    @pytest.mark.asyncio
    async def test_malformed_bearer_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client: AsyncClient) -> None:
        from backend.services.auth_service import create_access_token

        # Create a token that expires immediately (negative minutes)
        token = create_access_token(
            {"sub": "1", "username": "admin", "is_admin": True},
            "test-secret",
            expires_minutes=-1,
        )
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestLabelCreateEmptyNames:
    """Issue 32: Creating labels with empty names should be rejected."""

    @pytest.mark.asyncio
    async def test_create_label_empty_names_rejected(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/labels",
            json={"id": "test-empty", "names": [""]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_label_whitespace_names_rejected(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/labels",
            json={"id": "test-ws", "names": ["   "]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
