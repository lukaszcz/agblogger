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


class XOAuthTokenError(Exception):
    """Raised when X OAuth token exchange fails."""


async def exchange_x_oauth_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    pkce_verifier: str,
) -> dict[str, str]:
    """Exchange authorization code for X OAuth tokens and fetch username.

    Returns dict with keys: access_token, refresh_token, username.
    Raises XOAuthTokenError on failure.
    """
    async with httpx.AsyncClient() as http_client:
        token_resp = await http_client.post(
            "https://api.x.com/2/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": pkce_verifier,
            },
            auth=(client_id, client_secret),
            timeout=15.0,
        )
        if token_resp.status_code != 200:
            msg = f"Token exchange failed: {token_resp.status_code}"
            raise XOAuthTokenError(msg)
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            msg = "Token response missing access_token"
            raise XOAuthTokenError(msg)
        refresh_token = token_data.get("refresh_token", "")

        user_resp = await http_client.get(
            "https://api.x.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )
        if user_resp.status_code != 200:
            msg = f"User fetch failed: {user_resp.status_code}"
            raise XOAuthTokenError(msg)
        user_data = user_resp.json()
        username = user_data.get("data", {}).get("username", "unknown")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "username": username,
    }


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
        """Authenticate with X using OAuth 2.0 tokens."""
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
                    logger.warning("X refresh request failed with status %s", resp.status_code)
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
            except httpx.HTTPError:
                logger.exception("X token refresh error")
                return False
            except KeyError:
                logger.exception("X token refresh error")
                return False

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a tweet on X."""
        if not self._access_token:
            return CrossPostResult(
                platform_id="",
                url="",
                success=False,
                error="Not authenticated",
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
                return CrossPostResult(platform_id=tweet_id, url=tweet_url, success=True)
            except httpx.HTTPError as exc:
                logger.exception("X post HTTP error")
                return CrossPostResult(
                    platform_id="",
                    url="",
                    success=False,
                    error=f"HTTP error: {exc}",
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
        """Return refreshed credentials if tokens were updated."""
        return self._updated_credentials
