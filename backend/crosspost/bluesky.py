"""Bluesky cross-posting implementation using AT Protocol OAuth + DPoP."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import grapheme
import httpx
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from backend.crosspost.atproto_oauth import create_dpop_proof
from backend.crosspost.base import CrossPostContent, CrossPostResult

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

logger = logging.getLogger(__name__)

BSKY_CHAR_LIMIT = 300

REQUIRED_CREDENTIAL_FIELDS = frozenset({
    "access_token", "did", "handle", "pds_url",
    "dpop_private_key_pem", "dpop_jwk", "dpop_nonce",
    "auth_server_issuer", "token_endpoint",
    "refresh_token", "client_id",
})


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

    available = BSKY_CHAR_LIMIT - grapheme.length(suffix)

    excerpt = content.excerpt
    if available <= 3:
        excerpt = grapheme.slice(excerpt, 0, max(available, 0))
    elif grapheme.length(excerpt) > available:
        truncated = grapheme.slice(excerpt, 0, available - 3)
        # Try to break at a word boundary
        space_pos = truncated.rfind(" ")
        if space_pos > 0:
            truncated = truncated[:space_pos]
        excerpt = truncated + "..."

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
    """Cross-poster for Bluesky via AT Protocol OAuth + DPoP."""

    platform: str = "bluesky"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._did: str | None = None
        self._handle: str | None = None
        self._pds_url: str | None = None
        self._dpop_private_key: EllipticCurvePrivateKey | None = None
        self._dpop_jwk: dict[str, str] | None = None
        self._dpop_nonce: str = ""
        self._auth_server_issuer: str | None = None
        self._token_endpoint: str | None = None
        self._refresh_token: str | None = None
        self._client_id: str | None = None
        self._updated_credentials: dict[str, str] | None = None

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Load OAuth credentials. No network call needed."""
        if not REQUIRED_CREDENTIAL_FIELDS.issubset(credentials):
            return False
        self._access_token = credentials["access_token"]
        self._did = credentials["did"]
        self._handle = credentials["handle"]
        self._pds_url = credentials["pds_url"].rstrip("/")
        self._dpop_private_key = load_pem_private_key(
            credentials["dpop_private_key_pem"].encode(),
            password=None,
        )
        self._dpop_jwk = json.loads(credentials["dpop_jwk"])
        self._dpop_nonce = credentials["dpop_nonce"]
        self._auth_server_issuer = credentials["auth_server_issuer"]
        self._token_endpoint = credentials["token_endpoint"]
        self._refresh_token = credentials["refresh_token"]
        self._client_id = credentials["client_id"]
        return True

    def get_updated_credentials(self) -> dict[str, str] | None:
        """Return updated credentials if tokens were refreshed during post()."""
        return self._updated_credentials

    async def _make_pds_request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to the PDS with DPoP."""
        dpop = create_dpop_proof(
            method=method,
            url=url,
            key=self._dpop_private_key,
            jwk=self._dpop_jwk,
            nonce=self._dpop_nonce,
            access_token=self._access_token,
        )
        headers = {
            "Authorization": f"DPoP {self._access_token}",
            "DPoP": dpop,
        }
        async with httpx.AsyncClient() as client:
            if method == "POST":
                resp = await client.post(url, json=json_body, headers=headers, timeout=15.0)
            else:
                resp = await client.get(url, headers=headers, timeout=15.0)

        new_nonce = resp.headers.get("DPoP-Nonce")
        if new_nonce:
            self._dpop_nonce = new_nonce
        return resp

    async def _try_refresh_tokens(self) -> bool:
        """Attempt to refresh the access token."""
        from backend.crosspost.atproto_oauth import ATProtoOAuthError, refresh_access_token

        try:
            result = await refresh_access_token(
                token_endpoint=self._token_endpoint,
                auth_server_issuer=self._auth_server_issuer,
                refresh_token=self._refresh_token,
                client_id=self._client_id,
                private_key=self._dpop_private_key,
                jwk=self._dpop_jwk,
                dpop_nonce=self._dpop_nonce,
            )
            self._access_token = result["access_token"]
            self._refresh_token = result.get("refresh_token", self._refresh_token)
            self._dpop_nonce = result.get("dpop_nonce", self._dpop_nonce)
            self._updated_credentials = {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "did": self._did,
                "handle": self._handle,
                "pds_url": self._pds_url,
                "dpop_private_key_pem": self._dpop_private_key.private_bytes(
                    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
                ).decode(),
                "dpop_jwk": json.dumps(self._dpop_jwk),
                "dpop_nonce": self._dpop_nonce,
                "auth_server_issuer": self._auth_server_issuer,
                "token_endpoint": self._token_endpoint,
                "client_id": self._client_id,
            }
            return True
        except ATProtoOAuthError:
            logger.exception("Token refresh failed")
            return False

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Create a post on Bluesky using DPoP-bound OAuth tokens."""
        if not self._access_token or not self._did:
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

        url = f"{self._pds_url}/xrpc/com.atproto.repo.createRecord"
        try:
            resp = await self._make_pds_request("POST", url, json_body=payload)

            if resp.status_code == 401 and self._refresh_token:
                refreshed = await self._try_refresh_tokens()
                if refreshed:
                    resp = await self._make_pds_request("POST", url, json_body=payload)

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
        """Check if current session is still valid via DPoP-bound request."""
        if not self._access_token or not self._pds_url:
            return False
        try:
            url = f"{self._pds_url}/xrpc/com.atproto.server.getSession"
            resp = await self._make_pds_request("GET", url)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
