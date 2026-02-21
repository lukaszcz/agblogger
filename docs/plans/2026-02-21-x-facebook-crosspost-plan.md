# X (Twitter) + Facebook Cross-Posting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add cross-posting support for X (Twitter) and Facebook Pages using the existing plugin architecture.

**Architecture:** Two new `CrossPoster` implementations (`XCrossPoster`, `FacebookCrossPoster`) following the exact pattern of the existing `MastodonCrossPoster`. Each gets OAuth 2.0 endpoints, encrypted credential storage, and frontend connect/disconnect UI. X uses OAuth 2.0 with PKCE and token refresh; Facebook uses OAuth 2.0 with a page-selection step and non-expiring Page Access Tokens.

**Tech Stack:** Python (FastAPI, httpx, Pydantic), TypeScript (React, ky), SQLite (existing `social_accounts` table), existing `OAuthStateStore` for state management.

**Design doc:** `docs/plans/2026-02-21-x-facebook-crosspost-design.md`

---

### Task 1: Add X_CLIENT_ID, X_CLIENT_SECRET, FACEBOOK_APP_ID, FACEBOOK_APP_SECRET to Settings

**Files:**
- Modify: `backend/config.py:55-56` (after `bluesky_client_url`)

**Step 1: Write the failing test**

Add to `tests/test_services/test_config.py`:

```python
class TestCrosspostSettings:
    def test_x_settings_default_empty(self) -> None:
        settings = Settings(secret_key="x" * 32, content_dir=Path("/tmp/test"))
        assert settings.x_client_id == ""
        assert settings.x_client_secret == ""

    def test_facebook_settings_default_empty(self) -> None:
        settings = Settings(secret_key="x" * 32, content_dir=Path("/tmp/test"))
        assert settings.facebook_app_id == ""
        assert settings.facebook_app_secret == ""
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_config.py::TestCrosspostSettings -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'x_client_id'`

**Step 3: Write minimal implementation**

In `backend/config.py`, after line 56 (`bluesky_client_url: str = ""`), add:

```python
    # X (Twitter) OAuth
    x_client_id: str = ""
    x_client_secret: str = ""

    # Facebook OAuth
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_config.py::TestCrosspostSettings -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/config.py tests/test_services/test_config.py
git commit -m "feat: add X and Facebook OAuth settings"
```

---

### Task 2: Implement XCrossPoster

**Files:**
- Create: `backend/crosspost/x.py`
- Test: `tests/test_services/test_crosspost.py` (add to existing file)

**Step 1: Write the failing tests**

Add to `tests/test_services/test_crosspost.py`:

```python
from backend.crosspost.x import XCrossPoster, _build_tweet_text, X_CHAR_LIMIT


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
        assert len(text) <= 280

    def test_build_tweet_text_long_truncation(self) -> None:
        content = CrossPostContent(
            title="Test Post",
            excerpt="A" * 500,
            url="https://blog.example.com/posts/test",
            labels=["swe"],
        )
        text = _build_tweet_text(content)
        assert len(text) <= 280
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
            {"access_token": "test_token", "refresh_token": "test_rt", "username": "testuser"}
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

        class DummyAsyncClient:
            async def __aenter__(self) -> DummyAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def get(self, url: str, **kwargs) -> DummyResponse:
                return DummyResponse()

            async def post(self, url: str, **kwargs) -> DummyResponse:
                captured["url"] = url
                captured["json"] = kwargs.get("json")
                return DummyResponse()

        monkeypatch.setattr("backend.crosspost.x.httpx.AsyncClient", DummyAsyncClient)

        poster = XCrossPoster()
        await poster.authenticate(
            {"access_token": "test_token", "refresh_token": "test_rt", "username": "testuser"}
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
            {"access_token": "old_at", "refresh_token": "old_rt", "username": "testuser"}
        )
        content = CrossPostContent(
            title="Test", excerpt="Hello", url="https://example.com/post", labels=[]
        )
        result = await poster.post(content)
        assert result.success
        updated = poster.get_updated_credentials()
        assert updated is not None
        assert updated["access_token"] == "new_at"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestXFormatting -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.crosspost.x'`

**Step 3: Write minimal implementation**

Create `backend/crosspost/x.py`:

