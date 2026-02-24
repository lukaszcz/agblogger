"""Tests for SSRF-safe HTTP client (backend.crosspost.ssrf)."""

from __future__ import annotations

import socket
from unittest.mock import patch

import httpcore
import pytest

from backend.crosspost.ssrf import SSRFSafeBackend, _is_public_ip, ssrf_safe_client


class TestIsPublicIp:
    def test_public_ipv4(self) -> None:
        assert _is_public_ip("93.184.216.34") is True

    def test_public_ipv6(self) -> None:
        assert _is_public_ip("2606:2800:220:1:248:1893:25c8:1946") is True

    def test_private_ipv4_10(self) -> None:
        assert _is_public_ip("10.0.0.1") is False

    def test_private_ipv4_172(self) -> None:
        assert _is_public_ip("172.16.0.1") is False

    def test_private_ipv4_192(self) -> None:
        assert _is_public_ip("192.168.1.1") is False

    def test_loopback_ipv4(self) -> None:
        assert _is_public_ip("127.0.0.1") is False

    def test_loopback_ipv6(self) -> None:
        assert _is_public_ip("::1") is False

    def test_link_local_ipv4(self) -> None:
        assert _is_public_ip("169.254.1.1") is False

    def test_link_local_ipv6(self) -> None:
        assert _is_public_ip("fe80::1") is False

    def test_multicast_ipv4(self) -> None:
        assert _is_public_ip("224.0.0.1") is False

    def test_reserved_ipv4(self) -> None:
        assert _is_public_ip("240.0.0.1") is False

    def test_unspecified_ipv4(self) -> None:
        assert _is_public_ip(".".join(["0"] * 4)) is False

    def test_unspecified_ipv6(self) -> None:
        assert _is_public_ip("::") is False

    def test_ipv4_mapped_ipv6_loopback(self) -> None:
        assert _is_public_ip("::ffff:127.0.0.1") is False

    def test_ipv4_mapped_ipv6_private(self) -> None:
        assert _is_public_ip("::ffff:10.0.0.1") is False

    def test_ipv4_mapped_ipv6_public(self) -> None:
        assert _is_public_ip("::ffff:93.184.216.34") is True


class TestSSRFSafeBackend:
    async def test_connect_tcp_blocks_private_ip(self) -> None:
        backend = SSRFSafeBackend()
        with patch("backend.crosspost.ssrf.socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 443))
            ]
            with pytest.raises(httpcore.ConnectError, match="private IP"):
                await backend.connect_tcp("evil.example.com", 443)

    async def test_connect_tcp_blocks_loopback(self) -> None:
        backend = SSRFSafeBackend()
        with patch("backend.crosspost.ssrf.socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
            ]
            with pytest.raises(httpcore.ConnectError, match="private IP"):
                await backend.connect_tcp("evil.example.com", 443)

    async def test_connect_tcp_blocks_localhost_hostname(self) -> None:
        backend = SSRFSafeBackend()
        with pytest.raises(httpcore.ConnectError, match="blocked hostname"):
            await backend.connect_tcp("localhost", 443)

    async def test_connect_tcp_allows_public_ip(self) -> None:
        backend = SSRFSafeBackend()
        connected_to: list[str] = []

        async def mock_connect_tcp(
            host, port, *, timeout=None, local_address=None, socket_options=None
        ):
            connected_to.append(host)

        with (
            patch("backend.crosspost.ssrf.socket.getaddrinfo") as mock_gai,
            patch.object(backend._inner, "connect_tcp", mock_connect_tcp),
        ):
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
            ]
            await backend.connect_tcp("example.com", 443)

        assert connected_to == ["93.184.216.34"]

    async def test_connect_tcp_dns_failure_raises(self) -> None:
        backend = SSRFSafeBackend()
        with patch("backend.crosspost.ssrf.socket.getaddrinfo") as mock_gai:
            mock_gai.side_effect = socket.gaierror("DNS failure")
            with pytest.raises(httpcore.ConnectError, match="DNS resolution failed"):
                await backend.connect_tcp("nonexistent.invalid", 443)

    async def test_connect_tcp_blocks_mixed_ips(self) -> None:
        """If any resolved IP is private, the connection should be blocked."""
        backend = SSRFSafeBackend()
        with patch("backend.crosspost.ssrf.socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
            ]
            with pytest.raises(httpcore.ConnectError, match="private IP"):
                await backend.connect_tcp("mixed.example.com", 443)

    async def test_connect_unix_socket_raises(self) -> None:
        backend = SSRFSafeBackend()
        with pytest.raises(httpcore.ConnectError, match="Unix socket"):
            await backend.connect_unix_socket("/var/run/docker.sock")


class TestSSRFSafeClient:
    async def test_returns_async_client(self) -> None:
        async with ssrf_safe_client() as client:
            assert hasattr(client, "get")
            assert hasattr(client, "post")
