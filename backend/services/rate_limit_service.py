"""Simple in-memory rate limiting helpers for auth endpoints."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime


class InMemoryRateLimiter:
    """Track failed attempts in an in-memory sliding window."""

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def clear(self, key: str) -> None:
        """Clear all attempts for a key."""
        self._attempts.pop(key, None)

    def is_limited(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return whether the key is rate-limited and retry-after seconds."""
        now = datetime.now(UTC).timestamp()
        attempts = self._attempts[key]
        cutoff = now - window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if len(attempts) < limit:
            return False, 0
        retry_after = int(attempts[0] + window_seconds - now) + 1
        return True, max(retry_after, 1)

    def add_failure(self, key: str, window_seconds: int) -> None:
        """Record one failed attempt."""
        now = datetime.now(UTC).timestamp()
        attempts = self._attempts[key]
        cutoff = now - window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        attempts.append(now)
