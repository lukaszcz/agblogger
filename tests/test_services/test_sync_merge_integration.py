"""Integration tests for three-way merge in sync protocol."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import Settings
from backend.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@pytest.fixture
def merge_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    """Create settings for merge integration tests."""
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "shared.md").write_text(
        "---\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n---\n"
        "# Shared Post\n\nParagraph one.\n\nParagraph two.\n"
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
async def merge_client(merge_settings: Settings) -> AsyncGenerator[AsyncClient]:
    """Create test HTTP client with git service for merge tests."""
    app = create_app(merge_settings)

    from backend.database import create_engine as create_db_engine
    from backend.filesystem.content_manager import ContentManager
    from backend.models.base import Base
    from backend.services.auth_service import ensure_admin_user
    from backend.services.cache_service import rebuild_cache
    from backend.services.git_service import GitService

    engine, session_factory = create_db_engine(merge_settings)
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

    content_manager = ContentManager(content_dir=merge_settings.content_dir)
    app.state.content_manager = content_manager

    git_service = GitService(content_dir=merge_settings.content_dir)
    git_service.init_repo()
    app.state.git_service = git_service

    async with session_factory() as session:
        await ensure_admin_user(session, merge_settings)

    async with session_factory() as session:
        await rebuild_cache(session, content_manager)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    await engine.dispose()


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return resp.json()["access_token"]


class TestThreeWayMerge:
    @pytest.mark.asyncio
    async def test_clean_merge(self, merge_client: AsyncClient, merge_settings: Settings) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        # Get initial server commit by doing a sync init
        resp = await merge_client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]
        assert server_commit is not None

        # Server-side edit (paragraph one) via API
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "body": "# Shared Post\n\nParagraph one (server edit).\n\nParagraph two.\n",
                "labels": [],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Upload client's version (paragraph two edited)
        client_content = (
            "---\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n---\n"
            "# Shared Post\n\nParagraph one.\n\nParagraph two (client edit).\n"
        )
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content.encode()), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        # Commit with conflict_files and last_sync_commit
        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": server_commit,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_hash"] is not None
        assert len(data["merge_results"]) == 1
        assert data["merge_results"][0]["status"] == "merged"

        # Verify the merged content on server has both edits
        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        merged = dl_resp.content.decode()
        assert "server edit" in merged
        assert "client edit" in merged

    @pytest.mark.asyncio
    async def test_conflict_returns_markers(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server edits paragraph one
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "body": "# Shared Post\n\nServer version of paragraph one.\n\nParagraph two.\n",
                "labels": [],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Client also edits paragraph one (conflict!)
        client_content = (
            "---\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n---\n"
            "# Shared Post\n\nClient version of paragraph one.\n\nParagraph two.\n"
        )
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content.encode()), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": server_commit,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["merge_results"]) == 1
        mr = data["merge_results"][0]
        assert mr["status"] == "conflicted"
        assert "<<<<<<< SERVER" in mr["content"]
        assert ">>>>>>> CLIENT" in mr["content"]

    @pytest.mark.asyncio
    async def test_no_base_falls_back_to_server(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        # Upload client version without providing last_sync_commit
        client_content = b"---\nauthor: Admin\n---\n# Conflict\n\nClient only.\n"
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": None,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["merge_results"]) == 1
        assert data["merge_results"][0]["status"] == "conflicted"

    @pytest.mark.asyncio
    async def test_invalid_commit_hash_falls_back(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        client_content = b"---\nauthor: Admin\n---\n# Different\n\nContent.\n"
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": "0000000000000000000000000000000000000000",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["merge_results"]) == 1
        assert data["merge_results"][0]["status"] == "conflicted"

    @pytest.mark.asyncio
    async def test_delete_modify_conflict_keeps_modified(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server deletes the file via API
        resp = await merge_client.delete(
            "/api/posts/posts/shared.md",
            headers=headers,
        )
        assert resp.status_code == 204

        # Client uploads their modified version
        client_content = b"---\nauthor: Admin\n---\n# Modified by client\n\nStill here.\n"
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": server_commit,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["merge_results"]) == 1
        assert data["merge_results"][0]["status"] == "merged"

        # File should still exist with client content
        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        assert dl_resp.status_code == 200
        assert b"Modified by client" in dl_resp.content

    @pytest.mark.asyncio
    async def test_commit_without_conflicts_backward_compatible(
        self, merge_client: AsyncClient
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["commit_hash"] is not None

    @pytest.mark.asyncio
    async def test_clean_merge_normalizes_frontmatter(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server edits paragraph one
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "body": "# Shared Post\n\nParagraph one (server).\n\nParagraph two.\n",
                "labels": [],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Client edits paragraph two (clean merge)
        client_content = (
            "---\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n---\n"
            "# Shared Post\n\nParagraph one.\n\nParagraph two (client).\n"
        )
        resp = await merge_client.post(
            "/api/sync/upload",
            params={"file_path": "posts/shared.md"},
            files={"file": ("shared.md", io.BytesIO(client_content.encode()), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await merge_client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "conflict_files": ["posts/shared.md"],
                "last_sync_commit": server_commit,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify the merged post has normalized timestamps
        post_resp = await merge_client.get("/api/posts/posts/shared.md")
        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["created_at"] is not None
        assert data["modified_at"] is not None
