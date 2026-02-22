"""Test helpers for mocking ssrf_safe_client."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import httpx


def make_fake_ssrf_safe_client(
    client_cls: type,
) -> object:
    """Create a fake ssrf_safe_client context manager that yields an instance of client_cls."""

    @asynccontextmanager
    async def fake_ssrf_safe_client(
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[object]:
        yield client_cls()

    return fake_ssrf_safe_client
