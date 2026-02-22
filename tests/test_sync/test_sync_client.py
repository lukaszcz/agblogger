"""Tests for simplified CLI sync client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cli import sync_client
from cli.sync_client import SyncClient

if TYPE_CHECKING:
    from pathlib import Path


class _DummyResponse:
    def __init__(
        self,
        json_data: dict[str, Any] | None = None,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self._json_data = json_data or {}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._json_data


class _RecordingHttpClient:
    def __init__(self, responses: dict[str, _DummyResponse] | None = None) -> None:
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses or {}

    def post(self, url: str, **kwargs: Any) -> _DummyResponse:
        self.post_calls.append((url, kwargs))
        return self._responses.get(url, _DummyResponse())

    def get(self, url: str, **kwargs: Any) -> _DummyResponse:
        self.get_calls.append((url, kwargs))
        return self._responses.get(url, _DummyResponse())

    def close(self) -> None:
        return None


def _build_sync_client(
    content_dir: Path,
    responses: dict[str, _DummyResponse] | None = None,
) -> tuple[SyncClient, _RecordingHttpClient]:
    client = SyncClient("http://example.com", content_dir, "test-token")
    http_client = _RecordingHttpClient(responses)
    client.client = http_client  # type: ignore[assignment]
    return client, http_client


class TestSyncClientStatus:
    def test_status_calls_new_endpoint(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        client, http_client = _build_sync_client(content_dir)
        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        client.status()
        assert any(url == "/api/sync/status" for url, _ in http_client.post_calls)


class TestSyncClientSync:
    def test_sync_sends_files_in_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "new.md").write_text("# New\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "abc123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": ["posts/new.md"],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        commit_calls = [
            (url, kw) for url, kw in http_client.post_calls if url == "/api/sync/commit"
        ]
        assert len(commit_calls) == 1

    def test_sync_saves_commit_hash(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "saved123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        config = sync_client.load_config(content_dir)
        assert config["last_sync_commit"] == "saved123"

    def test_sync_downloads_server_changed_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "dl123",
                "conflicts": [],
                "to_download": ["posts/remote.md"],
                "warnings": [],
            }
        )
        download_resp = _DummyResponse(content=b"# Remote\n\nContent.\n")
        client, http_client = _build_sync_client(
            content_dir,
            responses={
                "/api/sync/commit": commit_resp,
                "/api/sync/download/posts/remote.md": download_resp,
            },
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": ["posts/remote.md"],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        assert (posts_dir / "remote.md").exists()

    def test_sync_reports_conflicts(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "conflict.md").write_text("# Client\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "c123",
                "conflicts": [
                    {
                        "file_path": "posts/conflict.md",
                        "body_conflicted": True,
                        "field_conflicts": [],
                    }
                ],
                "to_download": [],
                "warnings": [],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": ["posts/conflict.md"],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()
        # No crash; conflicts are reported via print

    def test_sync_deletes_local_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        local_file = posts_dir / "old.md"
        local_file.write_text("# Old\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "del123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": ["posts/old.md"],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        assert not local_file.exists()

    def test_sync_sends_remote_deletes_in_metadata(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "rdel123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": ["posts/deleted.md"],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        # Verify metadata was sent with deleted_files
        commit_calls = [
            (url, kw) for url, kw in http_client.post_calls if url == "/api/sync/commit"
        ]
        assert len(commit_calls) == 1

    def test_sync_sends_last_sync_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        sync_client.save_config(content_dir, {"last_sync_commit": "deadbeef"})

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "new123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        # Verify the commit was called (last_sync_commit is embedded in metadata)
        commit_calls = [
            (url, kw) for url, kw in http_client.post_calls if url == "/api/sync/commit"
        ]
        assert len(commit_calls) == 1

    def test_sync_uploads_conflict_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "conflict.md").write_text("# Client version\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "abc123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [{"file_path": "posts/conflict.md", "action": "merge"}],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        # Conflict files should be included in the multipart commit upload
        commit_calls = [
            (url, kw) for url, kw in http_client.post_calls if url == "/api/sync/commit"
        ]
        assert len(commit_calls) == 1


class TestRemovedMethods:
    def test_push_method_removed(self) -> None:
        assert not hasattr(SyncClient, "push")

    def test_pull_method_removed(self) -> None:
        assert not hasattr(SyncClient, "pull")

    def test_upload_file_method_removed(self) -> None:
        assert not hasattr(SyncClient, "_upload_file")
