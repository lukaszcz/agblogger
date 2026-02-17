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


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert data["database"] == "ok"


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


class TestFiltering:
    @pytest.mark.asyncio
    async def test_filter_by_label(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts", params={"labels": "swe"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for post in data["posts"]:
            assert "swe" in post["labels"]

    @pytest.mark.asyncio
    async def test_filter_by_author(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts", params={"author": "Admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/posts", params={"from": "2026-01-01", "to": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_filter_no_results(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts", params={"author": "Nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_label_mode_or(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/posts", params={"labels": "swe", "labelMode": "or"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_label_mode_and(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/posts", params={"labels": "swe", "labelMode": "and"}
        )
        assert resp.status_code == 200
        # AND with single label same as OR
        data = resp.json()
        assert data["total"] >= 1


class TestSync:
    @pytest.mark.asyncio
    async def test_sync_init(self, client: AsyncClient) -> None:
        # Login first
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "to_upload" in data
        assert "to_download" in data
        # Server has files, client has empty manifest, so should see downloads
        assert len(data["to_download"]) >= 1

    @pytest.mark.asyncio
    async def test_sync_init_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/sync/init",
            json={"client_manifest": []},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_sync_download(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/sync/download/posts/hello.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert b"Hello World" in resp.content

    @pytest.mark.asyncio
    async def test_sync_download_nonexistent(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/sync/download/nonexistent.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_commit(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["files_synced"] >= 1


class TestCrosspost:
    @pytest.mark.asyncio
    async def test_list_accounts_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/crosspost/accounts")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/crosspost/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_account(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/crosspost/accounts",
            json={
                "platform": "bluesky",
                "account_name": "test.bsky.social",
                "credentials": {"identifier": "test", "password": "secret"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["platform"] == "bluesky"
        assert data["account_name"] == "test.bsky.social"

    @pytest.mark.asyncio
    async def test_crosspost_history_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/crosspost/history/posts/hello.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []


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
