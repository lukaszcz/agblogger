"""Tests for the pandoc renderer module."""

from __future__ import annotations

import inspect
from unittest.mock import patch


class TestRendererModule:
    def test_no_fallback_render_function(self) -> None:
        """_fallback_render should not exist — it was dead code."""
        from backend.pandoc import renderer

        assert not hasattr(renderer, "_fallback_render"), (
            "_fallback_render is dead code and should be removed"
        )

    def test_no_inline_format_function(self) -> None:
        """_inline_format should not exist — it was only used by _fallback_render."""
        from backend.pandoc import renderer

        assert not hasattr(renderer, "_inline_format"), (
            "_inline_format is dead code and should be removed"
        )

    def test_render_markdown_is_async(self) -> None:
        """render_markdown should be an async function."""
        from backend.pandoc.renderer import render_markdown

        assert inspect.iscoroutinefunction(render_markdown)

    def test_module_public_functions(self) -> None:
        """The public functions should be render_markdown and rewrite_relative_urls."""
        from backend.pandoc import renderer

        public_functions = sorted(
            name
            for name, obj in inspect.getmembers(renderer, inspect.isfunction)
            if not name.startswith("_")
        )
        assert public_functions == ["render_markdown", "rewrite_relative_urls"]

    def test_missing_pandoc_raises_runtime_error(self) -> None:
        """FileNotFoundError from subprocess should become RuntimeError."""
        from backend.pandoc.renderer import _render_markdown_sync

        with patch("subprocess.run", side_effect=FileNotFoundError("No such file")):
            try:
                _render_markdown_sync("# Hello")
                raise AssertionError("Expected RuntimeError was not raised")
            except RuntimeError as exc:
                assert "Pandoc is not installed" in str(exc)
