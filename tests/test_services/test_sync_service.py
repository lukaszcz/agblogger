"""Tests for the sync service."""

from backend.services.sync_service import (
    ChangeType,
    FileEntry,
    SyncPlan,
    compute_sync_plan,
)


def _entry(path: str, hash_: str = "abc", size: int = 100) -> FileEntry:
    return FileEntry(file_path=path, content_hash=hash_, file_size=size, file_mtime="1.0")


class TestComputeSyncPlan:
    def test_no_changes(self) -> None:
        manifest = {"a.md": _entry("a.md", "aaa")}
        client = {"a.md": _entry("a.md", "aaa")}
        server = {"a.md": _entry("a.md", "aaa")}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.no_change
        assert plan.to_upload == []
        assert plan.to_download == []

    def test_local_modification(self) -> None:
        manifest = {"a.md": _entry("a.md", "old")}
        client = {"a.md": _entry("a.md", "new")}
        server = {"a.md": _entry("a.md", "old")}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.to_upload

    def test_remote_modification(self) -> None:
        manifest = {"a.md": _entry("a.md", "old")}
        client = {"a.md": _entry("a.md", "old")}
        server = {"a.md": _entry("a.md", "new")}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.to_download

    def test_conflict(self) -> None:
        manifest = {"a.md": _entry("a.md", "old")}
        client = {"a.md": _entry("a.md", "client_new")}
        server = {"a.md": _entry("a.md", "server_new")}
        plan = compute_sync_plan(client, manifest, server)
        assert len(plan.conflicts) == 1
        assert plan.conflicts[0].file_path == "a.md"
        assert plan.conflicts[0].change_type == ChangeType.CONFLICT

    def test_both_same_change(self) -> None:
        """Both modified to same content = no conflict."""
        manifest = {"a.md": _entry("a.md", "old")}
        client = {"a.md": _entry("a.md", "same_new")}
        server = {"a.md": _entry("a.md", "same_new")}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.no_change

    def test_local_addition(self) -> None:
        plan = compute_sync_plan(
            {"new.md": _entry("new.md", "abc")},
            {},
            {},
        )
        assert "new.md" in plan.to_upload

    def test_remote_addition(self) -> None:
        plan = compute_sync_plan(
            {},
            {},
            {"remote.md": _entry("remote.md", "xyz")},
        )
        assert "remote.md" in plan.to_download

    def test_local_deletion(self) -> None:
        manifest = {"a.md": _entry("a.md", "hash")}
        client: dict[str, FileEntry] = {}
        server = {"a.md": _entry("a.md", "hash")}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.to_delete_remote

    def test_remote_deletion(self) -> None:
        manifest = {"a.md": _entry("a.md", "hash")}
        client = {"a.md": _entry("a.md", "hash")}
        server: dict[str, FileEntry] = {}
        plan = compute_sync_plan(client, manifest, server)
        assert "a.md" in plan.to_delete_local

    def test_both_deleted(self) -> None:
        manifest = {"a.md": _entry("a.md", "hash")}
        plan = compute_sync_plan({}, manifest, {})
        assert "a.md" in plan.no_change

    def test_independent_additions_same_content(self) -> None:
        """Both sides add same file with same content."""
        client = {"new.md": _entry("new.md", "same")}
        server = {"new.md": _entry("new.md", "same")}
        plan = compute_sync_plan(client, {}, server)
        assert "new.md" in plan.no_change

    def test_independent_additions_different_content(self) -> None:
        """Both sides add same file with different content = conflict."""
        client = {"new.md": _entry("new.md", "aaa")}
        server = {"new.md": _entry("new.md", "bbb")}
        plan = compute_sync_plan(client, {}, server)
        assert len(plan.conflicts) == 1

    def test_multiple_files_mixed(self) -> None:
        manifest = {
            "keep.md": _entry("keep.md", "same"),
            "push.md": _entry("push.md", "old"),
            "pull.md": _entry("pull.md", "old"),
        }
        client = {
            "keep.md": _entry("keep.md", "same"),
            "push.md": _entry("push.md", "new_local"),
            "pull.md": _entry("pull.md", "old"),
            "added.md": _entry("added.md", "fresh"),
        }
        server = {
            "keep.md": _entry("keep.md", "same"),
            "push.md": _entry("push.md", "old"),
            "pull.md": _entry("pull.md", "new_remote"),
        }
        plan = compute_sync_plan(client, manifest, server)
        assert "keep.md" in plan.no_change
        assert "push.md" in plan.to_upload
        assert "pull.md" in plan.to_download
        assert "added.md" in plan.to_upload
