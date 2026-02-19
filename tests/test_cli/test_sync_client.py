"""Security tests for CLI authentication transport settings."""

from __future__ import annotations

import pytest

from cli.sync_client import validate_server_url


class TestValidateServerUrl:
    def test_rejects_insecure_http_for_remote_hosts(self) -> None:
        with pytest.raises(ValueError, match="HTTPS is required"):
            validate_server_url("http://example.com")

    def test_allows_https_for_remote_hosts(self) -> None:
        assert validate_server_url("https://example.com") == "https://example.com"

    def test_allows_http_for_localhost(self) -> None:
        assert validate_server_url("http://localhost:8000") == "http://localhost:8000"

    def test_allows_insecure_http_when_flag_enabled(self) -> None:
        assert (
            validate_server_url("http://example.com:8000", allow_insecure_http=True)
            == "http://example.com:8000"
        )