```python
"""X (Twitter) cross-posting implementation using X API v2."""

from __future__ import annotations

import logging

import httpx

from backend.crosspost.base import CrossPostContent, CrossPostResult

logger = logging.getLogger(__name__)

X_CHAR_LIMIT = 280


def _build_tweet_text(content: CrossPostContent) -> str:
    """Build tweet text, truncated to fit within X's character limit.

    Format: excerpt + hashtags + link.
    """
    if content.custom_text is not None:
        if len(content.custom_text) > X_CHAR_LIMIT:
            msg = f"Custom text exceeds {X_CHAR_LIMIT} character limit"
            raise ValueError(msg)
        return content.custom_text

    link = content.url
    hashtags = " ".join(f"#{label}" for label in content.labels[:5])

    suffix_parts: list[str] = []
    if hashtags:
        suffix_parts.append(hashtags)
    suffix_parts.append(link)
    suffix = "\n\n" + "\n".join(suffix_parts)

    available = X_CHAR_LIMIT - len(suffix)

    excerpt = content.excerpt
    if available <= 3:
        excerpt = excerpt[: max(available, 0)]
    elif len(excerpt) > available:
        excerpt = excerpt[: available - 3].rsplit(" ", maxsplit=1)[0] + "..."

    return excerpt + suffix


class XCrossPoster:
    """Cross-poster for X (Twitter) using API v2."""

    platform: str = "x"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._username: str | None = None
        self._client_id: str = ""
        self._client_secret: str = ""
        self._updated_credentials: dict[str, str] | None = None

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Authenticate with X using OAuth 2.0 tokens.

        Expected keys: access_token, refresh_token, username.
        Optional keys: client_id, client_secret (needed for token refresh).
        """
        access_token = credentials.get("access_token", "")
        if not access_token:
            return False

        self._access_token = access_token
        self._refresh_token = credentials.get("refresh_token", "")
        self._username = credentials.get("username", "")
        self._client_id = credentials.get("client_id", "")
        self._client_secret = credentials.get("client_secret", "")

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    "https://api.x.com/2/users/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning("X auth failed: %s %s", resp.status_code, resp.text)
                    self._access_token = None
                    return False
                data = resp.json()
                self._username = data.get("data", {}).get("username", self._username)
                return True
            except httpx.HTTPError:
                logger.exception("X auth HTTP error")
                self._access_token = None
                return False

    async def _try_refresh_token(self) -> bool:
        """Attempt to refresh the access token."""
        if not self._refresh_token or not self._client_id:
            return False

        async with httpx.AsyncClient() as client:
            try:
                data: dict[str, str] = {
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                }
                if self._client_secret:
                    data["client_secret"] = self._client_secret
                resp = await client.post(
                    "https://api.x.com/2/oauth2/token",
                    data=data,
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning("X token refresh failed: %s", resp.status_code)
                    return False
                token_data = resp.json()
                self._access_token = token_data["access_token"]
                self._refresh_token = token_data.get("refresh_token", self._refresh_token)
                self._updated_credentials = {
                    "access_token": self._access_token or "",
                    "refresh_token": self._refresh_token or "",
                    "username": self._username or "",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                }
                return True
            except (httpx.HTTPError, KeyError):
                logger.exception("X token refresh error")
                return False

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a tweet on X."""
        if not self._access_token:
            return CrossPostResult(
                platform_id="", url="", success=False, error="Not authenticated"
            )

        tweet_text = _build_tweet_text(content)

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "https://api.x.com/2/tweets",
                    json={"text": tweet_text},
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=15.0,
                )
                if resp.status_code == 401 and await self._try_refresh_token():
                    resp = await client.post(
                        "https://api.x.com/2/tweets",
                        json={"text": tweet_text},
                        headers={"Authorization": f"Bearer {self._access_token}"},
                        timeout=15.0,
                    )
                if resp.status_code not in (200, 201):
                    return CrossPostResult(
                        platform_id="",
                        url="",
                        success=False,
                        error=f"X API error: {resp.status_code} {resp.text}",
                    )
                data = resp.json()
                tweet_id = data.get("data", {}).get("id", "")
                tweet_url = f"https://x.com/{self._username}/status/{tweet_id}" if tweet_id else ""
                return CrossPostResult(
                    platform_id=tweet_id, url=tweet_url, success=True
                )
            except httpx.HTTPError as exc:
                logger.exception("X post HTTP error")
                return CrossPostResult(
                    platform_id="", url="", success=False, error=f"HTTP error: {exc}"
                )

    async def validate_credentials(self) -> bool:
        """Check if current access token is still valid."""
        if not self._access_token:
            return False
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    "https://api.x.com/2/users/me",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=10.0,
                )
                return resp.status_code == 200
            except httpx.HTTPError:
                return False

    def get_updated_credentials(self) -> dict[str, str] | None:
        """Return refreshed credentials if tokens were updated during posting."""
        return self._updated_credentials
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestXFormatting tests/test_services/test_crosspost.py::TestXCrossPoster -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/crosspost/x.py tests/test_services/test_crosspost.py
git commit -m "feat: add XCrossPoster implementation with token refresh"
```

---

### Task 3: Implement FacebookCrossPoster

**Files:**
- Create: `backend/crosspost/facebook.py`
- Test: `tests/test_services/test_crosspost.py` (add to existing file)

**Step 1: Write the failing tests**

Add to `tests/test_services/test_crosspost.py`:

```python
from backend.crosspost.facebook import FacebookCrossPoster, _build_facebook_text


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

        monkeypatch.setattr("backend.crosspost.facebook.httpx.AsyncClient", DummyAsyncClient)

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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestFacebookFormatting -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.crosspost.facebook'`

**Step 3: Write minimal implementation**

Create `backend/crosspost/facebook.py`:

