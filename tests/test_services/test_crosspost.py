"""Tests for cross-posting base classes and formatting."""

from __future__ import annotations

import pytest

from backend.crosspost.base import CrossPostContent
from backend.crosspost.bluesky import _build_post_text, _find_facets
from backend.crosspost.mastodon import MastodonCrossPoster
from backend.crosspost.registry import list_platforms


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
        assert len(platforms) >= 2


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
