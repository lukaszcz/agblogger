"""Tests for cross-posting OAuth API endpoints."""

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


class TestXAuthorize:
    async def test_x_authorize_requires_auth(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.x_client_id = "test_client_id"
        test_settings.x_client_secret = "test_client_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.post("/api/crosspost/x/authorize")
            assert resp.status_code == 401

    async def test_x_authorize_returns_503_when_not_configured(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.x_client_id = ""
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/x/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503

    async def test_x_authorize_returns_authorization_url(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.x_client_id = "test_client_id"
        test_settings.x_client_secret = "test_client_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/x/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "authorization_url" in data
            auth_url = data["authorization_url"]
            assert auth_url.startswith("https://x.com/i/oauth2/authorize?")
            assert "client_id=test_client_id" in auth_url
            assert "code_challenge_method=S256" in auth_url
            assert "response_type=code" in auth_url
            assert "scope=tweet.read+tweet.write+users.read+offline.access" in auth_url

    async def test_x_authorize_returns_503_when_bluesky_client_url_not_set(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = ""
        test_settings.x_client_id = "test_client_id"
        test_settings.x_client_secret = "test_client_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/x/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503


class TestXCallback:
    async def test_x_callback_rejects_invalid_state(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.x_client_id = "test_client_id"
        test_settings.x_client_secret = "test_client_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/x/callback",
                params={"code": "test-code", "state": "invalid-state"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid or expired OAuth state"

    async def test_x_callback_handles_oauth_error_from_provider(
        self, test_settings: Settings
    ) -> None:
        """Issue #2: When user denies access, X redirects with error param instead of code."""
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.x_client_id = "test_client_id"
        test_settings.x_client_secret = "test_client_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/x/callback",
                params={
                    "error": "access_denied",
                    "state": "some-state",
                },
                follow_redirects=False,
            )
            # Should redirect to admin with error, not 422 validation error
            assert resp.status_code == 303
            location = resp.headers.get("location", "")
            assert "/admin" in location
            assert "oauth_error" in location


class TestFacebookAuthorize:
    async def test_facebook_authorize_requires_auth(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.post("/api/crosspost/facebook/authorize")
            assert resp.status_code == 401

    async def test_facebook_authorize_returns_503_when_not_configured(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = ""
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/facebook/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503

    async def test_facebook_authorize_returns_503_when_bluesky_client_url_not_set(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = ""
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/facebook/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503

    async def test_facebook_authorize_returns_authorization_url(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/facebook/authorize",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "authorization_url" in data
            auth_url = data["authorization_url"]
            assert auth_url.startswith("https://www.facebook.com/v22.0/dialog/oauth?")
            assert "client_id=test_app_id" in auth_url
            assert "response_type=code" in auth_url
            assert "pages_manage_posts" in auth_url


class TestFacebookCallback:
    async def test_facebook_callback_rejects_invalid_state(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/facebook/callback",
                params={"code": "test-code", "state": "invalid-state"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid or expired OAuth state"

    async def test_facebook_callback_handles_oauth_error_from_provider(
        self, test_settings: Settings
    ) -> None:
        """Issue #2: When user denies access, Facebook redirects with error param."""
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/facebook/callback",
                params={
                    "error": "access_denied",
                    "error_reason": "user_denied",
                    "state": "some-state",
                },
                follow_redirects=False,
            )
            # Should redirect to admin with error, not 422
            assert resp.status_code == 303
            location = resp.headers.get("location", "")
            assert "/admin" in location
            assert "oauth_error" in location


class TestFacebookPages:
    async def test_facebook_pages_requires_auth(self, test_settings: Settings) -> None:
        """Issue #1: Facebook pages endpoint should require auth."""
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.get(
                "/api/crosspost/facebook/pages",
                params={"state": "some-state"},
            )
            assert resp.status_code == 401

    async def test_facebook_pages_rejects_invalid_state(self, test_settings: Settings) -> None:
        """Issue #1: Invalid state token should return 400."""
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.get(
                "/api/crosspost/facebook/pages",
                params={"state": "invalid-state"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400


class TestFacebookSelectPage:
    async def test_facebook_select_page_requires_auth(self, test_settings: Settings) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        async with create_test_client(test_settings) as client:
            resp = await client.post(
                "/api/crosspost/facebook/select-page",
                json={"state": "some-state", "page_id": "123"},
            )
            assert resp.status_code == 401

    async def test_facebook_select_page_rejects_invalid_state(
        self, test_settings: Settings
    ) -> None:
        test_settings.bluesky_client_url = "https://myblog.example.com"
        test_settings.facebook_app_id = "test_app_id"
        test_settings.facebook_app_secret = "test_app_secret"
        test_settings.admin_password = "admin"
        async with create_test_client(test_settings) as client:
            login_resp = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            token = login_resp.json()["access_token"]
            resp = await client.post(
                "/api/crosspost/facebook/select-page",
                json={"state": "invalid-state", "page_id": "123"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Invalid or expired page selection state"
