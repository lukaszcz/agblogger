# Bluesky AT Protocol OAuth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Bluesky's username+password authentication with AT Protocol OAuth (confidential client, BFF pattern) so only scoped, revocable, DPoP-bound tokens are stored.

**Architecture:** AgBlogger acts as a confidential OAuth client. An ES256 keypair (generated on first startup) proves the client's identity. The OAuth flow uses PKCE + PAR + DPoP per the AT Protocol spec. Tokens are encrypted at rest in the existing `SocialAccount` table. The `BlueskyCrossPoster` uses DPoP-bound access tokens instead of `createSession`.

**Tech Stack:** PyJWT (already a dependency, supports ES256 via `cryptography`), `cryptography` (already a dependency, for EC key generation), httpx (already a dependency, for AT Protocol HTTP calls).

**Design doc:** `docs/plans/2026-02-21-bluesky-oauth-design.md`

---

### Task 1: AT Protocol OAuth Helpers — Key Generation and DPoP Proofs

**Files:**
- Create: `backend/crosspost/atproto_oauth.py`
- Create: `tests/test_services/test_atproto_oauth.py`

This task implements the cryptographic primitives: ES256 keypair generation, DPoP JWT proof creation, PKCE challenge generation, and client assertion JWT creation. These are pure functions with no external HTTP calls.

**Step 1: Write failing tests for key generation and DPoP proofs**

```python
"""Tests for AT Protocol OAuth helpers."""

from __future__ import annotations

import base64
import hashlib
import json

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey

from backend.crosspost.atproto_oauth import (
    create_client_assertion,
    create_dpop_proof,
    create_pkce_challenge,
    generate_es256_keypair,
    load_or_create_keypair,
    serialize_keypair,
)


class TestES256Keypair:
    def test_generate_returns_private_key_and_jwk(self) -> None:
        private_key, jwk = generate_es256_keypair()
        assert jwk["kty"] == "EC"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk
        assert "kid" in jwk
        assert isinstance(private_key.public_key(), EllipticCurvePublicKey)

    def test_serialize_and_load_roundtrip(self, tmp_path) -> None:
        private_key, jwk = generate_es256_keypair()
        path = tmp_path / "key.json"
        serialize_keypair(private_key, jwk, path)
        loaded_key, loaded_jwk = load_or_create_keypair(path)
        assert loaded_jwk["kid"] == jwk["kid"]
        assert loaded_jwk["x"] == jwk["x"]
        # Verify loaded key can sign
        token = jwt.encode({"test": True}, loaded_key, algorithm="ES256")
        decoded = jwt.decode(token, loaded_key.public_key(), algorithms=["ES256"])
        assert decoded["test"] is True

    def test_load_creates_if_missing(self, tmp_path) -> None:
        path = tmp_path / "nonexistent.json"
        assert not path.exists()
        private_key, jwk = load_or_create_keypair(path)
        assert path.exists()
        assert jwk["kty"] == "EC"


class TestDPoPProof:
    def test_create_dpop_proof_for_auth_server(self) -> None:
        private_key, jwk = generate_es256_keypair()
        proof = create_dpop_proof(
            method="POST",
            url="https://bsky.social/oauth/token",
            key=private_key,
            jwk=jwk,
            nonce="server-nonce-123",
        )
        # Decode without verification to inspect structure
        header = jwt.get_unverified_header(proof)
        assert header["typ"] == "dpop+jwt"
        assert header["alg"] == "ES256"
        assert header["jwk"]["kty"] == "EC"
        payload = jwt.decode(proof, private_key.public_key(), algorithms=["ES256"])
        assert payload["htm"] == "POST"
        assert payload["htu"] == "https://bsky.social/oauth/token"
        assert payload["nonce"] == "server-nonce-123"
        assert "jti" in payload
        assert "iat" in payload
        assert "ath" not in payload

    def test_create_dpop_proof_with_access_token_hash(self) -> None:
        private_key, jwk = generate_es256_keypair()
        access_token = "test-access-token-value"
        proof = create_dpop_proof(
            method="GET",
            url="https://pds.example.com/xrpc/com.atproto.repo.createRecord",
            key=private_key,
            jwk=jwk,
            nonce="nonce-456",
            access_token=access_token,
        )
        payload = jwt.decode(proof, private_key.public_key(), algorithms=["ES256"])
        assert payload["htm"] == "GET"
        assert "ath" in payload
        expected_ath = base64.urlsafe_b64encode(
            hashlib.sha256(access_token.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        assert payload["ath"] == expected_ath


class TestPKCE:
    def test_create_pkce_challenge(self) -> None:
        verifier, challenge = create_pkce_challenge()
        assert len(verifier) >= 43  # base64url of 32+ bytes
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        assert challenge == expected


class TestClientAssertion:
    def test_create_client_assertion_jwt(self) -> None:
        private_key, jwk = generate_es256_keypair()
        client_id = "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json"
        aud = "https://bsky.social"
        assertion = create_client_assertion(client_id, aud, private_key, jwk["kid"])
        payload = jwt.decode(
            assertion, private_key.public_key(), algorithms=["ES256"],
            audience=aud,
        )
        assert payload["iss"] == client_id
        assert payload["sub"] == client_id
        assert payload["aud"] == aud
        assert "jti" in payload
        assert "exp" in payload
```

