"""Tests for AT Protocol OAuth helpers."""

from __future__ import annotations

import base64
import hashlib

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
        _private_key, jwk = load_or_create_keypair(path)
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
        expected_ath = (
            base64.urlsafe_b64encode(hashlib.sha256(access_token.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        assert payload["ath"] == expected_ath


class TestPKCE:
    def test_create_pkce_challenge(self) -> None:
        verifier, challenge = create_pkce_challenge()
        assert len(verifier) >= 43
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        assert challenge == expected


class TestClientAssertion:
    def test_create_client_assertion_jwt(self) -> None:
        private_key, jwk = generate_es256_keypair()
        client_id = "https://myblog.example.com/api/crosspost/bluesky/client-metadata.json"
        aud = "https://bsky.social"
        assertion = create_client_assertion(client_id, aud, private_key, jwk["kid"])
        payload = jwt.decode(
            assertion,
            private_key.public_key(),
            algorithms=["ES256"],
            audience=aud,
        )
        assert payload["iss"] == client_id
        assert payload["sub"] == client_id
        assert payload["aud"] == aud
        assert "jti" in payload
        assert "exp" in payload