```python
"""Facebook cross-posting implementation using Graph API v22.0."""

from __future__ import annotations

import logging

import httpx

from backend.crosspost.base import CrossPostContent, CrossPostResult

logger = logging.getLogger(__name__)

FACEBOOK_GRAPH_API = "https://graph.facebook.com/v22.0"


class FacebookOAuthTokenError(Exception):
    """Raised when Facebook OAuth token exchange fails."""


def _build_facebook_text(content: CrossPostContent) -> str:
    """Build post text for Facebook. No character limit enforced."""
    if content.custom_text is not None:
        return content.custom_text

    hashtags = " ".join(f"#{label}" for label in content.labels[:10])

    parts: list[str] = [content.excerpt]
    if hashtags:
        parts.append(hashtags)
    return "\n\n".join(parts)


async def exchange_facebook_oauth_token(
    code: str,
    app_id: str,
    app_secret: str,
    redirect_uri: str,
) -> dict[str, str]:
    """Exchange authorization code for a Facebook user access token.

    Then exchange for a long-lived token and fetch managed pages.
    Returns dict with keys: user_access_token, pages (list of dicts).
    Raises FacebookOAuthTokenError on failure.
    """
    async with httpx.AsyncClient() as http_client:
        # Exchange code for short-lived user token
        token_resp = await http_client.get(
            f"{FACEBOOK_GRAPH_API}/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=15.0,
        )
        if token_resp.status_code != 200:
            msg = f"Token exchange failed: {token_resp.status_code}"
            raise FacebookOAuthTokenError(msg)
        token_data = token_resp.json()
        short_token = token_data.get("access_token")
        if not short_token:
            msg = "Token response missing access_token"
            raise FacebookOAuthTokenError(msg)

        # Exchange for long-lived user token
        ll_resp = await http_client.get(
            f"{FACEBOOK_GRAPH_API}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
            timeout=15.0,
        )
        if ll_resp.status_code != 200:
            msg = f"Long-lived token exchange failed: {ll_resp.status_code}"
            raise FacebookOAuthTokenError(msg)
        ll_data = ll_resp.json()
        long_lived_token = ll_data.get("access_token", short_token)

        # Fetch managed pages
        pages_resp = await http_client.get(
            f"{FACEBOOK_GRAPH_API}/me/accounts",
            params={"access_token": long_lived_token},
            timeout=15.0,
        )
        if pages_resp.status_code != 200:
            msg = f"Failed to fetch pages: {pages_resp.status_code}"
            raise FacebookOAuthTokenError(msg)
        pages_data = pages_resp.json()
        pages = pages_data.get("data", [])
        if not pages:
            msg = "No Facebook Pages found. You must manage at least one Page."
            raise FacebookOAuthTokenError(msg)

    return {
        "user_access_token": long_lived_token,
        "pages": pages,
    }


class FacebookCrossPoster:
    """Cross-poster for Facebook Pages using Graph API."""

    platform: str = "facebook"

    def __init__(self) -> None:
        self._page_access_token: str | None = None
        self._page_id: str | None = None
        self._page_name: str | None = None

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Authenticate with Facebook Page credentials.

        Expected keys: page_access_token, page_id, page_name.
        """
        page_access_token = credentials.get("page_access_token", "")
        page_id = credentials.get("page_id", "")
        if not page_access_token or not page_id:
            return False

        self._page_access_token = page_access_token
        self._page_id = page_id
        self._page_name = credentials.get("page_name", "")
        return True

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a post on a Facebook Page."""
        if not self._page_access_token or not self._page_id:
            return CrossPostResult(
                platform_id="", url="", success=False, error="Not authenticated"
            )

        message = _build_facebook_text(content)

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{FACEBOOK_GRAPH_API}/{self._page_id}/feed",
                    json={
                        "message": message,
                        "link": content.url,
                        "access_token": self._page_access_token,
                    },
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    return CrossPostResult(
                        platform_id="",
                        url="",
                        success=False,
                        error=f"Facebook API error: {resp.status_code} {resp.text}",
                    )
                data = resp.json()
                post_id = data.get("id", "")
                post_url = f"https://www.facebook.com/{post_id}" if post_id else ""
                return CrossPostResult(
                    platform_id=post_id, url=post_url, success=True
                )
            except httpx.HTTPError as exc:
                logger.exception("Facebook post HTTP error")
                return CrossPostResult(
                    platform_id="", url="", success=False, error=f"HTTP error: {exc}"
                )

    async def validate_credentials(self) -> bool:
        """Check if the Page access token is still valid."""
        if not self._page_access_token:
            return False
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{FACEBOOK_GRAPH_API}/me",
                    params={"access_token": self._page_access_token},
                    timeout=10.0,
                )
                return resp.status_code == 200
            except httpx.HTTPError:
                return False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestFacebookFormatting tests/test_services/test_crosspost.py::TestFacebookCrossPoster -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/crosspost/facebook.py tests/test_services/test_crosspost.py
git commit -m "feat: add FacebookCrossPoster implementation"
```

---

### Task 4: Register X and Facebook in the platform registry

**Files:**
- Modify: `backend/crosspost/registry.py`
- Test: `tests/test_services/test_crosspost.py` (existing TestRegistry)

**Step 1: Write the failing test**

Update `TestRegistry.test_list_platforms` in `tests/test_services/test_crosspost.py`:

