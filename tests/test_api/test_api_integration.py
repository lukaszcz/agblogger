"""Integration tests for the API endpoints."""

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
        auth_self_registration=True,
    )


@pytest.fixture
async def client(app_settings: Settings) -> AsyncGenerator[AsyncClient]:
    """Create test HTTP client with lifespan triggered."""
    app = create_app(app_settings)

    # Manually trigger lifespan since ASGITransport doesn't

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
                "title, content, content='posts_cache', content_rowid='id')"
            )
        )
        await session.commit()

    content_manager = ContentManager(content_dir=app_settings.content_dir)
    app.state.content_manager = content_manager

    from backend.services.git_service import GitService

    git_service = GitService(content_dir=app_settings.content_dir)
    git_service.init_repo()
    app.state.git_service = git_service

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
        resp = await client.get("/api/posts", params={"from": "2026-01-01", "to": "2026-12-31"})
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
        resp = await client.get("/api/posts", params={"labels": "swe", "labelMode": "or"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_label_mode_and(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts", params={"labels": "swe", "labelMode": "and"})
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

    @pytest.mark.asyncio
    async def test_sync_upload_normalizes_frontmatter(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a post with NO front matter
        content = b"# New Synced Post\n\nContent here.\n"
        resp = await client.post(
            "/api/sync/upload",
            params={"file_path": "posts/synced-new.md"},
            files={"file": ("synced-new.md", io.BytesIO(content), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        # Commit with uploaded_files so normalization runs
        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}, "uploaded_files": ["posts/synced-new.md"]},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify the post was cached with normalized timestamps
        resp = await client.get("/api/posts/posts/synced-new.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Synced Post"
        assert data["created_at"] is not None
        assert data["modified_at"] is not None

    @pytest.mark.asyncio
    async def test_sync_commit_warns_on_unrecognized_fields(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a post with an unrecognized front matter field
        content = b"---\ncustom_field: hello\n---\n# Post\n\nContent.\n"
        resp = await client.post(
            "/api/sync/upload",
            params={"file_path": "posts/custom-fields.md"},
            files={"file": ("custom-fields.md", io.BytesIO(content), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        # Commit with uploaded_files
        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}, "uploaded_files": ["posts/custom-fields.md"]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any("custom_field" in w for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_sync_commit_backward_compatible_no_uploaded_files(
        self, client: AsyncClient
    ) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Commit with no uploaded_files field at all (backward compatible)
        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_commit_deletes_remote_files(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        before_resp = await client.get("/api/sync/download/posts/hello.md", headers=headers)
        assert before_resp.status_code == 200

        commit_resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}, "deleted_files": ["posts/hello.md"]},
            headers=headers,
        )
        assert commit_resp.status_code == 200

        after_resp = await client.get("/api/sync/download/posts/hello.md", headers=headers)
        assert after_resp.status_code == 404


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
        data = resp.json()
        assert data["items"] == []


class TestRender:
    @pytest.mark.asyncio
    async def test_render_preview(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/render/preview",
            json={"markdown": "# Hello\n\nWorld"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "html" in data
        assert "Hello" in data["html"]

    @pytest.mark.asyncio
    async def test_render_preview_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/render/preview",
            json={"markdown": "# Hello\n\nWorld"},
        )
        assert resp.status_code == 401


class TestPostCRUD:
    @pytest.mark.asyncio
    async def test_create_post_authenticated(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/new-test.md",
                "body": "# New Post\n\nContent here.\n",
                "labels": [],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "New Post"

    @pytest.mark.asyncio
    async def test_create_post_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/no-auth.md",
                "body": "# No Auth\n",
                "labels": [],
                "is_draft": False,
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_post_authenticated(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/posts/posts/hello.md",
            json={
                "body": "# Hello World Updated\n\nUpdated content.\n",
                "labels": ["swe"],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Hello World Updated"

    @pytest.mark.asyncio
    async def test_update_nonexistent_post_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/posts/posts/nope.md",
            json={
                "body": "# Nope\n",
                "labels": [],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_post_authenticated(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        # Create a post to delete
        await client.post(
            "/api/posts",
            json={
                "file_path": "posts/to-delete.md",
                "body": "# Delete Me\n",
                "labels": [],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.delete(
            "/api/posts/posts/to-delete.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_post_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.delete(
            "/api/posts/posts/nope.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_post_for_edit(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/posts/posts/hello.md/edit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == "posts/hello.md"
        assert "# Hello World" in data["body"]
        assert data["labels"] == ["swe"]
        assert "created_at" in data
        assert "modified_at" in data
        assert data["author"] == "Admin"

    @pytest.mark.asyncio
    async def test_get_post_for_edit_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts/posts/hello.md/edit")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_post_for_edit_not_found(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/posts/posts/nonexistent.md/edit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_post_structured(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/structured-new.md",
                "body": "# Structured Post\n\nContent here.",
                "labels": ["swe"],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Structured Post"
        assert data["labels"] == ["swe"]
        assert data["is_draft"] is False
        assert data["author"] == "Admin"

    @pytest.mark.asyncio
    async def test_update_post_structured(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/posts/posts/hello.md",
            json={
                "body": "# Hello World Structured\n\nUpdated structured content.\n",
                "labels": ["swe"],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Hello World Structured"
        assert data["labels"] == ["swe"]

    @pytest.mark.asyncio
    async def test_create_and_edit_roundtrip(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        # Create a post with labels and draft
        await client.post(
            "/api/posts",
            json={
                "file_path": "posts/roundtrip-test.md",
                "body": "# Roundtrip\n\nVerify all fields survive.",
                "labels": ["swe"],
                "is_draft": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Retrieve via /edit and verify all fields round-tripped
        resp = await client.get(
            "/api/posts/posts/roundtrip-test.md/edit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == "posts/roundtrip-test.md"
        assert "# Roundtrip" in data["body"]
        assert data["labels"] == ["swe"]
        assert data["is_draft"] is True
        assert data["author"] == "Admin"
        assert data["created_at"] is not None
        assert data["modified_at"] is not None

    @pytest.mark.asyncio
    async def test_create_draft_post(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/draft-test.md",
                "body": "# Draft Post\n\nThis is a draft.",
                "labels": [],
                "is_draft": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_draft"] is True

        # Verify via /edit endpoint
        edit_resp = await client.get(
            "/api/posts/posts/draft-test.md/edit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert edit_resp.status_code == 200
        assert edit_resp.json()["is_draft"] is True

    @pytest.mark.asyncio
    async def test_create_post_updates_label_filter_cache(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "cache-create"}, headers=headers)
        create_resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/cache-create.md",
                "body": "# Cache Create\n\nBody.\n",
                "labels": ["cache-create"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert create_resp.status_code == 201

        filtered_resp = await client.get("/api/posts", params={"labels": "cache-create"})
        assert filtered_resp.status_code == 200
        filtered_paths = [post["file_path"] for post in filtered_resp.json()["posts"]]
        assert "posts/cache-create.md" in filtered_paths

        label_resp = await client.get("/api/labels/cache-create")
        assert label_resp.status_code == 200
        assert label_resp.json()["post_count"] == 1

    @pytest.mark.asyncio
    async def test_update_post_updates_label_filter_cache(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "cache-update"}, headers=headers)
        update_resp = await client.put(
            "/api/posts/posts/hello.md",
            json={
                "body": "# Hello World\n\nRetagged.\n",
                "labels": ["cache-update"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert update_resp.status_code == 200

        new_label_resp = await client.get("/api/posts", params={"labels": "cache-update"})
        assert new_label_resp.status_code == 200
        new_label_paths = [post["file_path"] for post in new_label_resp.json()["posts"]]
        assert "posts/hello.md" in new_label_paths

        old_label_resp = await client.get("/api/posts", params={"labels": "swe"})
        assert old_label_resp.status_code == 200
        old_label_paths = [post["file_path"] for post in old_label_resp.json()["posts"]]
        assert "posts/hello.md" not in old_label_paths


class TestLabelCRUD:
    @pytest.mark.asyncio
    async def test_create_label(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/labels",
            json={"id": "cooking"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "cooking"
        assert data["names"] == ["cooking"]

    @pytest.mark.asyncio
    async def test_create_label_duplicate_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        # swe already exists from fixture
        resp = await client.post(
            "/api/labels",
            json={"id": "swe"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_label_invalid_id_returns_422(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        # Uppercase not allowed
        resp = await client.post(
            "/api/labels",
            json={"id": "UPPER"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

        # Leading hyphen not allowed
        resp = await client.post(
            "/api/labels",
            json={"id": "-starts-bad"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

        # Spaces not allowed
        resp = await client.post(
            "/api/labels",
            json={"id": "has spaces"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/labels",
            json={"id": "nope"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_label_with_parents(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/labels",
            json={"id": "new-child", "names": ["new child"], "parents": ["swe"]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parents"] == ["swe"]
        assert data["names"] == ["new child"]

    @pytest.mark.asyncio
    async def test_create_label_nonexistent_parent_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/labels",
            json={"id": "orphan-child", "parents": ["nonexistent"]},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_label_parents(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create parent labels
        await client.post("/api/labels", json={"id": "math"}, headers=headers)
        await client.post("/api/labels", json={"id": "physics"}, headers=headers)

        # Create child with one parent
        await client.post(
            "/api/labels",
            json={"id": "quantum", "parents": ["math"]},
            headers=headers,
        )

        # Update to have two parents
        resp = await client.put(
            "/api/labels/quantum",
            json={"names": ["quantum mechanics"], "parents": ["math", "physics"]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["parents"]) == {"math", "physics"}
        assert data["names"] == ["quantum mechanics"]

    @pytest.mark.asyncio
    async def test_update_label_cycle_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "top"}, headers=headers)
        await client.post(
            "/api/labels",
            json={"id": "bottom", "parents": ["top"]},
            headers=headers,
        )

        # Try to make top a child of bottom (cycle)
        resp = await client.put(
            "/api/labels/top",
            json={"names": ["top"], "parents": ["bottom"]},
            headers=headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_label_nonexistent_parent_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "orphan"}, headers=headers)
        resp = await client.put(
            "/api/labels/orphan",
            json={"names": ["orphan"], "parents": ["nonexistent"]},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_label_not_found_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.put(
            "/api/labels/nonexistent",
            json={"names": ["nope"], "parents": []},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/labels/swe",
            json={"names": ["swe"], "parents": []},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_label(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "temp"}, headers=headers)
        resp = await client.delete("/api/labels/temp", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = await client.get("/api/labels/temp")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_label_with_edges_cleans_up(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create A -> B -> C
        await client.post("/api/labels", json={"id": "chain-a"}, headers=headers)
        await client.post(
            "/api/labels",
            json={"id": "chain-b", "parents": ["chain-a"]},
            headers=headers,
        )
        await client.post(
            "/api/labels",
            json={"id": "chain-c", "parents": ["chain-b"]},
            headers=headers,
        )

        # Delete the middle label
        resp = await client.delete("/api/labels/chain-b", headers=headers)
        assert resp.status_code == 200

        # Verify chain-a no longer lists chain-b as child
        resp = await client.get("/api/labels/chain-a")
        assert resp.status_code == 200
        assert "chain-b" not in resp.json()["children"]

        # Verify chain-c no longer lists chain-b as parent
        resp = await client.get("/api/labels/chain-c")
        assert resp.status_code == 200
        assert "chain-b" not in resp.json()["parents"]

        # Graph should not contain chain-b or 500 error
        resp = await client.get("/api/labels/graph")
        assert resp.status_code == 200
        node_ids = [n["id"] for n in resp.json()["nodes"]]
        assert "chain-b" not in node_ids

    @pytest.mark.asyncio
    async def test_create_label_cycle_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/labels", json={"id": "cyc-a"}, headers=headers)
        await client.post(
            "/api/labels",
            json={"id": "cyc-b", "parents": ["cyc-a"]},
            headers=headers,
        )

        # Create cyc-c with parent cyc-b, then try to make cyc-a's parent cyc-c
        await client.post(
            "/api/labels",
            json={"id": "cyc-c", "parents": ["cyc-b"]},
            headers=headers,
        )
        resp = await client.put(
            "/api/labels/cyc-a",
            json={"names": ["A"], "parents": ["cyc-c"]},
            headers=headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/labels/swe")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_nonexistent_label_returns_404(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.delete("/api/labels/nonexistent", headers=headers)
        assert resp.status_code == 404


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_matching_posts(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts/search", params={"q": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "Hello" in data[0]["title"]

    @pytest.mark.asyncio
    async def test_search_no_results(self, client: AsyncClient) -> None:
        resp = await client.get("/api/posts/search", params={"q": "xyznonexistent"})
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_search_reflects_post_create(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        create_resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/search-fresh.md",
                "body": "# Search Fresh\n\nuniquekeycreate987\n",
                "labels": [],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201

        search_resp = await client.get("/api/posts/search", params={"q": "uniquekeycreate987"})
        assert search_resp.status_code == 200
        file_paths = [result["file_path"] for result in search_resp.json()]
        assert "posts/search-fresh.md" in file_paths

    @pytest.mark.asyncio
    async def test_search_reflects_post_update(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        update_resp = await client.put(
            "/api/posts/posts/hello.md",
            json={
                "body": "# Hello World\n\nuniquekeyupdate654\n",
                "labels": ["swe"],
                "is_draft": False,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_resp.status_code == 200

        search_resp = await client.get("/api/posts/search", params={"q": "uniquekeyupdate654"})
        assert search_resp.status_code == 200
        file_paths = [result["file_path"] for result in search_resp.json()]
        assert "posts/hello.md" in file_paths


class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_new_user_succeeds(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_409(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={
                "username": "dupuser",
                "email": "dup1@test.com",
                "password": "password123",
            },
        )
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": "dupuser",
                "email": "dup2@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={
                "username": "emailuser1",
                "email": "same@test.com",
                "password": "password123",
            },
        )
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": "emailuser2",
                "email": "same@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409


class TestSyncCycleWarnings:
    @pytest.mark.asyncio
    async def test_sync_commit_returns_cycle_warnings(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a labels.toml with a cycle
        cyclic_toml = (
            "[labels]\n"
            '[labels.a]\nnames = ["A"]\nparents = ["#b"]\n'
            '[labels.b]\nnames = ["B"]\nparents = ["#a"]\n'
        )

        resp = await client.post(
            "/api/sync/upload",
            params={"file_path": "labels.toml"},
            files={"file": ("labels.toml", io.BytesIO(cyclic_toml.encode()), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200

        # Commit sync — should return warnings about dropped edges
        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert len(data["warnings"]) == 1
        assert "Cycle detected" in data["warnings"][0]

    @pytest.mark.asyncio
    async def test_sync_commit_no_warnings_without_cycles(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["warnings"] == []


class TestSyncSecurity:
    @pytest.mark.asyncio
    async def test_sync_upload_path_traversal_rejected(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/sync/upload",
            params={"file_path": "../../../etc/passwd"},
            files={"file": ("passwd", b"malicious content", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_sync_upload_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/sync/upload",
            params={"file_path": "posts/test.md"},
            files={"file": ("test.md", b"content", "text/plain")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_sync_commit_deleted_files_path_traversal_rejected(
        self, client: AsyncClient
    ) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}, "deleted_files": ["../../../etc/passwd"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_sync_commit_conflict_files_path_traversal_rejected(
        self, client: AsyncClient
    ) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/sync/commit",
            json={"resolutions": {}, "conflict_files": ["../../../etc/passwd"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestSearchAfterDelete:
    @pytest.mark.asyncio
    async def test_search_does_not_find_deleted_post(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a post with a unique keyword
        create_resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/fts-delete-test.md",
                "body": "# FTS Delete Test\n\nuniqueftsdeletekey999\n",
                "labels": [],
                "is_draft": False,
            },
            headers=headers,
        )
        assert create_resp.status_code == 201

        # Verify it's searchable
        search_resp = await client.get("/api/posts/search", params={"q": "uniqueftsdeletekey999"})
        assert search_resp.status_code == 200
        assert len(search_resp.json()) >= 1

        # Delete the post
        delete_resp = await client.delete("/api/posts/posts/fts-delete-test.md", headers=headers)
        assert delete_resp.status_code == 204

        # Verify it's no longer searchable
        search_resp = await client.get("/api/posts/search", params={"q": "uniqueftsdeletekey999"})
        assert search_resp.status_code == 200
        assert search_resp.json() == []
