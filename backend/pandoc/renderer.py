"""Pandoc-based markdown to HTML renderer."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import urllib.parse

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


def _fallback_render(markdown: str) -> str:
    """Basic fallback renderer when pandoc is unavailable.

    Handles headings, paragraphs, bold, italic, code, and links.
    """
    import html

    lines = markdown.split("\n")
    result: list[str] = []
    in_code_block = False
    code_lang = ""
    code_lines: list[str] = []
    in_paragraph = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_code_block:
                code_content = html.escape("\n".join(code_lines))
                cls = f' class="language-{code_lang}"' if code_lang else ""
                result.append(f"<pre><code{cls}>{code_content}</code></pre>")
                code_lines = []
                code_lang = ""
                in_code_block = False
            else:
                if in_paragraph:
                    result.append("</p>")
                    in_paragraph = False
                in_code_block = True
                code_lang = line.strip().removeprefix("```").strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            level = len(heading_match.group(1))
            text = _inline_format(html.escape(heading_match.group(2)))
            slug = re.sub(r"[^\w\s-]", "", heading_match.group(2).lower())
            slug = re.sub(r"[\s]+", "-", slug).strip("-")
            result.append(f'<h{level} id="{slug}">{text}</h{level}>')
            continue

        # Regular text
        formatted = _inline_format(html.escape(stripped))
        if not in_paragraph:
            result.append("<p>")
            in_paragraph = True
        result.append(formatted)

    if in_paragraph:
        result.append("</p>")

    return "\n".join(result)


def _inline_format(text: str) -> str:
    """Apply inline markdown formatting."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

    # Links (with scheme validation to prevent XSS)
    def _safe_link(m: re.Match[str]) -> str:
        href = m.group(2)
        parsed = urllib.parse.urlparse(href)
        if parsed.scheme and parsed.scheme not in ("http", "https", "mailto"):
            return m.group(1)
        return f'<a href="{href}">{m.group(1)}</a>'

    text = re.sub(r"\[(.+?)\]\((.+?)\)", _safe_link, text)
    return text