```python
class TestRegistry:
    def test_list_platforms(self) -> None:
        platforms = list_platforms()
        assert "bluesky" in platforms
        assert "mastodon" in platforms
        assert "x" in platforms
        assert "facebook" in platforms
        assert len(platforms) >= 4
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestRegistry -v`
Expected: FAIL — `assert "x" in platforms`

**Step 3: Write minimal implementation**

Update `backend/crosspost/registry.py`:

```python
"""Platform registry for cross-posting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.crosspost.bluesky import BlueskyCrossPoster
from backend.crosspost.facebook import FacebookCrossPoster
from backend.crosspost.mastodon import MastodonCrossPoster
from backend.crosspost.x import XCrossPoster

if TYPE_CHECKING:
    from backend.crosspost.base import CrossPoster

PLATFORMS: dict[
    str,
    type[BlueskyCrossPoster]
    | type[MastodonCrossPoster]
    | type[XCrossPoster]
    | type[FacebookCrossPoster],
] = {
    "bluesky": BlueskyCrossPoster,
    "mastodon": MastodonCrossPoster,
    "x": XCrossPoster,
    "facebook": FacebookCrossPoster,
}


async def get_poster(platform: str, credentials: dict[str, str]) -> CrossPoster:
    """Create and authenticate a cross-poster for the given platform.

    Raises ValueError if the platform is unknown or authentication fails.
    """
    poster_cls = PLATFORMS.get(platform)
    if poster_cls is None:
        msg = f"Unknown platform: {platform!r}. Available: {list(PLATFORMS)}"
        raise ValueError(msg)

    poster = poster_cls()
    authenticated = await poster.authenticate(credentials)
    if not authenticated:
        msg = f"Failed to authenticate with {platform}"
        raise ValueError(msg)

    return poster


def list_platforms() -> list[str]:
    """Return the list of supported platform names."""
    return list(PLATFORMS.keys())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestRegistry -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/crosspost/registry.py tests/test_services/test_crosspost.py
git commit -m "feat: register X and Facebook in platform registry"
```

---

### Task 5: Add Pydantic schemas and OAuth state stores for X and Facebook

**Files:**
- Modify: `backend/schemas/crosspost.py:75-79` (add schemas after MastodonAuthorizeResponse)
- Modify: `backend/main.py:144-145` (add OAuth state stores)

**Step 1: Add schemas**

Add to `backend/schemas/crosspost.py` after line 78:

```python
class XAuthorizeResponse(BaseModel):
    """Response with authorization URL for X OAuth."""

    authorization_url: str


class FacebookAuthorizeResponse(BaseModel):
    """Response with authorization URL for Facebook OAuth."""

    authorization_url: str


class FacebookSelectPageRequest(BaseModel):
    """Request to select a Facebook Page after OAuth."""

    state: str = Field(min_length=1, description="OAuth state token from callback")
    page_id: str = Field(min_length=1, description="Selected Facebook Page ID")


class FacebookSelectPageResponse(BaseModel):
    """Response after selecting a Facebook Page."""

    account_name: str
```

**Step 2: Add OAuth state stores in main.py**

In `backend/main.py`, after line 145 (`app.state.mastodon_oauth_state = OAuthStateStore(ttl_seconds=600)`), add:

```python
    app.state.x_oauth_state = OAuthStateStore(ttl_seconds=600)
    app.state.facebook_oauth_state = OAuthStateStore(ttl_seconds=600)
```

**Step 3: Run existing tests to verify no regressions**

Run: `uv run pytest tests/test_api/test_crosspost_api.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/schemas/crosspost.py backend/main.py
git commit -m "feat: add X/Facebook schemas and OAuth state stores"
```

---

### Task 6: Add X OAuth API endpoints

**Files:**
- Modify: `backend/api/crosspost.py` (add endpoints after mastodon_callback)
- Test: `tests/test_api/test_crosspost_api.py` (add X tests)

**Step 1: Write the failing tests**

