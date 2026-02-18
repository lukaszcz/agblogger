"""Bluesky cross-posting implementation using AT Protocol HTTP API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.crosspost.base import CrossPostContent, CrossPostResult

logger = logging.getLogger(__name__)

BSKY_BASE = "https://bsky.social/xrpc"
BSKY_CHAR_LIMIT = 300


def _build_post_text(content: CrossPostContent) -> str:
    """Build the post text, truncated to fit within Bluesky's character limit.

    Format: excerpt + hashtags + link.
    The link is always included at the end.
    """
    link = content.url
    hashtags = " ".join(f"#{label}" for label in content.labels[:5])

    # Reserve space for link and hashtags
    suffix_parts: list[str] = []
    if hashtags:
        suffix_parts.append(hashtags)
    suffix_parts.append(link)
    suffix = "\n\n" + "\n".join(suffix_parts)

    available = BSKY_CHAR_LIMIT - len(suffix)

    excerpt = content.excerpt
    if available <= 3:
        excerpt = excerpt[: max(available, 0)]
    elif len(excerpt) > available:
        excerpt = excerpt[: available - 3].rsplit(" ", maxsplit=1)[0] + "..."

    return excerpt + suffix


def _find_facets(text: str, content: CrossPostContent) -> list[dict[str, Any]]:
    """Build rich text facets for links and hashtags."""
    facets: list[dict[str, Any]] = []

    # Link facet for the URL
    url = content.url
    url_start = text.find(url)
    if url_start >= 0:
        byte_start = len(text[:url_start].encode("utf-8"))
        byte_end = byte_start + len(url.encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        "uri": url,
                    }
                ],
            }
        )

    # Hashtag facets (rfind to match tags in suffix, not in excerpt)
    for label in content.labels[:5]:
        tag_text = f"#{label}"
        tag_start = text.rfind(tag_text)
        if tag_start >= 0:
            byte_start = len(text[:tag_start].encode("utf-8"))
            byte_end = byte_start + len(tag_text.encode("utf-8"))
            facets.append(
                {
                    "index": {"byteStart": byte_start, "byteEnd": byte_end},
                    "features": [
                        {
                            "$type": "app.bsky.richtext.facet#tag",
                            "tag": label,
                        }
                    ],
                }
            )

    return facets


class BlueskyCrossPoster:
    """Cross-poster for Bluesky via AT Protocol."""

    platform: str = "bluesky"

    def __init__(self) -> None:
        self._access_jwt: str | None = None
        self._did: str | None = None
        self._handle: str | None = None

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Authenticate with Bluesky using identifier + password.

        Expected credentials keys: identifier, password.
        """
        identifier = credentials.get("identifier", "")
        password = credentials.get("password", "")
        if not identifier or not password:
            return False

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{BSKY_BASE}/com.atproto.server.createSession",
                    json={"identifier": identifier, "password": password},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning("Bluesky auth failed: %s %s", resp.status_code, resp.text)
                    return False
                data = resp.json()
                self._access_jwt = data["accessJwt"]
                self._did = data["did"]
                self._handle = data.get("handle", identifier)
                return True
            except httpx.HTTPError:
                logger.exception("Bluesky auth HTTP error")
                return False

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a post on Bluesky."""
        if not self._access_jwt or not self._did:
            return CrossPostResult(
                platform_id="",
                url="",
                success=False,
                error="Not authenticated",
            )

        text = _build_post_text(content)
        facets = _find_facets(text, content)

        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        if facets:
            record["facets"] = facets

        payload = {
            "repo": self._did,
            "collection": "app.bsky.feed.post",
            "record": record,
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{BSKY_BASE}/com.atproto.repo.createRecord",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._access_jwt}"},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    return CrossPostResult(
                        platform_id="",
                        url="",
                        success=False,
                        error=f"Bluesky API error: {resp.status_code} {resp.text}",
                    )
                data = resp.json()
                rkey = data.get("uri", "").split("/")[-1]
                post_url = (
                    f"https://bsky.app/profile/{self._handle}/post/{rkey}"
                    if self._handle and rkey
                    else ""
                )
                return CrossPostResult(
                    platform_id=data.get("uri", ""),
                    url=post_url,
                    success=True,
                )
            except httpx.HTTPError as exc:
                logger.exception("Bluesky post HTTP error")
                return CrossPostResult(
                    platform_id="",
                    url="",
                    success=False,
                    error=f"HTTP error: {exc}",
                )

    async def validate_credentials(self) -> bool:
        """Check if current session is still valid."""
        if not self._access_jwt:
            return False
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{BSKY_BASE}/com.atproto.server.getSession",
                    headers={"Authorization": f"Bearer {self._access_jwt}"},
                    timeout=10.0,
                )
                return resp.status_code == 200
            except httpx.HTTPError:
                return False
