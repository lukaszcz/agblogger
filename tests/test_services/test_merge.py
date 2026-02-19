"""Tests for the three-way merge logic."""

from __future__ import annotations

from backend.services.sync_service import merge_file


class TestMergeFile:
    def test_clean_merge_different_sections(self) -> None:
        base = "# Title\n\nFirst paragraph.\n\nSecond paragraph.\n"
        server = "# Title\n\nFirst paragraph (server).\n\nSecond paragraph.\n"
        client = "# Title\n\nFirst paragraph.\n\nSecond paragraph (client).\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert not has_conflicts
        assert "server" in merged
        assert "client" in merged

    def test_conflict_same_line(self) -> None:
        base = "line1\noriginal\nline3\n"
        server = "line1\nserver-version\nline3\n"
        client = "line1\nclient-version\nline3\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert has_conflicts
        assert "<<<<<<< SERVER" in merged
        assert ">>>>>>> CLIENT" in merged
        assert "||||||| BASE" in merged
        assert "server-version" in merged
        assert "client-version" in merged

    def test_no_base_returns_server_with_conflict(self) -> None:
        server = "server content\n"
        client = "client content\n"
        merged, has_conflicts = merge_file(None, server, client)
        assert has_conflicts
        assert merged == server

    def test_identical_changes_clean_merge(self) -> None:
        base = "original\n"
        server = "same change\n"
        client = "same change\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert not has_conflicts
        assert merged == "same change\n"

    def test_one_side_unchanged(self) -> None:
        base = "original\n"
        server = "original\n"
        client = "client changed\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert not has_conflicts
        assert merged == "client changed\n"

    def test_server_only_changed(self) -> None:
        base = "original\n"
        server = "server changed\n"
        client = "original\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert not has_conflicts
        assert merged == "server changed\n"

    def test_multiline_clean_merge(self) -> None:
        base = "# Title\n\nParagraph one.\n\nParagraph two.\n"
        server = "# Title\n\nParagraph one (server edit).\n\nParagraph two.\n"
        client = "# Title\n\nParagraph one.\n\nParagraph two (client edit).\n"
        merged, has_conflicts = merge_file(base, server, client)
        assert not has_conflicts
        assert "server edit" in merged
        assert "client edit" in merged
