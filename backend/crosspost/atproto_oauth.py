"""AT Protocol OAuth helpers: key generation, DPoP proofs, PKCE, client assertions."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from pathlib import Path


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
    """Create a DPoP proof JWT (ES256)."""
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
