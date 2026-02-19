"""Tests for CLI sync client behavior."""

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
    ) -> None:
        self._json_data = json_data or {}
        self.status_code = 200
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


def _commit_payload(http_client: _RecordingHttpClient) -> dict[str, Any]:
    for url, kwargs in http_client.post_calls:
        if url == "/api/sync/commit":
            return kwargs["json"]
    raise AssertionError("No /api/sync/commit call was made")


class TestSyncClientRemoteDeletes:
    def test_push_includes_remote_deletes_in_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        client, http_client = _build_sync_client(content_dir)
        client.status = lambda: {"to_upload": [], "to_delete_remote": ["posts/deleted.md"]}

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.push()

        payload = _commit_payload(http_client)
        assert payload["uploaded_files"] == []
        assert payload["deleted_files"] == ["posts/deleted.md"]

    def test_sync_includes_remote_deletes_in_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "new.md").write_text("# New\n")

        client, http_client = _build_sync_client(content_dir)
        client.status = lambda: {
            "to_upload": ["posts/new.md"],
            "to_download": [],
            "to_delete_remote": ["posts/deleted.md"],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        payload = _commit_payload(http_client)
        assert payload["uploaded_files"] == ["posts/new.md"]
        assert payload["deleted_files"] == ["posts/deleted.md"]


class TestSyncClientMerge:
    def test_sync_uploads_conflict_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "conflict.md").write_text("# Client version\n")

        commit_resp = _DummyResponse(
            json_data={"status": "ok", "commit_hash": "abc123", "merge_results": []}
        )
        client, http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
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

        payload = _commit_payload(http_client)
        assert "posts/conflict.md" in payload["conflict_files"]

    def test_sync_sends_last_sync_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        # Write config with last_sync_commit
        sync_client.save_config(content_dir, {"last_sync_commit": "deadbeef"})

        commit_resp = _DummyResponse(
            json_data={"status": "ok", "commit_hash": "new123", "merge_results": []}
        )
        client, http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
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

        payload = _commit_payload(http_client)
        assert payload["last_sync_commit"] == "deadbeef"

    def test_sync_saves_commit_hash(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={"status": "ok", "commit_hash": "saved123", "merge_results": []}
        )
        client, _http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
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

    def test_push_saves_commit_hash(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={"status": "ok", "commit_hash": "push123", "merge_results": []}
        )
        client, _http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
        )
        client.status = lambda: {"to_upload": [], "to_delete_remote": []}

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.push()

        config = sync_client.load_config(content_dir)
        assert config["last_sync_commit"] == "push123"

    def test_pull_saves_commit_hash(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={"status": "ok", "commit_hash": "pull123", "merge_results": []}
        )
        client, _http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
        )
        client.status = lambda: {
            "to_download": [],
            "to_delete_local": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.pull()

        config = sync_client.load_config(content_dir)
        assert config["last_sync_commit"] == "pull123"

    def test_sync_handles_conflicted_result(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "conflict.md").write_text("# Original\n")

        conflict_content = "<<<<<<< SERVER\nserver\n=======\nclient\n>>>>>>> CLIENT\n"
        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "merge123",
                "merge_results": [
                    {
                        "file_path": "posts/conflict.md",
                        "status": "conflicted",
                        "content": conflict_content,
                    }
                ],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir,
            responses={"/api/sync/commit": commit_resp},
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

        # Conflict markers written to main file
        assert (posts_dir / "conflict.md").read_text() == conflict_content
        # Backup created
        assert (posts_dir / "conflict.md.conflict-backup").exists()

    def test_sync_handles_merged_result(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "merged.md").write_text("# Original\n")

        merged_content = b"# Merged\n\nBoth edits.\n"
        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "merged123",
                "merge_results": [
                    {"file_path": "posts/merged.md", "status": "merged", "content": None}
                ],
            }
        )
        download_resp = _DummyResponse(content=merged_content)
        client, _http_client = _build_sync_client(
            content_dir,
            responses={
                "/api/sync/commit": commit_resp,
                "/api/sync/download/posts/merged.md": download_resp,
            },
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [{"file_path": "posts/merged.md", "action": "merge"}],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        # Merged content downloaded from server
        assert (posts_dir / "merged.md").read_bytes() == merged_content