Add to `tests/test_api/test_crosspost_api.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_crosspost_api.py::TestXAuthorize -v`
Expected: FAIL (endpoint doesn't exist yet → 404 or 405)

**Step 3: Write the endpoint implementations**

Add to `backend/api/crosspost.py` after the mastodon_callback function. Update imports at the top of the file to include:

```python
from backend.schemas.crosspost import (
    # ...existing imports...
    XAuthorizeResponse,
    FacebookAuthorizeResponse,
    FacebookSelectPageRequest,
    FacebookSelectPageResponse,
)
```

Add the X endpoints:

```python
@router.post("/x/authorize", response_model=XAuthorizeResponse)
async def x_authorize(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> XAuthorizeResponse:
    """Start X (Twitter) OAuth 2.0 flow with PKCE."""
    if not settings.x_client_id or not settings.x_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="X OAuth not configured: X_CLIENT_ID and X_CLIENT_SECRET not set",
        )
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth not configured: BLUESKY_CLIENT_URL not set",
        )

    import hashlib
    import secrets

    base_url = settings.bluesky_client_url.rstrip("/")
    redirect_uri = f"{base_url}/api/crosspost/x/callback"

    # PKCE
    unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    code_verifier = "".join(secrets.choice(unreserved) for _ in range(64))
    code_challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
    import base64

    code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).rstrip(b"=").decode("ascii")

    oauth_state = secrets.token_hex(32)

    state_store = request.app.state.x_oauth_state
    state_store.set(
        oauth_state,
        {
            "pkce_verifier": code_verifier,
            "user_id": user.id,
            "redirect_uri": redirect_uri,
            "client_id": settings.x_client_id,
            "client_secret": settings.x_client_secret,
        },
    )

    from urllib.parse import urlencode

    auth_params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.x_client_id,
            "redirect_uri": redirect_uri,
            "scope": "tweet.read tweet.write users.read offline.access",
            "state": oauth_state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorization_url = f"https://x.com/i/oauth2/authorize?{auth_params}"
    return XAuthorizeResponse(authorization_url=authorization_url)


@router.get("/x/callback")
async def x_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Handle X OAuth callback: exchange code for tokens, store account."""
    state_store = request.app.state.x_oauth_state
    pending = state_store.pop(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    import httpx

    # Exchange code for tokens
    async with httpx.AsyncClient() as http_client:
        try:
            token_resp = await http_client.post(
                "https://api.x.com/2/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": pending["redirect_uri"],
                    "client_id": pending["client_id"],
                    "code_verifier": pending["pkce_verifier"],
                },
                auth=(pending["client_id"], pending["client_secret"]),
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"X OAuth HTTP error: {exc}",
            ) from exc

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"X token exchange failed: {token_resp.status_code}",
        )
    token_data = token_resp.json()
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    # Fetch username
    async with httpx.AsyncClient() as http_client:
        try:
            user_resp = await http_client.get(
                "https://api.x.com/2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"X user fetch failed: {exc}",
            ) from exc

    if user_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"X user fetch failed: {user_resp.status_code}",
        )
    user_data = user_resp.json()
    username = user_data.get("data", {}).get("username", "unknown")

    credentials = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "username": username,
        "client_id": pending["client_id"],
        "client_secret": pending["client_secret"],
    }
    account_name = f"@{username}"
    account_data = SocialAccountCreate(
        platform="x",
        account_name=account_name,
        credentials=credentials,
    )
    try:
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)
    except DuplicateAccountError:
        existing = await get_social_accounts(session, pending["user_id"])
        replaced = False
        for acct in existing:
            if acct.platform == "x" and acct.account_name == account_name:
                await delete_social_account(session, acct.id, pending["user_id"])
                replaced = True
                break
        if not replaced:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="X account already exists",
            ) from None
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)

    base_url = settings.bluesky_client_url.rstrip("/")
    return RedirectResponse(url=f"{base_url}/admin", status_code=303)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_crosspost_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/crosspost.py tests/test_api/test_crosspost_api.py
git commit -m "feat: add X OAuth authorize and callback endpoints"
```

---

### Task 7: Add Facebook OAuth API endpoints

**Files:**
- Modify: `backend/api/crosspost.py` (add endpoints after X callback)
- Test: `tests/test_api/test_crosspost_api.py` (add Facebook tests)

**Step 1: Write the failing tests**

Add to `tests/test_api/test_crosspost_api.py`:

```python
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


class TestFacebookCallback:
    async def test_facebook_callback_rejects_invalid_state(
        self, test_settings: Settings
    ) -> None:
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_crosspost_api.py::TestFacebookAuthorize -v`
Expected: FAIL (404)

**Step 3: Write the endpoint implementations**

Add to `backend/api/crosspost.py`:

```python
@router.post("/facebook/authorize", response_model=FacebookAuthorizeResponse)
async def facebook_authorize(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> FacebookAuthorizeResponse:
    """Start Facebook OAuth flow."""
    if not settings.facebook_app_id or not settings.facebook_app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook OAuth not configured: FACEBOOK_APP_ID and FACEBOOK_APP_SECRET not set",
        )
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth not configured: BLUESKY_CLIENT_URL not set",
        )

    import secrets

    base_url = settings.bluesky_client_url.rstrip("/")
    redirect_uri = f"{base_url}/api/crosspost/facebook/callback"
    oauth_state = secrets.token_hex(32)

    state_store = request.app.state.facebook_oauth_state
    state_store.set(
        oauth_state,
        {
            "user_id": user.id,
            "redirect_uri": redirect_uri,
            "app_id": settings.facebook_app_id,
            "app_secret": settings.facebook_app_secret,
        },
    )

    from urllib.parse import urlencode

    auth_params = urlencode(
        {
            "client_id": settings.facebook_app_id,
            "redirect_uri": redirect_uri,
            "state": oauth_state,
            "scope": "pages_manage_posts,pages_read_engagement,pages_show_list",
            "response_type": "code",
        }
    )
    authorization_url = f"https://www.facebook.com/v22.0/dialog/oauth?{auth_params}"
    return FacebookAuthorizeResponse(authorization_url=authorization_url)


@router.get("/facebook/callback")
async def facebook_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Handle Facebook OAuth callback: exchange code, fetch pages, store or prompt selection."""
    state_store = request.app.state.facebook_oauth_state
    pending = state_store.pop(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    from backend.crosspost.facebook import FacebookOAuthTokenError, exchange_facebook_oauth_token

    import httpx

    try:
        result = await exchange_facebook_oauth_token(
            code=code,
            app_id=pending["app_id"],
            app_secret=pending["app_secret"],
            redirect_uri=pending["redirect_uri"],
        )
    except FacebookOAuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Facebook OAuth HTTP error: {exc}",
        ) from exc

    pages = result["pages"]
    base_url = settings.bluesky_client_url.rstrip("/")

    if len(pages) == 1:
        # Auto-select single page
        page = pages[0]
        credentials = {
            "page_access_token": page["access_token"],
            "page_id": page["id"],
            "page_name": page.get("name", ""),
        }
        account_name = page.get("name", f"Page {page['id']}")
        account_data = SocialAccountCreate(
            platform="facebook",
            account_name=account_name,
            credentials=credentials,
        )
        try:
            await create_social_account(
                session, pending["user_id"], account_data, settings.secret_key
            )
        except DuplicateAccountError:
            existing = await get_social_accounts(session, pending["user_id"])
            for acct in existing:
                if acct.platform == "facebook" and acct.account_name == account_name:
                    await delete_social_account(session, acct.id, pending["user_id"])
                    break
            await create_social_account(
                session, pending["user_id"], account_data, settings.secret_key
            )
        return RedirectResponse(url=f"{base_url}/admin", status_code=303)

    # Multiple pages: store in temp state and redirect with page selection needed
    page_selection_state = secrets.token_hex(32)
    state_store = request.app.state.facebook_oauth_state
    state_store.set(
        page_selection_state,
        {
            "user_id": pending["user_id"],
            "pages": pages,
        },
    )

    from urllib.parse import urlencode

    import secrets

    page_params = urlencode({"fb_pages": page_selection_state})
    return RedirectResponse(url=f"{base_url}/admin?{page_params}", status_code=303)


@router.post("/facebook/select-page", response_model=FacebookSelectPageResponse)
async def facebook_select_page(
    body: FacebookSelectPageRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> FacebookSelectPageResponse:
    """Finalize Facebook account by selecting a Page from the OAuth results."""
    state_store = request.app.state.facebook_oauth_state
    pending = state_store.pop(body.state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired page selection state",
        )
    if pending["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User mismatch",
        )

    pages = pending["pages"]
    page = next((p for p in pages if p["id"] == body.page_id), None)
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page not found in OAuth results",
        )

    credentials = {
        "page_access_token": page["access_token"],
        "page_id": page["id"],
        "page_name": page.get("name", ""),
    }
    account_name = page.get("name", f"Page {page['id']}")
    account_data = SocialAccountCreate(
        platform="facebook",
        account_name=account_name,
        credentials=credentials,
    )
    try:
        await create_social_account(session, user.id, account_data, settings.secret_key)
    except DuplicateAccountError:
        existing = await get_social_accounts(session, user.id)
        for acct in existing:
            if acct.platform == "facebook" and acct.account_name == account_name:
                await delete_social_account(session, acct.id, user.id)
                break
        await create_social_account(session, user.id, account_data, settings.secret_key)
    return FacebookSelectPageResponse(account_name=account_name)
```

Note: The `facebook_callback` function uses `import secrets` after the import-style established in the Mastodon callback at lines 381-391 of the existing code.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_crosspost_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/crosspost.py tests/test_api/test_crosspost_api.py
git commit -m "feat: add Facebook OAuth authorize, callback, and page selection endpoints"
```

---

### Task 8: Add OAuth state stores to test conftest

**Files:**
- Modify: `tests/conftest.py` (add x and facebook state stores)

**Step 1: Check if conftest already initializes state stores for new platforms**

The `create_test_client` in conftest creates `bluesky_oauth_state` and `mastodon_oauth_state`. Since `main.py` lifespan now also creates `x_oauth_state` and `facebook_oauth_state`, the test client factory must match.

Add after the mastodon state store line in conftest:

```python
    app.state.x_oauth_state = OAuthStateStore(ttl_seconds=600)
    app.state.facebook_oauth_state = OAuthStateStore(ttl_seconds=600)
```

**Step 2: Run all crosspost tests**

Run: `uv run pytest tests/test_api/test_crosspost_api.py tests/test_services/test_crosspost.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add X and Facebook OAuth state stores to test conftest"
```

---

### Task 9: Add PlatformIcon SVGs for X and Facebook

**Files:**
- Modify: `frontend/src/components/crosspost/PlatformIcon.tsx:36` (before fallback)

**Step 1: Add X icon**

After the mastodon block (line 36), before the fallback `return` (line 38), add:

```tsx
  if (platform === 'x') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="currentColor"
        className={className}
        aria-label="X"
      >
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    )
  }

  if (platform === 'facebook') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="currentColor"
        className={className}
        aria-label="Facebook"
      >
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
      </svg>
    )
  }