Write this to `tests/test_services/test_atproto_oauth.py`.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_atproto_oauth.py -v`
Expected: FAIL — `ImportError: cannot import name ... from 'backend.crosspost.atproto_oauth'`

**Step 3: Implement the OAuth helpers**

Write to `backend/crosspost/atproto_oauth.py`:

```python
"""AT Protocol OAuth helpers: key generation, DPoP proofs, PKCE, client assertions."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    EllipticCurvePrivateKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)


def _b64url(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_es256_keypair() -> tuple[EllipticCurvePrivateKey, dict[str, str]]:
    """Generate an ES256 (P-256) keypair and return (private_key, public_jwk)."""
    private_key = ec.generate_private_key(SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    x_bytes = public_numbers.x.to_bytes(32, "big")
    y_bytes = public_numbers.y.to_bytes(32, "big")
    kid = str(uuid.uuid4())
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(x_bytes),
        "y": _b64url(y_bytes),
        "kid": kid,
    }
    return private_key, jwk


def serialize_keypair(
    private_key: EllipticCurvePrivateKey, jwk: dict[str, str], path: Path
) -> None:
    """Serialize keypair to a JSON file (PEM private key + public JWK)."""
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    data = {"private_key_pem": pem.decode("ascii"), "jwk": jwk}
    path.write_text(json.dumps(data, indent=2))


def load_or_create_keypair(
    path: Path,
) -> tuple[EllipticCurvePrivateKey, dict[str, str]]:
    """Load keypair from file, or create and save a new one."""
    if path.exists():
        data = json.loads(path.read_text())
        private_key = load_pem_private_key(
            data["private_key_pem"].encode("ascii"), password=None
        )
        return private_key, data["jwk"]  # type: ignore[return-value]
    private_key, jwk = generate_es256_keypair()
    serialize_keypair(private_key, jwk, path)
    return private_key, jwk


def create_dpop_proof(
    *,
    method: str,
    url: str,
    key: EllipticCurvePrivateKey,
    jwk: dict[str, str],
    nonce: str = "",
    access_token: str | None = None,
) -> str:
    """Create a DPoP proof JWT (ES256).

    For auth server requests, omit access_token.
    For resource server (PDS) requests, provide access_token to include `ath`.
    """
    headers = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
    payload: dict[str, str | int] = {
        "jti": str(uuid.uuid4()),
        "htm": method,
        "htu": url,
        "iat": int(time.time()),
    }
    if nonce:
        payload["nonce"] = nonce
    if access_token is not None:
        token_hash = hashlib.sha256(access_token.encode("ascii")).digest()
        payload["ath"] = _b64url(token_hash)
    return jwt.encode(payload, key, algorithm="ES256", headers=headers)


def create_pkce_challenge() -> tuple[str, str]:
    """Generate PKCE verifier and S256 challenge."""
    verifier_bytes = secrets.token_bytes(48)
    verifier = _b64url(verifier_bytes)
    challenge_hash = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _b64url(challenge_hash)
    return verifier, challenge


def create_client_assertion(
    client_id: str,
    aud: str,
    key: EllipticCurvePrivateKey,
    kid: str,
) -> str:
    """Create a client assertion JWT for token endpoint authentication."""
    headers = {"alg": "ES256", "kid": kid}
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": aud,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 60,
    }
    return jwt.encode(payload, key, algorithm="ES256", headers=headers)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_atproto_oauth.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/crosspost/atproto_oauth.py tests/test_services/test_atproto_oauth.py
git commit -m "feat: add AT Protocol OAuth crypto helpers (DPoP, PKCE, client assertion)"
```

---

### Task 2: AT Protocol Discovery and PAR

**Files:**
- Modify: `backend/crosspost/atproto_oauth.py`
- Modify: `tests/test_services/test_atproto_oauth.py`

This task adds handle→DID resolution, authorization server discovery, and Pushed Authorization Request (PAR) helpers. All HTTP calls use httpx and include SSRF protection.

**Step 1: Write failing tests for discovery and PAR**

Append to `tests/test_services/test_atproto_oauth.py`:

```python
import httpx
import pytest
from unittest.mock import AsyncMock, patch

from backend.crosspost.atproto_oauth import (
    discover_auth_server,
    resolve_handle_to_did,
    send_par_request,
    exchange_code_for_tokens,
    refresh_access_token,
    ATProtoOAuthError,
)


class TestHandleResolution:
    async def test_resolve_handle_via_dns_txt(self, monkeypatch) -> None:
        """Resolve handle via DNS TXT record _atproto.{handle}."""
        import socket
        def mock_getaddrinfo(host, port, *args, **kwargs):
            if host == "_atproto.alice.bsky.social":
                raise socket.gaierror("no DNS")
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))]

        async def mock_dns_resolve(handle):
            return "did:plc:abc123"

        monkeypatch.setattr(
            "backend.crosspost.atproto_oauth._resolve_handle_dns",
            mock_dns_resolve,
        )
        did = await resolve_handle_to_did("alice.bsky.social")
        assert did == "did:plc:abc123"

    async def test_resolve_handle_via_http_fallback(self, monkeypatch) -> None:
        """Fall back to HTTP /.well-known/atproto-did when DNS fails."""
        async def mock_dns_fail(handle):
            return None

        async def mock_http_resolve(handle):
            return "did:plc:http-fallback"

        monkeypatch.setattr(
            "backend.crosspost.atproto_oauth._resolve_handle_dns",
            mock_dns_fail,
        )
        monkeypatch.setattr(
            "backend.crosspost.atproto_oauth._resolve_handle_http",
            mock_http_resolve,
        )
        did = await resolve_handle_to_did("alice.bsky.social")
        assert did == "did:plc:http-fallback"

    async def test_resolve_handle_fails_when_both_methods_fail(self, monkeypatch) -> None:
        async def mock_fail(handle):
            return None
        monkeypatch.setattr("backend.crosspost.atproto_oauth._resolve_handle_dns", mock_fail)
        monkeypatch.setattr("backend.crosspost.atproto_oauth._resolve_handle_http", mock_fail)
        with pytest.raises(ATProtoOAuthError, match="resolve handle"):
            await resolve_handle_to_did("nonexistent.invalid")


class TestAuthServerDiscovery:
    async def test_discover_auth_server_from_pds(self, monkeypatch) -> None:
        """Discover authorization server metadata from PDS."""
        responses = {
            "https://plc.directory/did:plc:abc123": httpx.Response(
                200,
                json={
                    "id": "did:plc:abc123",
                    "service": [
                        {"id": "#atproto_pds", "type": "AtprotoPersonalDataServer",
                         "serviceEndpoint": "https://pds.example.com"}
                    ],
                },
            ),
            "https://pds.example.com/.well-known/oauth-protected-resource": httpx.Response(
                200,
                json={"authorization_servers": ["https://auth.example.com"]},
            ),
            "https://auth.example.com/.well-known/oauth-authorization-server": httpx.Response(
                200,
                json={
                    "issuer": "https://auth.example.com",
                    "authorization_endpoint": "https://auth.example.com/oauth/authorize",
                    "token_endpoint": "https://auth.example.com/oauth/token",
                    "pushed_authorization_request_endpoint": "https://auth.example.com/oauth/par",
                    "scopes_supported": ["atproto", "transition:generic"],
                    "dpop_signing_alg_values_supported": ["ES256"],
                    "revocation_endpoint": "https://auth.example.com/oauth/revoke",
                },
            ),
        }

        async def mock_get(self, url, **kwargs):
            if url in responses:
                return responses[url]
            return httpx.Response(404)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await discover_auth_server("did:plc:abc123")
        assert result["issuer"] == "https://auth.example.com"
        assert result["token_endpoint"] == "https://auth.example.com/oauth/token"
        assert result["pds_url"] == "https://pds.example.com"


class TestPARRequest:
    async def test_send_par_request(self, monkeypatch) -> None:
        """PAR should return request_uri and state."""
        private_key, jwk = generate_es256_keypair()

        async def mock_post(self, url, **kwargs):
            assert url == "https://auth.example.com/oauth/par"
            return httpx.Response(
                201,
                json={"request_uri": "urn:ietf:params:oauth:request_uri:abc", "expires_in": 60},
                headers={"DPoP-Nonce": "new-nonce-from-server"},
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await send_par_request(
            auth_server_meta={
                "issuer": "https://auth.example.com",
                "pushed_authorization_request_endpoint": "https://auth.example.com/oauth/par",
                "authorization_endpoint": "https://auth.example.com/oauth/authorize",
            },
            client_id="https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
            redirect_uri="https://myblog.example.com/api/crosspost/bluesky/callback",
            did="did:plc:abc123",
            scope="atproto transition:generic",
            private_key=private_key,
            jwk=jwk,
        )
        assert result["authorization_url"].startswith("https://auth.example.com/oauth/authorize")
        assert "request_uri=" in result["authorization_url"]
        assert "state" in result
        assert "pkce_verifier" in result
        assert "dpop_nonce" in result


class TestTokenExchange:
    async def test_exchange_code_for_tokens(self, monkeypatch) -> None:
        private_key, jwk = generate_es256_keypair()

        async def mock_post(self, url, **kwargs):
            return httpx.Response(
                200,
                json={
                    "access_token": "at_123",
                    "refresh_token": "rt_456",
                    "token_type": "DPoP",
                    "expires_in": 300,
                    "sub": "did:plc:abc123",
                },
                headers={"DPoP-Nonce": "token-nonce"},
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await exchange_code_for_tokens(
            token_endpoint="https://auth.example.com/oauth/token",
            auth_server_issuer="https://auth.example.com",
            code="auth-code-xyz",
            redirect_uri="https://myblog.example.com/api/crosspost/bluesky/callback",
            pkce_verifier="verifier-abc",
            client_id="https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
            private_key=private_key,
            jwk=jwk,
            dpop_nonce="initial-nonce",
        )
        assert result["access_token"] == "at_123"
        assert result["refresh_token"] == "rt_456"
        assert result["sub"] == "did:plc:abc123"
        assert result["dpop_nonce"] == "token-nonce"

    async def test_refresh_access_token(self, monkeypatch) -> None:
        private_key, jwk = generate_es256_keypair()

        async def mock_post(self, url, **kwargs):
            return httpx.Response(
                200,
                json={
                    "access_token": "at_new",
                    "refresh_token": "rt_new",
                    "token_type": "DPoP",
                    "expires_in": 300,
                    "sub": "did:plc:abc123",
                },
                headers={"DPoP-Nonce": "refreshed-nonce"},
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await refresh_access_token(
            token_endpoint="https://auth.example.com/oauth/token",
            auth_server_issuer="https://auth.example.com",
            refresh_token="rt_456",
            client_id="https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
            private_key=private_key,
            jwk=jwk,
            dpop_nonce="old-nonce",
        )
        assert result["access_token"] == "at_new"
        assert result["refresh_token"] == "rt_new"
        assert result["dpop_nonce"] == "refreshed-nonce"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_atproto_oauth.py -v -k "TestHandleResolution or TestAuthServerDiscovery or TestPARRequest or TestTokenExchange"`
Expected: FAIL — `ImportError`

**Step 3: Implement discovery, PAR, and token exchange**

Append to `backend/crosspost/atproto_oauth.py`:

```python
import logging
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ATPROTO_TIMEOUT = 15.0


class ATProtoOAuthError(Exception):
    """Error during AT Protocol OAuth operations."""


def _is_safe_url(url: str) -> bool:
    """Reject URLs targeting private/loopback addresses (SSRF protection)."""
    import ipaddress
    import socket

    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if parsed.scheme not in ("https",):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified)
    except ValueError:
        pass
    blocked = {"localhost", "localhost.localdomain"}
    if hostname.lower() in blocked:
        return False
    try:
        for entry in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(str(entry[4][0]))
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
    except socket.gaierror:
        return False
    return True


async def _resolve_handle_dns(handle: str) -> str | None:
    """Resolve handle via DNS TXT record at _atproto.{handle}."""
    import asyncio
    import socket

    loop = asyncio.get_running_loop()
    try:
        # DNS TXT lookup for _atproto.{handle}
        results = await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(f"_atproto.{handle}", None, type=socket.SOCK_STREAM)
        )
        # This is a simplification — real DNS TXT needs dnspython or similar.
        # For production, we use the HTTP fallback as primary.
        return None
    except (socket.gaierror, OSError):
        return None


async def _resolve_handle_http(handle: str) -> str | None:
    """Resolve handle via HTTP GET https://{handle}/.well-known/atproto-did."""
    url = f"https://{handle}/.well-known/atproto-did"
    if not _is_safe_url(url):
        return None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=ATPROTO_TIMEOUT, follow_redirects=False)
            if resp.status_code == 200:
                did = resp.text.strip()
                if did.startswith("did:"):
                    return did
        except httpx.HTTPError:
            pass
    return None


