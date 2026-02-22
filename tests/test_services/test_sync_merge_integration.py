"""Integration tests for simplified sync protocol."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from backend.config import Settings
from tests.conftest import create_test_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from httpx import AsyncClient


@pytest.fixture
def merge_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "shared.md").write_text(
        "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
        "labels:\n- '#a'\n---\n\nParagraph one.\n\nParagraph two.\n"
    )
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret-key-with-at-least-32-characters",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
        admin_username="admin",
        admin_password="admin123",
    )


@pytest.fixture
async def merge_client(merge_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(merge_settings) as ac:
        yield ac


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return resp.json()["access_token"]


class TestSyncStatus:
    async def test_status_returns_plan(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "to_upload" in data
        assert "to_download" in data
        assert "server_commit" in data


class TestSyncCommit:
    async def test_clean_body_merge(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "title": "Shared Post",
                "body": "Paragraph one (server edit).\n\nParagraph two.\n",
                "labels": ["a"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        client_content = (
            "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
            "labels:\n- '#a'\n---\n\nParagraph one.\n\nParagraph two (client edit).\n"
        )
        import json

        metadata = json.dumps({"deleted_files": [], "last_sync_commit": server_commit})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content.encode()), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_hash"] is not None
        assert len(data["conflicts"]) == 0

        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        merged = dl_resp.content.decode()
        assert "server edit" in merged
        assert "client edit" in merged

    async def test_body_conflict_server_wins(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "title": "Shared Post",
                "body": "Server version of paragraph one.\n\nParagraph two.\n",
                "labels": ["a"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        client_content = (
            "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
            "labels:\n- '#a'\n---\n\nClient version of paragraph one.\n\nParagraph two.\n"
        )
        import json

        metadata = json.dumps({"deleted_files": [], "last_sync_commit": server_commit})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content.encode()), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["body_conflicted"] is True

        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        assert b"Server version" in dl_resp.content

    async def test_no_base_server_wins(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        client_content = b"---\ntitle: Different\nauthor: Admin\n---\n\nClient only.\n"
        import json

        metadata = json.dumps({"deleted_files": [], "last_sync_commit": None})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conflicts"]) == 1

    async def test_commit_no_changes(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        import json

        metadata = json.dumps({"deleted_files": []})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_upload_new_file(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        new_content = b"---\ntitle: New Post\nauthor: Admin\n---\n\nBrand new.\n"
        import json

        metadata = json.dumps({"deleted_files": []})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            files=[
                (
                    "files",
                    ("posts/2026-02-22-new/index.md", io.BytesIO(new_content), "text/plain"),
                ),
            ],
            headers=headers,
        )
        assert resp.status_code == 200

        dl_resp = await merge_client.get(
            "/api/sync/download/posts/2026-02-22-new/index.md", headers=headers
        )
        assert dl_resp.status_code == 200

    async def test_delete_file(self, merge_client: AsyncClient, merge_settings: Settings) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        import json

        metadata = json.dumps({"deleted_files": ["posts/shared.md"]})
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": metadata},
            headers=headers,
        )
        assert resp.status_code == 200

        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        assert dl_resp.status_code == 404
