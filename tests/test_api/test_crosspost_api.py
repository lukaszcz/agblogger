"""Tests for Mastodon OAuth API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import create_test_client

if TYPE_CHECKING:
    from backend.config import Settings


class TestMastodonAuthorize:
    async def test_mastodon_authorize_requires_auth(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        async with create_test_client(test_settings) as client:
            resp = await client.post(
                "/api/crosspost/mastodon/authorize",
                json={"instance_url": "https://mastodon.social"},
            )
            assert resp.status_code == 401

    async def test_mastodon_authorize_rejects_invalid_instance(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]

            resp = await client.post(
                "/api/crosspost/mastodon/authorize",
                json={"instance_url": "http://localhost"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid instance URL"

    async def test_mastodon_authorize_returns_503_when_not_configured(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = ""
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]

            resp = await client.post(
                "/api/crosspost/mastodon/authorize",
                json={"instance_url": "https://mastodon.social"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503


class TestMastodonCallback:
    async def test_mastodon_callback_rejects_invalid_state(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/mastodon/callback",
                params={"code": "test-code", "state": "invalid-state"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid or expired OAuth state"