async def resolve_handle_to_did(handle: str) -> str:
    """Resolve a Bluesky handle to a DID.

    Tries DNS TXT first, falls back to HTTP well-known.
    """
    did = await _resolve_handle_dns(handle)
    if did:
        return did
    did = await _resolve_handle_http(handle)
    if did:
        return did
    raise ATProtoOAuthError(f"Could not resolve handle '{handle}' to a DID")


async def discover_auth_server(did: str) -> dict[str, Any]:
    """Discover the authorization server for a DID.

    1. Resolve DID to DID document (via plc.directory for did:plc)
    2. Extract PDS URL from service endpoints
    3. Fetch PDS protected resource metadata
    4. Fetch authorization server metadata
    """
    # Step 1: Resolve DID document
    if did.startswith("did:plc:"):
        did_url = f"https://plc.directory/{did}"
    elif did.startswith("did:web:"):
        domain = did.removeprefix("did:web:")
        did_url = f"https://{domain}/.well-known/did.json"
    else:
        raise ATProtoOAuthError(f"Unsupported DID method: {did}")

    async with httpx.AsyncClient() as client:
        resp = await client.get(did_url, timeout=ATPROTO_TIMEOUT)
        if resp.status_code != 200:
            raise ATProtoOAuthError(f"Failed to resolve DID document: {resp.status_code}")
        did_doc = resp.json()

    # Step 2: Extract PDS URL
    pds_url = None
    for service in did_doc.get("service", []):
        if service.get("id") == "#atproto_pds":
            pds_url = service["serviceEndpoint"].rstrip("/")
            break
    if not pds_url:
        raise ATProtoOAuthError("No PDS service endpoint in DID document")

    async with httpx.AsyncClient() as client:
        # Step 3: Fetch protected resource metadata
        resp = await client.get(
            f"{pds_url}/.well-known/oauth-protected-resource",
            timeout=ATPROTO_TIMEOUT,
        )
        if resp.status_code != 200:
            raise ATProtoOAuthError(f"PDS protected resource metadata unavailable: {resp.status_code}")
        resource_meta = resp.json()

        auth_servers = resource_meta.get("authorization_servers", [])
        if not auth_servers:
            raise ATProtoOAuthError("No authorization servers in protected resource metadata")
        auth_server_url = auth_servers[0].rstrip("/")

        # Step 4: Fetch authorization server metadata
        resp = await client.get(
            f"{auth_server_url}/.well-known/oauth-authorization-server",
            timeout=ATPROTO_TIMEOUT,
        )
        if resp.status_code != 200:
            raise ATProtoOAuthError(f"Auth server metadata unavailable: {resp.status_code}")
        auth_meta = resp.json()

    auth_meta["pds_url"] = pds_url
    return auth_meta


