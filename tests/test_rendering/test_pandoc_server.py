"""Tests for the PandocServer lifecycle manager and render-via-server."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.pandoc.server import PandocServer


class TestPandocServerInit:
    def test_default_port_and_timeout(self) -> None:
        server = PandocServer()
        assert server._port == 3031
        assert server._timeout == 10

    def test_custom_port_and_timeout(self) -> None:
        server = PandocServer(port=4000, timeout=30)
        assert server._port == 4000
        assert server._timeout == 30

    def test_base_url(self) -> None:
        server = PandocServer(port=5050)
        assert server.base_url == "http://127.0.0.1:5050"

    def test_is_running_false_when_no_process(self) -> None:
        server = PandocServer()
        assert server.is_running is False


class TestCheckServerSupport:
    async def test_raises_when_server_not_supported(self) -> None:
        server = PandocServer()
        mock_result = MagicMock()
        mock_result.stdout = "pandoc 3.6\nFeatures: -server\n"
        mock_result.returncode = 0
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (mock_result.stdout.encode(), b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc
            with pytest.raises(RuntimeError, match="does not support server mode"):
                await server._check_server_support()

    async def test_passes_when_server_supported(self) -> None:
        server = PandocServer()
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (
                b"pandoc 3.6\nFeatures: +server\n",
                b"",
            )
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc
            # Should not raise
            await server._check_server_support()

    async def test_raises_when_pandoc_not_found(self) -> None:
        server = PandocServer()
        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("No such file"),
            ),
            pytest.raises(RuntimeError, match="Pandoc is not installed"),
        ):
            await server._check_server_support()

    async def test_raises_when_version_command_fails(self) -> None:
        server = PandocServer()
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"error")
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc
            with pytest.raises(RuntimeError, match="Failed to check pandoc version"):
                await server._check_server_support()


class TestSpawn:
    async def test_spawn_creates_subprocess(self) -> None:
        server = PandocServer(port=3031, timeout=10)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = None
            mock_exec.return_value = mock_proc
            await server._spawn()
            mock_exec.assert_called_once_with(
                "pandoc",
                "server",
                "--port",
                "3031",
                "--timeout",
                "10",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            assert server._process is mock_proc


class TestWaitForReady:
    async def test_succeeds_when_server_responds(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            await server._wait_for_ready()

    async def test_succeeds_on_http_error_non_connect(self) -> None:
        """A ReadError or similar means the server is listening but rejects GET."""
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ReadError("connection reset")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            # Should succeed — ReadError means the server is listening
            await server._wait_for_ready()

    async def test_retries_on_connection_error(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = [
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
                mock_response,
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            await server._wait_for_ready()
            assert mock_sleep.call_count == 2

    async def test_raises_when_process_exits_during_startup(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.read.return_value = b"GHC timer error"
        server._process = mock_proc

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            with pytest.raises(RuntimeError, match="Pandoc server exited"):
                await server._wait_for_ready()

    async def test_raises_after_max_retries(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            with pytest.raises(RuntimeError, match="Pandoc server failed to start"):
                await server._wait_for_ready()


class TestStop:
    async def test_stop_terminates_running_process(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock()
        server._process = mock_proc

        await server.stop()
        mock_proc.terminate.assert_called_once()
        assert server._process is None

    async def test_stop_kills_if_terminate_times_out(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()
        # First wait() call (inside wait_for) raises TimeoutError;
        # second wait() call (after kill) succeeds.
        mock_proc.wait = AsyncMock(side_effect=[asyncio.TimeoutError, None])
        server._process = mock_proc

        await server.stop()
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert server._process is None

    async def test_stop_is_idempotent(self) -> None:
        server = PandocServer()
        # No process set, should not raise
        await server.stop()
        await server.stop()

    async def test_stop_when_process_already_exited(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = 0  # Already exited
        server._process = mock_proc

        await server.stop()
        assert server._process is None


class TestStart:
    async def test_start_calls_check_spawn_and_wait(self) -> None:
        server = PandocServer()
        with (
            patch.object(server, "_check_server_support", new_callable=AsyncMock) as mock_check,
            patch.object(server, "_spawn", new_callable=AsyncMock) as mock_spawn,
            patch.object(server, "_wait_for_ready", new_callable=AsyncMock) as mock_wait,
        ):
            await server.start()
            mock_check.assert_awaited_once()
            mock_spawn.assert_awaited_once()
            mock_wait.assert_awaited_once()

    async def test_start_stops_existing_before_starting(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        with (
            patch.object(server, "stop", new_callable=AsyncMock) as mock_stop,
            patch.object(server, "_check_server_support", new_callable=AsyncMock),
            patch.object(server, "_spawn", new_callable=AsyncMock),
            patch.object(server, "_wait_for_ready", new_callable=AsyncMock),
        ):
            await server.start()
            mock_stop.assert_awaited_once()


class TestEnsureRunning:
    async def test_no_restart_when_running(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        server._process = mock_proc

        with patch.object(server, "start", new_callable=AsyncMock) as mock_start:
            await server.ensure_running()
            mock_start.assert_not_awaited()

    async def test_restarts_when_process_dead(self) -> None:
        server = PandocServer()
        mock_proc = AsyncMock()
        mock_proc.returncode = 1  # exited
        server._process = mock_proc

        with patch.object(server, "start", new_callable=AsyncMock) as mock_start:
            await server.ensure_running()
            mock_start.assert_awaited_once()

    async def test_restarts_when_no_process(self) -> None:
        server = PandocServer()

        with patch.object(server, "start", new_callable=AsyncMock) as mock_start:
            await server.ensure_running()
            mock_start.assert_awaited_once()

    async def test_concurrent_ensure_running_only_starts_once(self) -> None:
        server = PandocServer()
        start_count = 0

        async def mock_start() -> None:
            nonlocal start_count
            start_count += 1
            # Simulate the start setting up a running process
            mock_proc = AsyncMock()
            mock_proc.returncode = None
            server._process = mock_proc
            await asyncio.sleep(0.1)

        with patch.object(server, "start", side_effect=mock_start):
            await asyncio.gather(
                server.ensure_running(),
                server.ensure_running(),
                server.ensure_running(),
            )
            assert start_count == 1


async def _pandoc_server_available() -> bool:
    """Check if pandoc server mode can actually start locally."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pandoc",
            "server",
            "--port",
            "0",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
            # If it exited within 1 second, server mode is not functional
            return False
        except TimeoutError:
            # Still running after 1 second -- server mode works
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except TimeoutError:
                proc.kill()
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


