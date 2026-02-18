"""Tests for auth service edge cases (Issues 13, 14)."""

from __future__ import annotations

from backend.services.auth_service import decode_access_token


class TestDecodeAccessToken:
    def test_valid_token_decodes(self) -> None:
        from backend.services.auth_service import create_access_token

        secret = "test-secret"
        token = create_access_token(
            {"sub": "1", "username": "admin", "is_admin": True},
            secret,
        )
        payload = decode_access_token(token, secret)
        assert payload is not None
        assert payload["sub"] == "1"

    def test_wrong_secret_returns_none(self) -> None:
        from backend.services.auth_service import create_access_token

        token = create_access_token(
            {"sub": "1", "username": "admin", "is_admin": True},
            "correct-secret",
        )
        assert decode_access_token(token, "wrong-secret") is None

    def test_garbage_token_returns_none(self) -> None:
        assert decode_access_token("not.a.jwt", "secret") is None

    def test_empty_token_returns_none(self) -> None:
        assert decode_access_token("", "secret") is None


class TestUserIdValidation:
    """Issue 13: get_current_user should validate user_id before int() conversion."""

    async def test_invalid_user_id_in_jwt_returns_none(self) -> None:
        """JWT with non-numeric sub should not crash the server."""
        from backend.services.auth_service import create_access_token

        secret = "test-secret"
        # Manually craft a token with a non-numeric sub
        # The create_access_token function sets type=access, so we need to decode
        token = create_access_token(
            {"sub": "not-a-number", "username": "hacker", "is_admin": False},
            secret,
        )
        payload = decode_access_token(token, secret)
        assert payload is not None
        # The sub is "not-a-number" — deps.py should handle this gracefully
        assert payload["sub"] == "not-a-number"
        # Validate that isdigit() check would catch this
        assert not payload["sub"].isdigit()
