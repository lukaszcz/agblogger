"""Tests for fallback renderer XSS prevention (Issue 4)."""

from __future__ import annotations

from backend.pandoc.renderer import _fallback_render, _inline_format


class TestFallbackRendererXSS:
    def test_safe_http_link(self) -> None:
        result = _inline_format("[Click](https://example.com)")
        assert '<a href="https://example.com">Click</a>' in result

    def test_safe_https_link(self) -> None:
        result = _inline_format("[Click](https://example.com)")
        assert "https://example.com" in result

    def test_safe_mailto_link(self) -> None:
        result = _inline_format("[Email](mailto:user@example.com)")
        assert '<a href="mailto:user@example.com">' in result

    def test_javascript_scheme_blocked(self) -> None:
        """Issue 4: javascript: links must be stripped."""
        result = _inline_format("[XSS](javascript:alert(1))")
        assert "javascript:" not in result
        assert "<a" not in result
        # The link text should still appear
        assert "XSS" in result

    def test_data_scheme_blocked(self) -> None:
        result = _inline_format("[XSS](data:text/html,<script>alert(1)</script>)")
        assert "data:" not in result
        assert "<a" not in result

    def test_vbscript_scheme_blocked(self) -> None:
        result = _inline_format("[XSS](vbscript:MsgBox)")
        assert "vbscript:" not in result
        assert "<a" not in result

    def test_relative_link_allowed(self) -> None:
        """Links without a scheme (relative) should be allowed."""
        result = _inline_format("[Page](/about)")
        assert '<a href="/about">Page</a>' in result

    def test_full_fallback_render_with_xss_link(self) -> None:
        md = "Click [here](javascript:alert('xss')) for fun"
        html = _fallback_render(md)
        assert "javascript:" not in html
        assert "here" in html


class TestFallbackRendererBasic:
    def test_headings(self) -> None:
        html = _fallback_render("# Hello World")
        assert "<h1" in html
        assert "Hello World" in html

    def test_code_blocks(self) -> None:
        html = _fallback_render("```python\nprint('hi')\n```")
        assert "<pre>" in html
        assert "<code" in html
        assert "print" in html

    def test_paragraphs(self) -> None:
        html = _fallback_render("Hello\n\nWorld")
        assert "<p>" in html

    def test_inline_formatting(self) -> None:
        html = _fallback_render("This is **bold** and *italic*")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html


class TestPandocMissingRaises:
    def test_missing_pandoc_raises_runtime_error(self) -> None:
        from unittest.mock import patch

        from backend.pandoc.renderer import _render_markdown_sync

        with patch("subprocess.run", side_effect=FileNotFoundError("No such file")):
            try:
                _render_markdown_sync("# Hello")
                raise AssertionError("Expected RuntimeError was not raised")
            except RuntimeError as exc:
                assert "Pandoc is not installed" in str(exc)