```

**Step 2: Run frontend static checks**

Run: `cd frontend && npx eslint src/components/crosspost/PlatformIcon.tsx`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/crosspost/PlatformIcon.tsx
git commit -m "feat: add X and Facebook SVG platform icons"
```

---

### Task 10: Add frontend API client functions for X and Facebook

**Files:**
- Modify: `frontend/src/api/crosspost.ts:46` (after authorizeMastodon)

**Step 1: Add functions**

After `authorizeMastodon` (line 46), add:

```typescript
export async function authorizeX(): Promise<{ authorization_url: string }> {
  return api
    .post('crosspost/x/authorize')
    .json<{ authorization_url: string }>()
}

export async function authorizeFacebook(): Promise<{ authorization_url: string }> {
  return api
    .post('crosspost/facebook/authorize')
    .json<{ authorization_url: string }>()
}

export interface FacebookPage {
  id: string
  name: string
  access_token: string
}

export async function selectFacebookPage(
  state: string,
  pageId: string,
): Promise<{ account_name: string }> {
  return api
    .post('crosspost/facebook/select-page', {
      json: { state, page_id: pageId },
    })
    .json<{ account_name: string }>()
}
```

**Step 2: Run frontend static checks**

Run: `cd frontend && npx eslint src/api/crosspost.ts`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/api/crosspost.ts
git commit -m "feat: add X and Facebook frontend API client functions"
```

---

### Task 11: Update CrossPostDialog character limits

**Files:**
- Modify: `frontend/src/components/crosspost/CrossPostDialog.tsx:7-10`

**Step 1: Update the CHAR_LIMITS constant**

Change lines 7-10 from:

```typescript
const CHAR_LIMITS: Record<string, number> = {
  bluesky: 300,
  mastodon: 500,
}
```

To:

```typescript
const CHAR_LIMITS: Record<string, number> = {
  bluesky: 300,
  x: 280,
  mastodon: 500,
}
```

Note: Facebook has no practical character limit, so it's intentionally omitted (the dialog only shows counters for platforms in `CHAR_LIMITS`).

**Step 2: Run frontend static checks**

Run: `cd frontend && npx eslint src/components/crosspost/CrossPostDialog.tsx`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/crosspost/CrossPostDialog.tsx
git commit -m "feat: add X character limit to cross-post dialog"
```