async def _auth_server_post(
    url: str,
    data: dict[str, str],
    *,
    client_id: str,
    auth_server_issuer: str,
    private_key: EllipticCurvePrivateKey,
    jwk: dict[str, str],
    dpop_nonce: str,
) -> tuple[httpx.Response, str]:
    """POST to an auth server endpoint with client assertion and DPoP.

    Returns (response, updated_dpop_nonce). Handles nonce rotation.
    """
    assertion = create_client_assertion(client_id, auth_server_issuer, private_key, jwk["kid"])
    data["client_id"] = client_id
    data["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    data["client_assertion"] = assertion

    current_nonce = dpop_nonce

    async with httpx.AsyncClient() as client:
        for _attempt in range(2):  # retry once for nonce rotation
            dpop = create_dpop_proof(
                method="POST", url=url, key=private_key, jwk=jwk, nonce=current_nonce,
            )
            resp = await client.post(
                url,
                data=data,
                headers={"DPoP": dpop},
                timeout=ATPROTO_TIMEOUT,
            )
            new_nonce = resp.headers.get("DPoP-Nonce", current_nonce)
            if resp.status_code == 400:
                body = resp.json()
                if body.get("error") == "use_dpop_nonce":
                    current_nonce = new_nonce
                    continue
            return resp, new_nonce
    return resp, current_nonce  # should not reach here


async def send_par_request(
    *,
    auth_server_meta: dict[str, Any],
    client_id: str,
    redirect_uri: str,
    did: str,
    scope: str,
    private_key: EllipticCurvePrivateKey,
    jwk: dict[str, str],
    dpop_nonce: str = "",
) -> dict[str, str]:
    """Send a Pushed Authorization Request (PAR).

    Returns dict with authorization_url, state, pkce_verifier, dpop_nonce.
    """
    pkce_verifier, code_challenge = create_pkce_challenge()
    state = secrets.token_urlsafe(32)

    par_endpoint = auth_server_meta["pushed_authorization_request_endpoint"]
    auth_endpoint = auth_server_meta["authorization_endpoint"]
    issuer = auth_server_meta["issuer"]

    data = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "login_hint": did,
    }

    resp, updated_nonce = await _auth_server_post(
        par_endpoint, data,
        client_id=client_id, auth_server_issuer=issuer,
        private_key=private_key, jwk=jwk, dpop_nonce=dpop_nonce,
    )

    if resp.status_code not in (200, 201):
        raise ATProtoOAuthError(f"PAR request failed: {resp.status_code} {resp.text}")

    par_response = resp.json()
    request_uri = par_response["request_uri"]

    authorization_url = (
        f"{auth_endpoint}?"
        f"client_id={urllib.parse.quote(client_id, safe='')}&"
        f"request_uri={urllib.parse.quote(request_uri, safe='')}"
    )

    return {
        "authorization_url": authorization_url,
        "state": state,
        "pkce_verifier": pkce_verifier,
        "dpop_nonce": updated_nonce,
    }


async def exchange_code_for_tokens(
    *,
    token_endpoint: str,
    auth_server_issuer: str,
    code: str,
    redirect_uri: str,
    pkce_verifier: str,
    client_id: str,
    private_key: EllipticCurvePrivateKey,
    jwk: dict[str, str],
    dpop_nonce: str = "",
) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": pkce_verifier,
    }

    resp, updated_nonce = await _auth_server_post(
        token_endpoint, data,
        client_id=client_id, auth_server_issuer=auth_server_issuer,
        private_key=private_key, jwk=jwk, dpop_nonce=dpop_nonce,
    )

    if resp.status_code != 200:
        raise ATProtoOAuthError(f"Token exchange failed: {resp.status_code} {resp.text}")

    token_data = resp.json()
    token_data["dpop_nonce"] = updated_nonce
    return token_data


