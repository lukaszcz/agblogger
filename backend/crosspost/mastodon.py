"""Mastodon cross-posting implementation using Mastodon HTTP API."""

from __future__ import annotations

import logging

import httpx

from backend.crosspost.base import CrossPostContent, CrossPostResult

logger = logging.getLogger(__name__)

MASTODON_CHAR_LIMIT = 500


def _build_status_text(content: CrossPostContent) -> str:
    """Build the status text, truncated to fit within Mastodon's character limit.

    Format: excerpt + hashtags + link.
    """
    link = content.url
    hashtags = " ".join(f"#{label}" for label in content.labels[:10])

    suffix_parts: list[str] = []
    if hashtags:
        suffix_parts.append(hashtags)
    suffix_parts.append(link)
    suffix = "\n\n" + "\n".join(suffix_parts)

    available = MASTODON_CHAR_LIMIT - len(suffix)

    excerpt = content.excerpt
    if len(excerpt) > available:
        excerpt = excerpt[: available - 3].rsplit(" ", maxsplit=1)[0] + "..."

    return excerpt + suffix


class MastodonCrossPoster:
    """Cross-poster for Mastodon-compatible instances."""

    platform: str = "mastodon"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._instance_url: str | None = None
        self._account_id: str | None = None
        self._username: str | None = None

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Authenticate with Mastodon using an access token.

        Expected credentials keys: access_token, instance_url.
        instance_url should be the base URL, e.g. https://mastodon.social
        """
        access_token = credentials.get("access_token", "")
        instance_url = credentials.get("instance_url", "").rstrip("/")
        if not access_token or not instance_url:
            return False

        self._access_token = access_token
        self._instance_url = instance_url

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{instance_url}/api/v1/accounts/verify_credentials",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Mastodon auth failed: %s %s", resp.status_code, resp.text
                    )
                    self._access_token = None
                    self._instance_url = None
                    return False
                data = resp.json()
                self._account_id = str(data.get("id", ""))
                self._username = data.get("acct", "")
                return True
            except httpx.HTTPError:
                logger.exception("Mastodon auth HTTP error")
                self._access_token = None
                self._instance_url = None
                return False

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a status on Mastodon."""
        if not self._access_token or not self._instance_url:
            return CrossPostResult(
                platform_id="",
                url="",
                success=False,
                error="Not authenticated",
            )

        status_text = _build_status_text(content)

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self._instance_url}/api/v1/statuses",
                    json={"status": status_text},
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=15.0,
                )
                if resp.status_code not in (200, 201):
                    return CrossPostResult(
                        platform_id="",
                        url="",
                        success=False,
                        error=f"Mastodon API error: {resp.status_code} {resp.text}",
                    )
                data = resp.json()
                return CrossPostResult(
                    platform_id=str(data.get("id", "")),
                    url=data.get("url", ""),
                    success=True,
                )
            except httpx.HTTPError as exc:
                logger.exception("Mastodon post HTTP error")
                return CrossPostResult(
                    platform_id="",
                    url="",
                    success=False,
                    error=f"HTTP error: {exc}",
                )

    async def validate_credentials(self) -> bool:
        """Check if current access token is still valid."""
        if not self._access_token or not self._instance_url:
            return False
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self._instance_url}/api/v1/accounts/verify_credentials",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=10.0,
                )
                return resp.status_code == 200
            except httpx.HTTPError:
                return False
