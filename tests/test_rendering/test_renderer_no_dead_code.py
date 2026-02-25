"""Tests for the pandoc renderer module."""

from __future__ import annotations

import inspect


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

    def test_render_markdown_excerpt_is_async(self) -> None:
        """render_markdown_excerpt should be an async function."""
        from backend.pandoc.renderer import render_markdown_excerpt

        assert inspect.iscoroutinefunction(render_markdown_excerpt)

    def test_module_public_functions(self) -> None:
        """Public API includes renderer lifecycle, full render, excerpt render, URL rewriting."""
        from backend.pandoc import renderer

        public_functions = sorted(
            name
            for name, obj in inspect.getmembers(renderer, inspect.isfunction)
            if not name.startswith("_")
        )
        assert public_functions == [
            "close_renderer",
            "init_renderer",
            "render_markdown",
            "render_markdown_excerpt",
            "rewrite_relative_urls",
        ]