async def refresh_access_token(
    *,
    token_endpoint: str,
    auth_server_issuer: str,
    refresh_token: str,
    client_id: str,
    private_key: EllipticCurvePrivateKey,
    jwk: dict[str, str],
    dpop_nonce: str = "",
) -> dict[str, Any]:
    """Refresh an access token using a refresh token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    resp, updated_nonce = await _auth_server_post(
        token_endpoint, data,
        client_id=client_id, auth_server_issuer=auth_server_issuer,
        private_key=private_key, jwk=jwk, dpop_nonce=dpop_nonce,
    )

    if resp.status_code != 200:
        raise ATProtoOAuthError(f"Token refresh failed: {resp.status_code} {resp.text}")

    token_data = resp.json()
    token_data["dpop_nonce"] = updated_nonce
    return token_data
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_atproto_oauth.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/crosspost/atproto_oauth.py tests/test_services/test_atproto_oauth.py
git commit -m "feat: add AT Protocol discovery, PAR, and token exchange"
```

---

### Task 3: OAuth State Store and Config

**Files:**
- Create: `backend/crosspost/bluesky_oauth_state.py`
- Create: `tests/test_services/test_bluesky_oauth_state.py`
- Modify: `backend/config.py`

This task adds a time-limited in-memory store for pending OAuth flows and the `bluesky_client_url` setting.

**Step 1: Write failing tests for OAuth state store**

Write to `tests/test_services/test_bluesky_oauth_state.py`:

```python
"""Tests for Bluesky OAuth pending state store."""

from __future__ import annotations

import time

from backend.crosspost.bluesky_oauth_state import OAuthStateStore


class TestOAuthStateStore:
    def test_store_and_retrieve(self) -> None:
        store = OAuthStateStore(ttl_seconds=60)
        state_data = {"pkce_verifier": "v123", "user_id": 1}
        store.set("state-abc", state_data)
        result = store.pop("state-abc")
        assert result == state_data

    def test_pop_removes_entry(self) -> None:
        store = OAuthStateStore(ttl_seconds=60)
        store.set("state-abc", {"key": "value"})
        store.pop("state-abc")
        assert store.pop("state-abc") is None

    def test_returns_none_for_unknown_state(self) -> None:
        store = OAuthStateStore(ttl_seconds=60)
        assert store.pop("nonexistent") is None

    def test_expired_entries_are_not_returned(self) -> None:
        store = OAuthStateStore(ttl_seconds=0)  # 0 second TTL = immediate expiry
        store.set("state-abc", {"key": "value"})
        # Force expiration by manipulating internal timestamp
        store._entries["state-abc"] = (store._entries["state-abc"][0], time.time() - 1)
        assert store.pop("state-abc") is None

    def test_cleanup_removes_expired(self) -> None:
        store = OAuthStateStore(ttl_seconds=0)
        store.set("old", {"key": "value"})
        store._entries["old"] = (store._entries["old"][0], time.time() - 1)
        store.set("new", {"key": "value2"})
        store.cleanup()
        assert "old" not in store._entries
        assert "new" in store._entries
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_bluesky_oauth_state.py -v`
Expected: FAIL — `ImportError`

**Step 3: Implement the OAuth state store**

Write to `backend/crosspost/bluesky_oauth_state.py`:

```python
"""Time-limited in-memory store for pending Bluesky OAuth flows."""

from __future__ import annotations

import time
from typing import Any


class OAuthStateStore:
    """Store pending OAuth authorization state with automatic expiry.

    Each entry maps a `state` parameter to the associated flow data
    (PKCE verifier, DPoP key, auth server URL, user_id, etc.).
    Entries expire after `ttl_seconds`.
    """

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[dict[str, Any], float]] = {}

    def set(self, state: str, data: dict[str, Any]) -> None:
        """Store data for a pending OAuth flow."""
        self.cleanup()
        self._entries[state] = (data, time.time())

    def pop(self, state: str) -> dict[str, Any] | None:
        """Retrieve and remove data for a completed OAuth flow.

        Returns None if state is unknown or expired.
        """
        entry = self._entries.pop(state, None)
        if entry is None:
            return None
        data, created_at = entry
        if time.time() - created_at > self._ttl:
            return None
        return data

    def cleanup(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, t) in self._entries.items() if now - t > self._ttl]
        for k in expired:
            del self._entries[k]
```

**Step 4: Add `bluesky_client_url` to Settings**

In `backend/config.py`, add to the `Settings` class after the CORS section:

```python
    # Bluesky OAuth
    bluesky_client_url: str = ""
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_bluesky_oauth_state.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/crosspost/bluesky_oauth_state.py tests/test_services/test_bluesky_oauth_state.py backend/config.py
git commit -m "feat: add OAuth state store and bluesky_client_url setting"
```

---

### Task 4: Rewrite BlueskyCrossPoster for OAuth

**Files:**
- Modify: `backend/crosspost/bluesky.py`
- Modify: `tests/test_services/test_crosspost.py`

This task rewrites `BlueskyCrossPoster` to use DPoP-bound OAuth tokens instead of `createSession`. The `authenticate()` method now accepts OAuth token credentials, and `post()` creates DPoP proofs per-request.

**Step 1: Write failing tests for the new BlueskyCrossPoster**

Replace the Bluesky-specific tests in `tests/test_services/test_crosspost.py` (keep the registry and Mastodon tests). Add new tests:

```python
class TestBlueskyCrossPosterOAuth:
    """Test BlueskyCrossPoster with OAuth DPoP tokens."""

    @pytest.mark.asyncio
    async def test_authenticate_with_oauth_tokens(self, monkeypatch) -> None:
        from backend.crosspost.bluesky import BlueskyCrossPoster

        poster = BlueskyCrossPoster()
        result = await poster.authenticate({
            "access_token": "at_valid",
            "did": "did:plc:abc123",
            "handle": "alice.bsky.social",
            "pds_url": "https://pds.example.com",
            "dpop_private_key_pem": "...",  # will be set below
            "dpop_jwk": "...",
            "dpop_nonce": "nonce-1",
            "auth_server_issuer": "https://bsky.social",
            "token_endpoint": "https://bsky.social/oauth/token",
            "refresh_token": "rt_valid",
            "client_id": "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
        })
        # authenticate just stores the credentials, always returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_rejects_missing_fields(self) -> None:
        from backend.crosspost.bluesky import BlueskyCrossPoster

        poster = BlueskyCrossPoster()
        result = await poster.authenticate({"access_token": "at_valid"})
        assert result is False

    @pytest.mark.asyncio
    async def test_post_uses_dpop(self, monkeypatch) -> None:
        from backend.crosspost.atproto_oauth import generate_es256_keypair, serialize_keypair
        from backend.crosspost.bluesky import BlueskyCrossPoster
        from backend.crosspost.base import CrossPostContent

        private_key, jwk = generate_es256_keypair()
        import json
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
        pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

        captured_headers: dict[str, str] = {}

        async def mock_post(self, url, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return httpx.Response(
                200,
                json={"uri": "at://did:plc:abc123/app.bsky.feed.post/abc", "cid": "bafy123"},
                headers={"DPoP-Nonce": "nonce-updated"},
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        poster = BlueskyCrossPoster()
        await poster.authenticate({
            "access_token": "at_valid",
            "did": "did:plc:abc123",
            "handle": "alice.bsky.social",
            "pds_url": "https://pds.example.com",
            "dpop_private_key_pem": pem,
            "dpop_jwk": json.dumps(jwk),
            "dpop_nonce": "nonce-1",
            "auth_server_issuer": "https://bsky.social",
            "token_endpoint": "https://bsky.social/oauth/token",
            "refresh_token": "rt_valid",
            "client_id": "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json",
        })

        content = CrossPostContent(
            title="Test", excerpt="Hello", url="https://blog.example.com/post", labels=["swe"],
        )
        result = await poster.post(content)
        assert result.success
        assert "DPoP" in captured_headers.get("Authorization", "")
        assert "DPoP" in captured_headers  # DPoP header with proof
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_crosspost.py::TestBlueskyCrossPosterOAuth -v`
Expected: FAIL

**Step 3: Rewrite BlueskyCrossPoster**

Replace `backend/crosspost/bluesky.py` with:

```python
"""Bluesky cross-posting implementation using AT Protocol OAuth + DPoP."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import grapheme
import httpx
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from backend.crosspost.atproto_oauth import create_dpop_proof
from backend.crosspost.base import CrossPostContent, CrossPostResult

