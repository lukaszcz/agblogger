"""Tests for Bluesky OAuth API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import create_test_client

if TYPE_CHECKING:
    from backend.config import Settings


class TestClientMetadata:
    async def test_returns_metadata_when_configured(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        async with create_test_client(test_settings) as client:
            resp = await client.get("/api/crosspost/bluesky/client-metadata.json")
            assert resp.status_code == 200
            data = resp.json()
            assert data["client_id"] == (
                "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json"
            )
            assert data["application_type"] == "web"
            assert data["dpop_bound_access_tokens"] is True
            assert data["token_endpoint_auth_method"] == "private_key_jwt"
            assert "keys" in data["jwks"]
            assert data["jwks"]["keys"][0]["kty"] == "EC"

    async def test_returns_503_when_not_configured(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = ""
        async with create_test_client(test_settings) as client:
            resp = await client.get("/api/crosspost/bluesky/client-metadata.json")
            assert resp.status_code == 503


class TestAuthorizeEndpoint:
    async def test_returns_401_when_not_authenticated(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        async with create_test_client(test_settings) as client:
            resp = await client.post(
                "/api/crosspost/bluesky/authorize",
                json={"handle": "alice.bsky.social"},
            )
            assert resp.status_code == 401


class TestCallbackEndpoint:
    async def test_rejects_invalid_state(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/bluesky/callback",
                params={"code": "test-code", "state": "invalid-state"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
