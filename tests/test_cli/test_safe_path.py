"""Tests for _is_safe_local_path security boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli.sync_client import _is_safe_local_path

if TYPE_CHECKING:
    from pathlib import Path


class TestIsSafeLocalPath:
    def test_normal_path_resolves(self, tmp_path: Path):
        result = _is_safe_local_path(tmp_path, "posts/hello.md")
        assert result is not None
        assert result == (tmp_path / "posts" / "hello.md").resolve()

    def test_traversal_returns_none(self, tmp_path: Path):
        result = _is_safe_local_path(tmp_path, "../../etc/passwd")
        assert result is None

    def test_absolute_traversal_returns_none(self, tmp_path: Path):
        result = _is_safe_local_path(tmp_path, "../../etc/passwd")
        assert result is None
        result = _is_safe_local_path(tmp_path, "../../../etc/passwd")
        assert result is None

    def test_dotdot_in_middle_returns_none(self, tmp_path: Path):
        result = _is_safe_local_path(tmp_path, "posts/../../../etc/passwd")
        assert result is None

    def test_nested_path_resolves(self, tmp_path: Path):
        result = _is_safe_local_path(tmp_path, "posts/cooking/recipe.md")
        assert result is not None
        assert str(result).endswith("posts/cooking/recipe.md")