---

### Task 12: Update SocialAccountsPanel with X and Facebook connect UI

**Files:**
- Modify: `frontend/src/components/crosspost/SocialAccountsPanel.tsx`

**Step 1: Update imports**

At line 7, add the new API functions:

```typescript
import {
  fetchSocialAccounts,
  deleteSocialAccount,
  authorizeBluesky,
  authorizeMastodon,
  authorizeX,
  authorizeFacebook,
  selectFacebookPage,
} from '@/api/crosspost'
import type { SocialAccount, FacebookPage } from '@/api/crosspost'
```

**Step 2: Update connectingPlatform type (line 35)**

```typescript
const [connectingPlatform, setConnectingPlatform] = useState<
  'bluesky' | 'mastodon' | 'x' | 'facebook' | null
>(null)
```

**Step 3: Add Facebook page selection state (after line 42)**

```typescript
  // Facebook page selection state
  const [facebookPages, setFacebookPages] = useState<FacebookPage[]>([])
  const [facebookPageState, setFacebookPageState] = useState<string | null>(null)
  const [selectingPage, setSelectingPage] = useState(false)
```

**Step 4: Add URL param detection for Facebook page selection (after the loadAccounts effect)**

```typescript
  // Check for Facebook page selection callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const fbPagesState = params.get('fb_pages')
    if (fbPagesState) {
      setFacebookPageState(fbPagesState)
      // Clean URL
      const url = new URL(window.location.href)
      url.searchParams.delete('fb_pages')
      window.history.replaceState({}, '', url.toString())
    }
  }, [])
```

**Step 5: Add handler functions (after handleConnectMastodon, line 109)**

```typescript
  async function handleConnectX() {
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const { authorization_url } = await authorizeX()
      window.location.href = authorization_url
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to start X authorization. Please try again.')
      }
      setSubmitting(false)
    }
  }

  async function handleConnectFacebook() {
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const { authorization_url } = await authorizeFacebook()
      window.location.href = authorization_url
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to start Facebook authorization. Please try again.')
      }
      setSubmitting(false)
    }
  }

  async function handleSelectFacebookPage(pageId: string) {
    if (!facebookPageState) return
    setSelectingPage(true)
    setError(null)
    try {
      const result = await selectFacebookPage(facebookPageState, pageId)
      setFacebookPageState(null)
      setFacebookPages([])
      setSuccess(`Connected Facebook Page: ${result.account_name}`)
      await loadAccounts()
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to connect Facebook Page. Please try again.')
      }
    } finally {
      setSelectingPage(false)
    }
  }
```

**Step 6: Update localBusy (line 44)**

```typescript
  const localBusy = submitting || deleting || selectingPage
```

**Step 7: Add X and Facebook connect buttons to the JSX**

After the Mastodon connect section (line 336), before `</div>` on line 337, add:

