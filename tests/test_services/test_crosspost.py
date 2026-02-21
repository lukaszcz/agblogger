"""Tests for cross-posting base classes and formatting."""

from __future__ import annotations

import json as json_mod

import httpx
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from backend.crosspost.atproto_oauth import generate_es256_keypair
from backend.crosspost.base import CrossPostContent
from backend.crosspost.bluesky import BlueskyCrossPoster, _build_post_text, _find_facets
from backend.crosspost.facebook import FacebookCrossPoster, _build_facebook_text
from backend.crosspost.mastodon import (
    MastodonCrossPoster,
    MastodonOAuthTokenError,
    _build_status_text,
    exchange_mastodon_oauth_token,
)
from backend.crosspost.registry import list_platforms
from backend.crosspost.x import X_CHAR_LIMIT, XCrossPoster, _build_tweet_text


async def _always_safe(_url: str) -> bool:
    return True


class TestBlueSkyFormatting:
    def test_build_post_text_short(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="Short excerpt.",
            url="https://blog.example.com/posts/test",
            labels=["swe", "ai"],
        )
        text = _build_post_text(content)
        assert "Short excerpt." in text
        assert "#swe" in text
        assert "#ai" in text
        assert "https://blog.example.com/posts/test" in text
        assert len(text) <= 300

    def test_build_post_text_long_truncation(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="A" * 500,
            url="https://blog.example.com/posts/test",
            labels=["swe"],
        )
        text = _build_post_text(content)
        assert len(text) <= 300
        assert "..." in text

    def test_build_post_text_uses_custom_text(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="My custom post text!",
        )
        text = _build_post_text(content)
        assert text == "My custom post text!"

    def test_build_post_text_rejects_custom_text_over_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 301,
        )
        with pytest.raises(ValueError, match="300"):
            _build_post_text(content)

    def test_build_post_text_accepts_custom_text_at_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 300,
        )
        text = _build_post_text(content)
        assert text == "A" * 300

    def test_find_facets_link(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Hello",
            url="https://blog.example.com",
            labels=[],
        )
        text = "Hello\n\nhttps://blog.example.com"
        facets = _find_facets(text, content)
        assert len(facets) >= 1
        link_facet = facets[0]
        assert link_facet["features"][0]["$type"] == "app.bsky.richtext.facet#link"

    def test_find_facets_hashtags(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Hello",
            url="https://blog.example.com",
            labels=["swe", "ai"],
        )
        text = "Hello\n\n#swe #ai\nhttps://blog.example.com"
        facets = _find_facets(text, content)
        types = [f["features"][0]["$type"] for f in facets]
        assert "app.bsky.richtext.facet#tag" in types


class TestRegistry:
    def test_list_platforms(self) -> None:
        platforms = list_platforms()
        assert "bluesky" in platforms
        assert "mastodon" in platforms
        assert "x" in platforms
        assert "facebook" in platforms
        assert len(platforms) >= 4


class TestMastodonUrlValidation:
    @pytest.mark.asyncio
    async def test_authenticate_rejects_localhost_instance_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requested_urls: list[str] = []

        class DummyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, str]:
                return {"id": "1", "acct": "tester"}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyResponse:
                requested_urls.append(url)
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.mastodon.httpx.AsyncClient", DummyAsyncClient)

        poster = MastodonCrossPoster()
        is_ok = await poster.authenticate(
            {"access_token": "token", "instance_url": "http://127.0.0.1:8080"}
        )
        assert is_ok is False
        assert requested_urls == []

    @pytest.mark.asyncio
    async def test_authenticate_accepts_public_https_instance_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requested_urls: list[str] = []

        class DummyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, str]:
                return {"id": "1", "acct": "tester"}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyResponse:
                requested_urls.append(url)
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.mastodon.httpx.AsyncClient", DummyAsyncClient)

        poster = MastodonCrossPoster()
        is_ok = await poster.authenticate(
            {"access_token": "token", "instance_url": "https://93.184.216.34"}
        )
        assert is_ok is True
        assert requested_urls == ["https://93.184.216.34/api/v1/accounts/verify_credentials"]


class TestMastodonFormatting:
    def test_build_status_text_uses_custom_text(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="My custom Mastodon text!",
        )
        text = _build_status_text(content)
        assert text == "My custom Mastodon text!"

    def test_build_status_text_rejects_custom_text_over_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 501,
        )
        with pytest.raises(ValueError, match="500"):
            _build_status_text(content)

    def test_build_status_text_accepts_custom_text_at_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 500,
        )
        text = _build_status_text(content)
        assert text == "A" * 500


