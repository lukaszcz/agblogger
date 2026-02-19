"""Symmetric encryption for credentials stored at rest."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _derive_key(secret_key: str) -> bytes:
    """Derive a Fernet key from the application secret using SHA-256."""
    digest = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plaintext: str, secret_key: str) -> str:
    """Encrypt a string and return the ciphertext as a URL-safe string."""
    f = Fernet(_derive_key(secret_key))
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, secret_key: str) -> str:
    """Decrypt a ciphertext string. Raises ValueError on failure."""
    f = Fernet(_derive_key(secret_key))
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt credential data") from exc
