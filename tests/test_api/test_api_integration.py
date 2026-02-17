"""Integration tests for the API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import Settings
from backend.main import create_app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def app_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    """Create settings for test app."""
    # Add a sample post
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "hello.md").write_text(
        "---\ncreated_at: 2026-02-02 22:21:29.975359+00\n"
        "author: Admin\nlabels: ['#swe']\n---\n# Hello World\n\nTest content.\n"
    )
    # Add labels
    (tmp_content_dir / "labels.toml").write_text(
        "[labels]\n[labels.swe]\nnames = ['software engineering']\n"
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
async def client(app_settings: Settings) -> AsyncClient:  # type: ignore[misc]
    """Create test HTTP client with lifespan triggered."""
    app = create_app(app_settings)

    # Manually trigger lifespan since ASGITransport doesn't
    from contextlib import asynccontextmanager

    from backend.database import create_engine as create_db_engine
    from backend.filesystem.content_manager import ContentManager
    from backend.models.base import Base
    from backend.services.auth_service import ensure_admin_user
    from backend.services.cache_service import rebuild_cache

    engine, session_factory = create_db_engine(app_settings)
    app.state.engine = engine
    app.state.session_factory = session_factory

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
        yield ac  # type: ignore[misc]

    await engine.dispose()


class TestSiteConfig:
    @pytest.mark.asyncio
    async def test_get_site_config(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pages")
        assert resp.status_code == 200
        data = resp.json()
        assert "title" in data
        assert "pages" in data


class TestPosts:
    @pytest.mark.asyncio
    async def test_list_posts(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert "posts" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_post(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts/posts/hello.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Hello World"
        assert "rendered_html" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_post(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts/posts/nope.md")
        assert resp.status_code == 404


class TestLabels:
    @pytest.mark.asyncio
    async def test_list_labels(self, client: AsyncClient) -> None:
        resp = await client.get("/api/labels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_label_graph(self, client: AsyncClient) -> None:
        resp = await client.get("/api/labels/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


class TestAuth:
    @pytest.mark.asyncio
    async def test_login(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_bad_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client: AsyncClient) -> None:
        # Login first
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


class TestRender:
    @pytest.mark.asyncio
    async def test_render_preview(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/render/preview",
            json={"markdown": "# Hello\n\nWorld"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "html" in data
        assert "Hello" in data["html"]