class TestMastodonOAuthTokenExchange:
    async def test_raises_on_missing_access_token_in_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Token response with 200 but no access_token should raise MastodonOAuthTokenError."""

        class DummyResponse:
            status_code = 200
            text = '{"error": "something"}'

            @staticmethod
            def json() -> dict[str, str]:
                return {"error": "something"}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def post(self, url: str, **kwargs) -> DummyResponse:
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.mastodon.httpx.AsyncClient", DummyAsyncClient)
        monkeypatch.setattr(
            "backend.crosspost.mastodon._normalize_instance_url",
            lambda u: "https://mastodon.social",
        )

        with pytest.raises(MastodonOAuthTokenError, match="access_token"):
            await exchange_mastodon_oauth_token(
                instance_url="https://mastodon.social",
                code="test-code",
                client_id="test-client-id",
                client_secret="test-client-secret",
                redirect_uri="https://example.com/callback",
                pkce_verifier="test-verifier",
            )


def _make_oauth_credentials() -> dict[str, str]:
    """Build a complete set of OAuth credentials for testing."""
    private_key, jwk = generate_es256_keypair()
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    return {
        "access_token": "at_valid",
        "did": "did:plc:abc123",
        "handle": "alice.bsky.social",
        "pds_url": "https://pds.example.com",
        "dpop_private_key_pem": pem,
        "dpop_jwk": json_mod.dumps(jwk),
        "dpop_nonce": "nonce-1",
        "auth_server_issuer": "https://bsky.social",
        "token_endpoint": "https://bsky.social/oauth/token",
        "refresh_token": "rt_valid",
        "client_id": "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
    }


class TestBlueskyCrossPosterOAuth:
    async def test_authenticate_with_oauth_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("backend.crosspost.atproto_oauth._is_safe_url", _always_safe)
        creds = _make_oauth_credentials()
        poster = BlueskyCrossPoster()
        result = await poster.authenticate(creds)
        assert result is True

    async def test_authenticate_rejects_missing_fields(self) -> None:
        poster = BlueskyCrossPoster()
        result = await poster.authenticate({"access_token": "at_valid"})
        assert result is False

    async def test_post_uses_dpop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("backend.crosspost.atproto_oauth._is_safe_url", _always_safe)
        captured_headers: dict[str, str] = {}

        async def mock_post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
            headers = kwargs.get("headers", {})
            assert isinstance(headers, dict)
            captured_headers.update(headers)
            return httpx.Response(
                200,
                json={
                    "uri": "at://did:plc:abc123/app.bsky.feed.post/abc",
                    "cid": "bafy123",
                },
                headers={"DPoP-Nonce": "nonce-updated"},
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        poster = BlueskyCrossPoster()
        await poster.authenticate(_make_oauth_credentials())
        content = CrossPostContent(
            title="Test",
            excerpt="Hello",
            url="https://blog.example.com/post",
            labels=["swe"],
        )
        result = await poster.post(content)
        assert result.success
        assert captured_headers.get("Authorization", "").startswith("DPoP ")
        assert "DPoP" in captured_headers


class TestXFormatting:
    def test_build_tweet_text_short(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="Short excerpt.",
            url="https://blog.example.com/posts/test",
            labels=["swe", "ai"],
        )
        text = _build_tweet_text(content)
        assert "Short excerpt." in text
        assert "#swe" in text
        assert "#ai" in text
        assert "https://blog.example.com/posts/test" in text
        assert len(text) <= X_CHAR_LIMIT

    def test_build_tweet_text_long_truncation(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="A" * 500,
            url="https://blog.example.com/posts/test",
            labels=["swe"],
        )
        text = _build_tweet_text(content)
        assert len(text) <= X_CHAR_LIMIT
        assert "..." in text

    def test_build_tweet_text_uses_custom_text(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="My custom tweet!",
        )
        text = _build_tweet_text(content)
        assert text == "My custom tweet!"

    def test_build_tweet_text_rejects_custom_text_over_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 281,
        )
        with pytest.raises(ValueError, match="280"):
            _build_tweet_text(content)

    def test_build_tweet_text_accepts_custom_text_at_limit(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="A" * 280,
        )
        text = _build_tweet_text(content)
        assert text == "A" * 280


class TestXCrossPoster:
    async def test_authenticate_with_valid_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class DummyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"data": {"id": "123", "username": "testuser"}}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyResponse:
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.x.httpx.AsyncClient", DummyAsyncClient)

        poster = XCrossPoster()
        result = await poster.authenticate(
            {
                "access_token": "test_token",
                "refresh_token": "test_rt",
                "username": "testuser",
            }
        )
        assert result is True

    async def test_authenticate_rejects_missing_token(self) -> None:
        poster = XCrossPoster()
        result = await poster.authenticate({"refresh_token": "rt"})
        assert result is False

    async def test_post_creates_tweet(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        class DummyResponse:
            status_code = 201
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"data": {"id": "1234567890", "text": "Hello"}}

        class DummyVerifyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"data": {"id": "123", "username": "testuser"}}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyVerifyResponse:
                return DummyVerifyResponse()

            async def post(self, url: str, **kwargs) -> DummyResponse:
                captured["url"] = url
                captured["json"] = kwargs.get("json")
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.x.httpx.AsyncClient", DummyAsyncClient)

        poster = XCrossPoster()
        await poster.authenticate(
            {
                "access_token": "test_token",
                "refresh_token": "test_rt",
                "username": "testuser",
            }
        )
        content = CrossPostContent(
            title="Test",
            excerpt="Hello world",
            url="https://blog.example.com/post",
            labels=["swe"],
        )
        result = await poster.post(content)
        assert result.success
        assert result.platform_id == "1234567890"
        assert captured["url"] == "https://api.x.com/2/tweets"

    async def test_post_refreshes_on_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = 0

        class DummyRefreshResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, str]:
                return {"access_token": "new_at", "refresh_token": "new_rt"}

        class DummyTweetResponse:
            status_code = 201
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"data": {"id": "999", "text": "Hello"}}

        class Dummy401Response:
            status_code = 401
            text = "Unauthorized"

            @staticmethod
            def json() -> dict[str, str]:
                return {"detail": "Unauthorized"}

        class DummyVerifyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"data": {"id": "123", "username": "testuser"}}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyVerifyResponse:
                return DummyVerifyResponse()

            async def post(self, url: str, **kwargs) -> object:
                nonlocal call_count
                call_count += 1
                if url == "https://api.x.com/2/oauth2/token":
                    return DummyRefreshResponse()
                if call_count == 1:
                    return Dummy401Response()
                return DummyTweetResponse()

        monkeypatch.setattr("backend.crosspost.x.httpx.AsyncClient", DummyAsyncClient)

        poster = XCrossPoster()
        await poster.authenticate(
            {
                "access_token": "old_at",
                "refresh_token": "old_rt",
                "username": "testuser",
                "client_id": "test_client_id",
            }
        )
        content = CrossPostContent(
            title="Test",
            excerpt="Hello",
            url="https://example.com/post",
            labels=[],
        )
        result = await poster.post(content)
        assert result.success
        updated = poster.get_updated_credentials()
        assert updated is not None
        assert updated["access_token"] == "new_at"


class TestFacebookFormatting:
    def test_build_facebook_text_includes_parts(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="Short excerpt.",
            url="https://blog.example.com/posts/test",
            labels=["swe", "ai"],
        )
        text = _build_facebook_text(content)
        assert "Short excerpt." in text
        assert "#swe" in text
        assert "#ai" in text

    def test_build_facebook_text_uses_custom_text(self) -> None:
        content = CrossPostContent(
            title="Test",
            excerpt="Excerpt.",
            url="https://example.com/posts/test",
            custom_text="My custom Facebook post!",
        )
        text = _build_facebook_text(content)
        assert text == "My custom Facebook post!"


class TestFacebookCrossPoster:
    async def test_authenticate_with_valid_credentials(self) -> None:
        poster = FacebookCrossPoster()
        result = await poster.authenticate(
            {
                "page_access_token": "test_token",
                "page_id": "12345",
                "page_name": "My Page",
            }
        )
        assert result is True

    async def test_authenticate_rejects_missing_token(self) -> None:
        poster = FacebookCrossPoster()
        result = await poster.authenticate({"page_id": "12345"})
        assert result is False

    async def test_authenticate_rejects_missing_page_id(self) -> None:
        poster = FacebookCrossPoster()
        result = await poster.authenticate({"page_access_token": "test"})
        assert result is False

    async def test_post_to_page(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        class DummyResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, str]:
                return {"id": "12345_67890"}

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def post(self, url: str, **kwargs) -> DummyResponse:
                captured["url"] = url
                captured["json"] = kwargs.get("json")
                return DummyResponse()

        monkeypatch.setattr(
            "backend.crosspost.facebook.httpx.AsyncClient", DummyAsyncClient
        )

        poster = FacebookCrossPoster()
        await poster.authenticate(
            {
                "page_access_token": "test_token",
                "page_id": "12345",
                "page_name": "My Page",
            }
        )
        content = CrossPostContent(
            title="Test",
            excerpt="Hello world",
            url="https://blog.example.com/post",
            labels=["swe"],
        )
        result = await poster.post(content)
        assert result.success
        assert result.platform_id == "12345_67890"
        assert "12345" in str(captured["url"])
        assert captured["json"]["link"] == "https://blog.example.com/post"
