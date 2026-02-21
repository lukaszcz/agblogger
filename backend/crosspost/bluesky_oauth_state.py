"""Time-limited in-memory store for pending Bluesky OAuth flows."""

from __future__ import annotations

import time
from typing import Any


class OAuthStateStore:
    """Store pending OAuth authorization state with automatic expiry."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[dict[str, Any], float]] = {}

    def set(self, state: str, data: dict[str, Any]) -> None:
        """Store data for a pending OAuth flow."""
        self.cleanup()
        self._entries[state] = (data, time.time())

    def pop(self, state: str) -> dict[str, Any] | None:
        """Retrieve and remove data for a completed OAuth flow."""
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
