"""Tests for GitService.merge_file_content using git merge-file."""

from __future__ import annotations

from pathlib import Path

from backend.services.git_service import GitService


class TestMergeFileContent:
    def test_clean_merge_non_overlapping(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "line1\nline2\nline3\n"
        ours = "line1 changed\nline2\nline3\n"
        theirs = "line1\nline2\nline3 changed\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert "line1 changed" in merged
        assert "line3 changed" in merged

    def test_conflict_overlapping(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "line1\noriginal\nline3\n"
        ours = "line1\nours-version\nline3\n"
        theirs = "line1\ntheirs-version\nline3\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert conflicted

    def test_identical_changes(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "original\n"
        ours = "same change\n"
        theirs = "same change\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert merged == "same change\n"

    def test_one_side_unchanged(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "original\n"
        ours = "original\n"
        theirs = "changed\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert merged == "changed\n"