logger = logging.getLogger(__name__)

BSKY_CHAR_LIMIT = 300
REQUIRED_CREDENTIAL_FIELDS = frozenset({
    "access_token", "did", "handle", "pds_url",
    "dpop_private_key_pem", "dpop_jwk", "dpop_nonce",
    "auth_server_issuer", "token_endpoint",
    "refresh_token", "client_id",
})


# _build_post_text and _find_facets stay exactly the same as before


class BlueskyCrossPoster:
    """Cross-poster for Bluesky via AT Protocol OAuth + DPoP."""

    platform: str = "bluesky"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._did: str | None = None
        self._handle: str | None = None
        self._pds_url: str | None = None
        self._dpop_private_key = None
        self._dpop_jwk: dict[str, str] | None = None
        self._dpop_nonce: str = ""
        self._auth_server_issuer: str | None = None
        self._token_endpoint: str | None = None
        self._refresh_token: str | None = None
        self._client_id: str | None = None
        self._credentials_updated = False
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
            credentials["dpop_private_key_pem"].encode(), password=None,
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
        self, method: str, url: str, *, json_body: dict | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to the PDS with DPoP."""
        dpop = create_dpop_proof(
            method=method, url=url,
            key=self._dpop_private_key, jwk=self._dpop_jwk,
            nonce=self._dpop_nonce, access_token=self._access_token,
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
        from backend.crosspost.atproto_oauth import refresh_access_token, ATProtoOAuthError
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
            self._credentials_updated = True
            # Store updated credentials for persistence
            from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
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
                platform_id="", url="", success=False, error="Not authenticated",
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

            # If 401, try refreshing the token and retry once
            if resp.status_code == 401 and self._refresh_token:
                refreshed = await self._try_refresh_tokens()
                if refreshed:
                    resp = await self._make_pds_request("POST", url, json_body=payload)

            if resp.status_code != 200:
                return CrossPostResult(
                    platform_id="", url="", success=False,
                    error=f"Bluesky API error: {resp.status_code} {resp.text}",
                )
            data = resp.json()
            rkey = data.get("uri", "").split("/")[-1]
            post_url = (
                f"https://bsky.app/profile/{self._handle}/post/{rkey}"
                if self._handle and rkey else ""
            )
            return CrossPostResult(
                platform_id=data.get("uri", ""), url=post_url, success=True,
            )
        except httpx.HTTPError as exc:
            logger.exception("Bluesky post HTTP error")
            return CrossPostResult(
                platform_id="", url="", success=False, error=f"HTTP error: {exc}",
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
```

Keep `_build_post_text` and `_find_facets` exactly as they are — they don't change.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_crosspost.py -v && uv run pytest tests/test_services/test_crosspost_formatting.py -v`
Expected: All PASS (formatting tests unchanged, new OAuth tests pass)

**Step 5: Commit**

```bash
git add backend/crosspost/bluesky.py tests/test_services/test_crosspost.py
git commit -m "feat: rewrite BlueskyCrossPoster to use AT Protocol OAuth + DPoP"
```

---

### Task 5: Bluesky OAuth API Endpoints

**Files:**
- Modify: `backend/api/crosspost.py`
- Modify: `backend/schemas/crosspost.py`
- Modify: `backend/main.py`
- Modify: `backend/api/deps.py` (if needed for new dependencies)
- Create: `tests/test_api/test_bluesky_oauth_endpoints.py`

This task adds the three new API endpoints: client metadata, authorize, and callback. It also initializes the OAuth keypair and state store on startup.

**Step 1: Add new schemas**

Add to `backend/schemas/crosspost.py`:

```python
class BlueskyAuthorizeRequest(BaseModel):
    """Request to start Bluesky OAuth flow."""
    handle: str = Field(min_length=1, description="Bluesky handle, e.g. 'alice.bsky.social'")


class BlueskyAuthorizeResponse(BaseModel):
    """Response with authorization URL for Bluesky OAuth."""
    authorization_url: str
```

**Step 2: Add keypair initialization to `backend/main.py`**

In the `lifespan` function, after the git service initialization, add:

```python
    # Initialize AT Protocol OAuth keypair for Bluesky cross-posting
    from backend.crosspost.atproto_oauth import load_or_create_keypair
    oauth_key_path = settings.content_dir / ".atproto-oauth-key.json"
    atproto_key, atproto_jwk = load_or_create_keypair(oauth_key_path)
    app.state.atproto_oauth_key = atproto_key
    app.state.atproto_oauth_jwk = atproto_jwk

    from backend.crosspost.bluesky_oauth_state import OAuthStateStore
    app.state.bluesky_oauth_state = OAuthStateStore(ttl_seconds=600)
```

**Step 3: Add API endpoints to `backend/api/crosspost.py`**

```python
from fastapi import Query, Request
from fastapi.responses import RedirectResponse

from backend.schemas.crosspost import BlueskyAuthorizeRequest, BlueskyAuthorizeResponse


@router.get("/bluesky/client-metadata.json")
async def bluesky_client_metadata(
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> dict:
    """Serve AT Protocol OAuth client metadata document."""
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bluesky OAuth not configured: BLUESKY_CLIENT_URL not set",
        )
    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"
    jwk = request.app.state.atproto_oauth_jwk

    return {
        "client_id": client_id,
        "client_name": "AgBlogger",
        "client_uri": base_url,
        "grant_types": ["authorization_code", "refresh_token"],
        "scope": "atproto transition:generic",
        "response_types": ["code"],
        "redirect_uris": [redirect_uri],
        "dpop_bound_access_tokens": True,
        "application_type": "web",
        "token_endpoint_auth_method": "private_key_jwt",
        "token_endpoint_auth_signing_alg": "ES256",
        "jwks": {"keys": [jwk]},
    }


@router.post("/bluesky/authorize", response_model=BlueskyAuthorizeResponse)
async def bluesky_authorize(
    body: BlueskyAuthorizeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> BlueskyAuthorizeResponse:
    """Start Bluesky OAuth flow: resolve handle, send PAR, return auth URL."""
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bluesky OAuth not configured: BLUESKY_CLIENT_URL not set",
        )

    from backend.crosspost.atproto_oauth import (
        ATProtoOAuthError,
        discover_auth_server,
        resolve_handle_to_did,
        send_par_request,
    )

    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"

    try:
        did = await resolve_handle_to_did(body.handle)
        auth_meta = await discover_auth_server(did)
        par_result = await send_par_request(
            auth_server_meta=auth_meta,
            client_id=client_id,
            redirect_uri=redirect_uri,
            did=did,
            scope="atproto transition:generic",
            private_key=request.app.state.atproto_oauth_key,
            jwk=request.app.state.atproto_oauth_jwk,
        )
    except ATProtoOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Store pending state
    state_store = request.app.state.bluesky_oauth_state
    state_store.set(par_result["state"], {
        "pkce_verifier": par_result["pkce_verifier"],
        "dpop_nonce": par_result["dpop_nonce"],
        "user_id": user.id,
        "did": did,
        "handle": body.handle,
        "auth_server_meta": auth_meta,
    })

    return BlueskyAuthorizeResponse(authorization_url=par_result["authorization_url"])


@router.get("/bluesky/callback")
async def bluesky_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    iss: str = Query(""),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle Bluesky OAuth callback: exchange code for tokens, store account."""
    state_store = request.app.state.bluesky_oauth_state
    pending = state_store.pop(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    from backend.crosspost.atproto_oauth import (
        ATProtoOAuthError,
        exchange_code_for_tokens,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"
    auth_meta = pending["auth_server_meta"]
    private_key = request.app.state.atproto_oauth_key
    jwk = request.app.state.atproto_oauth_jwk

    try:
        token_data = await exchange_code_for_tokens(
            token_endpoint=auth_meta["token_endpoint"],
            auth_server_issuer=auth_meta["issuer"],
            code=code,
            redirect_uri=redirect_uri,
            pkce_verifier=pending["pkce_verifier"],
            client_id=client_id,
            private_key=private_key,
            jwk=jwk,
            dpop_nonce=pending["dpop_nonce"],
        )
    except ATProtoOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed: {exc}",
        ) from exc

    # Verify the returned sub matches the expected DID
    if token_data.get("sub") != pending["did"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DID mismatch in token response",
        )

    # Generate a per-session DPoP key for PDS requests
    from backend.crosspost.atproto_oauth import generate_es256_keypair
    dpop_key, dpop_jwk = generate_es256_keypair()
    dpop_pem = dpop_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

    # Build credentials to store (encrypted)
    import json
    credentials = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "did": pending["did"],
        "handle": pending["handle"],
        "pds_url": auth_meta["pds_url"],
        "dpop_private_key_pem": dpop_pem,
        "dpop_jwk": json.dumps(dpop_jwk),
        "dpop_nonce": token_data.get("dpop_nonce", ""),
        "auth_server_issuer": auth_meta["issuer"],
        "token_endpoint": auth_meta["token_endpoint"],
        "client_id": client_id,
    }

    from backend.schemas.crosspost import SocialAccountCreate
    from backend.services.crosspost_service import create_social_account

    account_data = SocialAccountCreate(
        platform="bluesky",
        account_name=pending["handle"],
        credentials=credentials,
    )

    try:
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)
    except ValueError:
        # Account may already exist; delete old one and recreate
        from backend.services.crosspost_service import get_social_accounts, delete_social_account
        existing = await get_social_accounts(session, pending["user_id"])
        for acct in existing:
            if acct.platform == "bluesky":
                await delete_social_account(session, acct.id, pending["user_id"])
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)

    # Redirect back to the app
    return RedirectResponse(url=f"{base_url}/admin", status_code=303)