@pytest.fixture(scope="module")
def pandoc_server_available() -> bool:
    """Eagerly check if pandoc server mode is available."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_pandoc_server_available())
    finally:
        loop.close()


class TestIntegration:
    """Integration tests that start a real pandoc server process.

    Skipped when pandoc server mode is not functional locally (e.g. macOS
    Homebrew builds lacking GHC threaded runtime).
    """

    async def test_start_and_stop(self, pandoc_server_available: bool) -> None:
        if not pandoc_server_available:
            pytest.skip("pandoc server mode not available locally")

        server = PandocServer(port=13031, timeout=10)
        try:
            await server.start()
            assert server.is_running
        finally:
            await server.stop()
        assert not server.is_running

    async def test_ensure_running_recovers(self, pandoc_server_available: bool) -> None:
        if not pandoc_server_available:
            pytest.skip("pandoc server mode not available locally")

        server = PandocServer(port=13032, timeout=10)
        try:
            await server.start()
            assert server.is_running

            # Forcefully kill the process and verify it recovers
            proc = server._process
            assert proc is not None
            proc.kill()
            await proc.wait()
        finally:
            await server.stop()

        # Start fresh, kill, and verify ensure_running recovers
        try:
            await server.start()
            proc = server._process
            assert proc is not None
            proc.kill()
            await proc.wait()

            await server.ensure_running()
            assert server.is_running
        finally:
            await server.stop()


class TestRenderViaServer:
    """Tests for render_markdown() using the pandoc server HTTP API."""

    async def test_render_simple_markdown(self) -> None:
        """Mock httpx client, verify sanitized HTML returned."""
        from backend.pandoc import renderer

        mock_server = MagicMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"output": "<p>Hello <strong>world</strong></p>\n"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
        ):
            result = await renderer.render_markdown("Hello **world**")

        assert "<p>Hello <strong>world</strong></p>" in result
        mock_client.post.assert_awaited_once()

    async def test_render_connection_error_triggers_restart(self) -> None:
        """Mock ConnectError on first call, success on retry."""
        from backend.pandoc import renderer

        mock_server = AsyncMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        success_response = MagicMock()
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {"output": "<p>ok</p>\n"}

        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            httpx.ConnectError("connection refused"),
            success_response,
        ]

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
        ):
            result = await renderer.render_markdown("ok")

        mock_server.ensure_running.assert_awaited_once()
        assert "<p>ok</p>" in result

    async def test_render_timeout_raises_runtime_error(self) -> None:
        """Mock ReadTimeout, verify RuntimeError."""
        from backend.pandoc import renderer

        mock_server = MagicMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ReadTimeout("timed out")

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            await renderer.render_markdown("# slow")

    async def test_render_server_not_initialized_raises(self) -> None:
        """Patch _server to None, verify RuntimeError."""
        from backend.pandoc import renderer

        with (
            patch.object(renderer, "_server", None),
            patch.object(renderer, "_http_client", None),
            pytest.raises(RuntimeError, match="not initialized"),
        ):
            await renderer.render_markdown("# test")

    async def test_render_pandoc_error_response(self) -> None:
        """Mock response with {"error": "..."}, verify RuntimeError."""
        from backend.pandoc import renderer

        mock_server = MagicMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"error": "Could not parse input"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
            pytest.raises(RuntimeError, match="Could not parse input"),
        ):
            await renderer.render_markdown("bad input")

    async def test_render_double_connect_error_raises(self) -> None:
        """Double ConnectError (initial + post-restart) should raise RuntimeError."""
        from backend.pandoc import renderer

        mock_server = AsyncMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
            pytest.raises(RuntimeError, match="unreachable after restart"),
        ):
            await renderer.render_markdown("test")

        mock_server.ensure_running.assert_called_once()

    async def test_render_non_json_response_raises(self) -> None:
        """Non-JSON response from pandoc server should raise RuntimeError."""
        from backend.pandoc import renderer

        mock_server = AsyncMock(spec=PandocServer)
        mock_server.base_url = "http://127.0.0.1:3031"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("not JSON")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(renderer, "_server", mock_server),
            patch.object(renderer, "_http_client", mock_client),
            pytest.raises(RuntimeError, match="non-JSON response"),
        ):
            await renderer.render_markdown("test")
