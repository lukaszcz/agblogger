"""SSRF-safe HTTP client: validates resolved IPs at the socket connection level."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import httpcore
import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

_BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})

_SocketOption = (
    tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
)


def _is_public_ip(ip_text: str) -> bool:
    """Return True when an IP address is globally routable (public)."""
    ip = ipaddress.ip_address(ip_text)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


class SSRFSafeBackend(httpcore.AsyncNetworkBackend):
    """Network backend that blocks connections to private/reserved IPs.

    DNS resolution happens inside connect_tcp() so validation occurs at
    connection time, closing the TOCTOU gap that pre-request DNS checks have.
    """

    def __init__(self) -> None:
        self._inner = cast("httpcore.AsyncNetworkBackend", httpcore.AnyIOBackend())

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[_SocketOption] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        # Reject blocked hostnames outright
        if host.strip().lower() in _BLOCKED_HOSTNAMES:
            msg = f"SSRF protection: blocked hostname {host!r}"
            raise httpcore.ConnectError(msg)

        # Resolve DNS asynchronously and validate all returned IPs
        loop = asyncio.get_running_loop()
        try:
            addr_infos = await loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            msg = f"DNS resolution failed for {host!r}"
            raise httpcore.ConnectError(msg) from exc

        if not addr_infos:
            msg = f"DNS resolution returned no results for {host!r}"
            raise httpcore.ConnectError(msg)

        # Validate every resolved IP is public
        for _family, _type, _proto, _canonname, sockaddr in addr_infos:
            ip_text = str(sockaddr[0])
            if not _is_public_ip(ip_text):
                msg = f"SSRF protection: {host!r} resolved to private IP {ip_text}"
                raise httpcore.ConnectError(msg)

        # Use the first resolved IP to connect (bypasses re-resolution)
        validated_ip = str(addr_infos[0][4][0])
        return await self._inner.connect_tcp(
            validated_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[_SocketOption] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        msg = "SSRF protection: Unix socket connections are not allowed"
        raise httpcore.ConnectError(msg)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


@asynccontextmanager
async def ssrf_safe_client(
    timeout: float | httpx.Timeout | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create an httpx.AsyncClient that validates IPs at connection time."""
    transport = httpx.AsyncHTTPTransport()
    # Inject our SSRF-safe network backend into the transport's connection pool.
    # Uses httpx internal _pool attribute (tested against httpx 0.28.x).
    transport._pool = httpcore.AsyncConnectionPool(
        network_backend=SSRFSafeBackend(),
    )
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        yield client
