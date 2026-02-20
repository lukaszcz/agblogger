"""Pandoc-based markdown to HTML renderer."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess

logger = logging.getLogger(__name__)


async def render_markdown(markdown: str) -> str:
    """Render markdown to HTML using pandoc.

    Uses GFM + KaTeX math + syntax highlighting.
    Raises RuntimeError if pandoc is not installed or fails.
    """
    return await asyncio.to_thread(_render_markdown_sync, markdown)


def _render_markdown_sync(markdown: str) -> str:
    """Synchronous pandoc rendering (runs in thread pool)."""
    try:
        result = subprocess.run(
            [
                "pandoc",
                "-f",
                "gfm+tex_math_dollars+footnotes+raw_html",
                "-t",
                "html5",
                "--katex",
                "--highlight-style=pygments",
                "--wrap=none",
            ],
            input=markdown,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            html = result.stdout
            html = _add_heading_anchors(html)
            return html
        logger.error("Pandoc failed (rc=%d): %s", result.returncode, result.stderr)
        raise RuntimeError(
            f"Pandoc rendering failed with return code {result.returncode}: {result.stderr[:200]}"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Pandoc is not installed. Install pandoc to enable markdown rendering. "
            "See https://pandoc.org/installing.html"
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("Pandoc rendering timed out after 30 seconds") from None


def _add_heading_anchors(html: str) -> str:
    """Add id attributes to headings for anchor links."""

    def _add_id(match: re.Match[str]) -> str:
        tag = match.group(1)
        attrs = match.group(2)
        content = match.group(3)
        if 'id="' in attrs:
            return match.group(0)
        slug = re.sub(r"[^\w\s-]", "", content.lower())
        slug = re.sub(r"[\s]+", "-", slug).strip("-")
        return f'<{tag}{attrs} id="{slug}">{content}</{tag}>'

    return re.sub(
        r"<(h[1-6])([^>]*)>(.*?)</\1>",
        _add_id,
        html,
        flags=re.DOTALL,
    )