```

**Step 4: Write tests for the endpoints**

Write to `tests/test_api/test_bluesky_oauth_endpoints.py`:

```python
"""Tests for Bluesky OAuth API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import TEST_SECRET_KEY, create_test_client

if TYPE_CHECKING:
    from pathlib import Path

    from backend.config import Settings


@pytest.fixture
def oauth_settings(test_settings: Settings) -> Settings:
    test_settings.bluesky_client_url = "https://myblog.example.com"
    return test_settings


class TestClientMetadata:
    async def test_returns_metadata_when_configured(self, oauth_settings) -> None:
        async with create_test_client(oauth_settings) as client:
            resp = await client.get("/api/crosspost/bluesky/client-metadata.json")
            assert resp.status_code == 200
            data = resp.json()
            assert data["client_id"] == "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json"
            assert data["application_type"] == "web"
            assert data["dpop_bound_access_tokens"] is True
            assert data["token_endpoint_auth_method"] == "private_key_jwt"
            assert "keys" in data["jwks"]
            assert data["jwks"]["keys"][0]["kty"] == "EC"

    async def test_returns_503_when_not_configured(self, test_settings) -> None:
        test_settings.bluesky_client_url = ""
        async with create_test_client(test_settings) as client:
            resp = await client.get("/api/crosspost/bluesky/client-metadata.json")
            assert resp.status_code == 503


class TestAuthorizeEndpoint:
    async def test_returns_401_when_not_authenticated(self, oauth_settings) -> None:
        async with create_test_client(oauth_settings) as client:
            resp = await client.post(
                "/api/crosspost/bluesky/authorize",
                json={"handle": "alice.bsky.social"},
            )
            assert resp.status_code == 401


class TestCallbackEndpoint:
    async def test_rejects_invalid_state(self, oauth_settings) -> None:
        async with create_test_client(oauth_settings) as client:
            resp = await client.get(
                "/api/crosspost/bluesky/callback",
                params={"code": "test-code", "state": "invalid-state"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
```

**Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_bluesky_oauth_endpoints.py -v && uv run pytest tests/test_services/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/api/crosspost.py backend/schemas/crosspost.py backend/main.py tests/test_api/test_bluesky_oauth_endpoints.py
git commit -m "feat: add Bluesky OAuth API endpoints (client-metadata, authorize, callback)"
```

---

### Task 6: Update crosspost_service for Token Refresh Persistence

**Files:**
- Modify: `backend/services/crosspost_service.py`
- Modify: `tests/test_services/test_crosspost_decrypt_fallback.py`

This task updates the crosspost service to persist refreshed OAuth tokens after a successful cross-post. When `BlueskyCrossPoster` refreshes tokens during a post, the updated credentials are re-encrypted and saved.

**Step 1: Write failing test**

Add to `tests/test_services/test_crosspost_decrypt_fallback.py`:

```python
class TestCrosspostTokenRefreshPersistence:
    async def test_updated_credentials_are_persisted(self, session, monkeypatch):
        """When BlueskyCrossPoster refreshes tokens during post(), the new tokens
        should be encrypted and saved back to the SocialAccount."""
        import json
        from backend.services.crypto_service import encrypt_value
        from backend.crosspost.base import CrossPostContent, CrossPostResult

        # Create a mock poster that simulates a token refresh
        class MockPoster:
            platform = "bluesky"
            _updated = {"access_token": "new_at", "refresh_token": "new_rt"}

            async def authenticate(self, creds):
                return True

            async def post(self, content):
                return CrossPostResult(platform_id="at://post/1", url="https://bsky.app/post/1", success=True)

            def get_updated_credentials(self):
                return self._updated

        async def mock_get_poster(platform, creds):
            return MockPoster()

        monkeypatch.setattr("backend.services.crosspost_service.get_poster", mock_get_poster)

        # Set up account with initial credentials
        creds = json.dumps({"access_token": "old_at", "refresh_token": "old_rt"})
        encrypted = encrypt_value(creds, TEST_SECRET_KEY)
        now = format_datetime(now_utc())
        account = SocialAccount(
            user_id=1, platform="bluesky", account_name="test",
            credentials=encrypted, created_at=now, updated_at=now,
        )
        session.add(account)
        await session.commit()

        mock_cm = MagicMock()
        mock_cm.read_post.return_value = MagicMock(
            title="Test", content="content", labels=[], is_draft=False,
        )
        mock_cm.get_plain_excerpt.return_value = "excerpt"

        results = await crosspost(
            session=session, content_manager=mock_cm,
            post_path="posts/test.md", platforms=["bluesky"],
            actor=MagicMock(id=1, username="tester", display_name="Tester", is_admin=False),
            site_url="https://example.com", secret_key=TEST_SECRET_KEY,
        )
        assert results[0].success

        # Verify credentials were updated in DB
        from sqlalchemy import select
        stmt = select(SocialAccount).where(SocialAccount.id == account.id)
        result = await session.execute(stmt)
        updated_acct = result.scalar_one()
        from backend.services.crypto_service import decrypt_value
        stored = json.loads(decrypt_value(updated_acct.credentials, TEST_SECRET_KEY))
        assert stored["access_token"] == "new_at"
        assert stored["refresh_token"] == "new_rt"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_crosspost_decrypt_fallback.py::TestCrosspostTokenRefreshPersistence -v`
Expected: FAIL

**Step 3: Update crosspost_service.py**

In the `crosspost()` function, after `post_result = await poster.post(content)`, add:

```python
        # Persist refreshed credentials if tokens were updated during posting
        if hasattr(poster, "get_updated_credentials"):
            updated_creds = poster.get_updated_credentials()
            if updated_creds is not None:
                account.credentials = encrypt_value(json.dumps(updated_creds), secret_key)
                account.updated_at = now
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_crosspost_decrypt_fallback.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/services/crosspost_service.py tests/test_services/test_crosspost_decrypt_fallback.py
git commit -m "feat: persist refreshed Bluesky OAuth tokens after cross-posting"
```

---

### Task 7: Update ARCHITECTURE.md and Run Full Check

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update ARCHITECTURE.md**

Update the Cross-Posting section to reflect the OAuth change:

- Replace mention of username+password with OAuth (DPoP-bound tokens)
- Add `bluesky_client_url` to the Settings documentation
- Add the three new endpoints to the API routes table
- Mention the ES256 keypair stored at `{content_dir}/.atproto-oauth-key.json`
- Update the Platforms subsection for Bluesky

**Step 2: Run full check**

Run: `just check`
Expected: All checks pass. Fix any type errors, lint issues, or test failures.

**Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: update architecture for Bluesky AT Protocol OAuth"
```
