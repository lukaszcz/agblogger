"""Regression tests for high-impact security issues."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backend.config import Settings
from tests.conftest import create_test_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from httpx import AsyncClient


@pytest.fixture
def app_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    """Create application settings for security regression tests."""
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "hello.md").write_text(
        "---\n"
        "title: Hello World\n"
        "created_at: 2026-02-02 22:21:29.975359+00\n"
        "modified_at: 2026-02-02 22:21:29.975359+00\n"
        "author: Admin\n"
        "labels: ['#swe']\n"
        "---\n"
        "Hello from fixture.\n",
        encoding="utf-8",
    )
    (tmp_content_dir / "labels.toml").write_text(
        "[labels]\n[labels.swe]\nnames = ['software engineering']\n",
        encoding="utf-8",
    )
    (tmp_content_dir / "about.md").write_text(
        "# About\n\nThis is the about page.\n",
        encoding="utf-8",
    )
    (tmp_content_dir / "index.toml").write_text(
        "[site]\n"
        'title = "Test Blog"\n'
        'timezone = "UTC"\n\n'
        "[[pages]]\n"
        'id = "timeline"\n'
        'title = "Posts"\n\n'
        "[[pages]]\n"
        'id = "about"\n'
        'title = "About"\n'
        'file = "about.md"\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret-key-very-long-for-security",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
        admin_username="admin",
        admin_password="admin123",
        auth_self_registration=True,
        auth_login_max_failures=2,
        auth_rate_limit_window_seconds=300,
    )


@pytest.fixture
async def client(app_settings: Settings) -> AsyncGenerator[AsyncClient]:
    """Create test HTTP client with initialized app state."""
    async with create_test_client(app_settings) as ac:
        yield ac


async def _login(client: AsyncClient, username: str, password: str) -> str:
    """Login helper returning the access token."""
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _register(client: AsyncClient, username: str, email: str, password: str) -> None:
    """Register a non-admin user."""
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201
    assert resp.json()["is_admin"] is False


class TestSyncAuthorizationBoundary:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_initialize_sync(self, client: AsyncClient) -> None:
        await _register(client, "writer", "writer@test.com", "writer-password")
        token = await _login(client, "writer", "writer-password")

        resp = await client.post(
            "/api/sync/init",
            json={"client_manifest": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestRenderedHtmlSanitization:
    @pytest.mark.asyncio
    async def test_render_preview_strips_script_and_javascript_links(
        self,
        client: AsyncClient,
    ) -> None:
        token = await _login(client, "admin", "admin123")
        resp = await client.post(
            "/api/render/preview",
            json={
                "markdown": (
                    "[click](javascript:alert('xss'))\n\n"
                    "<script>alert('owned')</script>\n\n"
                    "safe text"
                )
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        html = resp.json()["html"].lower()
        assert "<script" not in html
        assert 'href="javascript:' not in html


class TestDraftVisibility:
    @pytest.mark.asyncio
    async def test_draft_post_not_publicly_readable(self, client: AsyncClient) -> None:
        token = await _login(client, "admin", "admin123")
        create_resp = await client.post(
            "/api/posts",
            json={
                "file_path": "posts/private-draft.md",
                "title": "Private Draft",
                "body": "Top secret.",
                "labels": [],
                "is_draft": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201

        client.cookies.clear()
        unauth_resp = await client.get("/api/posts/posts/private-draft.md")
        assert unauth_resp.status_code == 404

        auth_resp = await client.get(
            "/api/posts/posts/private-draft.md",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert auth_resp.status_code == 200
        assert auth_resp.json()["is_draft"] is True


class TestCrosspostHistoryIsolation:
    @pytest.mark.asyncio
    async def test_crosspost_history_isolated_per_user(self, client: AsyncClient) -> None:
        admin_token = await _login(client, "admin", "admin123")
        trigger_resp = await client.post(
            "/api/crosspost/post",
            json={"post_path": "posts/hello.md", "platforms": ["bluesky"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert trigger_resp.status_code == 200
        assert trigger_resp.json()[0]["status"] == "failed"

        client.cookies.clear()
        await _register(client, "reader", "reader@test.com", "reader-password")
        reader_token = await _login(client, "reader", "reader-password")
        history_resp = await client.get(
            "/api/crosspost/history/posts/hello.md",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert history_resp.status_code == 200
        assert history_resp.json()["items"] == []


class TestPageTraversalGuard:
    @pytest.mark.asyncio
    async def test_page_file_path_cannot_escape_content_dir(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "posts").mkdir()
        (content_dir / "labels.toml").write_text("[labels]\n", encoding="utf-8")
        (tmp_path / "secret.md").write_text("# Secret\n\nsensitive", encoding="utf-8")
        (content_dir / "index.toml").write_text(
            "[site]\n"
            'title = "Traversal Test"\n'
            'timezone = "UTC"\n\n'
            "[[pages]]\n"
            'id = "timeline"\n'
            'title = "Posts"\n\n'
            "[[pages]]\n"
            'id = "leak"\n'
            'title = "Leak"\n'
            'file = "../secret.md"\n',
            encoding="utf-8",
        )
        settings = Settings(
            secret_key="test-secret-key-very-long-for-security",
            debug=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
            content_dir=content_dir,
            frontend_dir=tmp_path / "frontend",
            admin_username="admin",
            admin_password="admin123",
            auth_self_registration=True,
        )

        async with create_test_client(settings) as local_client:
            resp = await local_client.get("/api/pages/leak")
            assert resp.status_code == 404


class TestLoginOriginValidation:
    @pytest.mark.asyncio
    async def test_login_rejects_untrusted_origin(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            headers={"Origin": "http://evil.example"},
        )
        assert resp.status_code == 403


class TestRateLimitClientIpHandling:
    @pytest.mark.asyncio
    async def test_untrusted_forwarded_for_does_not_bypass_login_rate_limit(
        self, client: AsyncClient
    ) -> None:
        first = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        second = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
            headers={"X-Forwarded-For": "198.51.100.42"},
        )

        assert first.status_code == 401
        assert second.status_code == 429


class TestProductionHardeningDefaults:
    @pytest.mark.asyncio
    async def test_docs_disabled_headers_set_and_untrusted_host_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "posts").mkdir()
        (content_dir / "index.toml").write_text(
            "[site]\n"
            'title = "Hardening Test"\n'
            'timezone = "UTC"\n\n'
            "[[pages]]\n"
            'id = "timeline"\n'
            'title = "Posts"\n',
            encoding="utf-8",
        )
        (content_dir / "labels.toml").write_text("[labels]\n", encoding="utf-8")

        settings = Settings(
            secret_key="this-is-a-long-production-like-secret-key",
            debug=False,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'prod.db'}",
            content_dir=content_dir,
            frontend_dir=tmp_path / "frontend",
            admin_username="admin",
            admin_password="this-is-a-long-admin-password",
            trusted_hosts=["test"],
        )

        async with create_test_client(settings) as local_client:
            docs_resp = await local_client.get("/docs")
            assert docs_resp.status_code == 404

            health_resp = await local_client.get("/api/health")
            assert health_resp.status_code == 200
            assert health_resp.headers.get("x-content-type-options") == "nosniff"
            assert health_resp.headers.get("x-frame-options") == "DENY"
            assert health_resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
            assert "content-security-policy" in health_resp.headers

            bad_host_resp = await local_client.get("/api/health", headers={"Host": "evil.example"})
            assert bad_host_resp.status_code == 400


class TestProductionStartupValidation:
    @pytest.mark.asyncio
    async def test_production_rejects_insecure_default_secrets(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "posts").mkdir()
        (content_dir / "index.toml").write_text(
            "[site]\n"
            'title = "Hardening Test"\n'
            'timezone = "UTC"\n\n'
            "[[pages]]\n"
            'id = "timeline"\n'
            'title = "Posts"\n',
            encoding="utf-8",
        )
        (content_dir / "labels.toml").write_text("[labels]\n", encoding="utf-8")
        settings = Settings(
            secret_key="change-me-in-production",
            debug=False,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'prod.db'}",
            content_dir=content_dir,
            frontend_dir=tmp_path / "frontend",
            admin_username="admin",
            admin_password="admin",
            trusted_hosts=["test"],
        )

        with pytest.raises(ValueError):
            async with create_test_client(settings):
                pass