```tsx
            {/* X connect */}
            {connectingPlatform === 'x' ? (
              <div className="p-4 bg-paper-warm border border-border rounded-lg space-y-3">
                <p className="text-xs text-muted">
                  You will be redirected to X to authorize AgBlogger.
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => void handleConnectX()}
                    disabled={allBusy}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-accent text-white rounded-lg
                             hover:bg-accent-light disabled:opacity-50 transition-colors"
                  >
                    <Plus size={14} />
                    {submitting ? 'Connecting...' : 'Connect'}
                  </button>
                  <button
                    onClick={() => setConnectingPlatform(null)}
                    disabled={allBusy}
                    className="px-4 py-2 text-sm font-medium border border-border rounded-lg
                             hover:bg-paper-warm disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => {
                  setConnectingPlatform('x')
                  setError(null)
                  setSuccess(null)
                }}
                disabled={allBusy}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                         border border-border rounded-lg hover:bg-paper-warm
                         disabled:opacity-50 transition-colors"
              >
                <PlatformIcon platform="x" size={14} />
                Connect X
              </button>
            )}

            {/* Facebook connect */}
            {connectingPlatform === 'facebook' ? (
              <div className="p-4 bg-paper-warm border border-border rounded-lg space-y-3">
                <p className="text-xs text-muted">
                  You will be redirected to Facebook to authorize AgBlogger and select a Page.
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => void handleConnectFacebook()}
                    disabled={allBusy}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-accent text-white rounded-lg
                             hover:bg-accent-light disabled:opacity-50 transition-colors"
                  >
                    <Plus size={14} />
                    {submitting ? 'Connecting...' : 'Connect'}
                  </button>
                  <button
                    onClick={() => setConnectingPlatform(null)}
                    disabled={allBusy}
                    className="px-4 py-2 text-sm font-medium border border-border rounded-lg
                             hover:bg-paper-warm disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => {
                  setConnectingPlatform('facebook')
                  setError(null)
                  setSuccess(null)
                }}
                disabled={allBusy}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                         border border-border rounded-lg hover:bg-paper-warm
                         disabled:opacity-50 transition-colors"
              >
                <PlatformIcon platform="facebook" size={14} />
                Connect Facebook
              </button>
            )}
```

**Step 8: Add Facebook page picker (after the connect buttons, before `</>` closing)**

If `facebookPageState` is set, show a page picker instead of the normal connect buttons:

```tsx
          {/* Facebook page selection overlay */}
          {facebookPageState !== null && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
              <p className="text-sm font-medium text-ink">Select a Facebook Page</p>
              <p className="text-xs text-muted">
                Choose which Page AgBlogger should post to:
              </p>
              <div className="space-y-2">
                {facebookPages.map((page) => (
                  <button
                    key={page.id}
                    onClick={() => void handleSelectFacebookPage(page.id)}
                    disabled={selectingPage}
                    className="w-full text-left px-4 py-3 border border-border rounded-lg
                             hover:bg-paper-warm disabled:opacity-50 transition-colors"
                  >
                    <span className="text-sm font-medium text-ink">{page.name}</span>
                  </button>
                ))}
              </div>
              <button
                onClick={() => {
                  setFacebookPageState(null)
                  setFacebookPages([])
                }}
                disabled={selectingPage}
                className="px-4 py-2 text-sm font-medium border border-border rounded-lg
                         hover:bg-paper-warm disabled:opacity-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
```

**Step 2 (frontend tests): Run frontend static checks**

Run: `cd frontend && npx eslint src/components/crosspost/SocialAccountsPanel.tsx`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/crosspost/SocialAccountsPanel.tsx
git commit -m "feat: add X and Facebook connect UI to SocialAccountsPanel"
```

---

### Task 13: Update ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md`

Update the following sections:

1. **Cross-Posting > Platforms**: Add X and Facebook entries
2. **Cross-Posting > Cross-Posting UI > Admin page**: Mention X and Facebook connect buttons
3. **API Routes table**: Note that crosspost router now includes X and Facebook OAuth endpoints

**Step 1: Make the updates**

In the Platforms section, add:

```markdown
- **X (Twitter)** — OAuth 2.0 with PKCE. Posts text tweets via X API v2 (`POST /2/tweets`). 280-character limit. Token refresh on 401.
- **Facebook** — OAuth 2.0 for Facebook Pages. Posts to Pages via Graph API v22.0 (`POST /{page-id}/feed`). Page Access Tokens are non-expiring. Multi-page selection supported.
```

Update character limits section if present.

**Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add X and Facebook cross-posting to architecture docs"
```

---

### Task 14: Run full check gate

**Step 1: Run the full check**

Run: `just check`
Expected: All static checks and tests pass

**Step 2: Fix any issues found**

If any linting, typing, or test failures occur, fix them and re-run.

**Step 3: Final commit if fixes were needed**

```bash
git add -A
git commit -m "fix: resolve static check issues for X/Facebook cross-posting"
```

---

### Task 15: Browser test the full flow

**Step 1: Start the dev server**

Run: `just start`

**Step 2: Test in browser using Playwright MCP**

- Navigate to `/admin` and verify X and Facebook connect buttons appear
- Verify PlatformIcon renders correctly for both platforms
- Test the cross-post dialog shows correct character limits (280 for X)
- Verify the dialog works with the new platforms in the checkbox list

**Step 3: Stop the dev server**

Run: `just stop`

**Step 4: Clean up screenshots**

Remove any `.png` files created during testing.
