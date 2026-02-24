"""Pandoc-based markdown to HTML renderer."""

from __future__ import annotations

import html
import logging
import posixpath
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urlparse as _urlparse

import httpx

if TYPE_CHECKING:
    from backend.pandoc.server import PandocServer

logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """Raised when pandoc rendering fails (server unreachable, timeout, parse error)."""


_server: PandocServer | None = None
_http_client: httpx.AsyncClient | None = None

_SAFE_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9:_-]*$")
_VOID_TAGS: frozenset[str] = frozenset({"br", "hr", "img"})
_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "blockquote",
        "br",
        "code",
        "dd",
        "del",
        "div",
        "dl",
        "dt",
        "em",
        "figcaption",
        "figure",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "img",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "samp",
        "section",
        "span",
        "strong",
        "sub",
        "sup",
        "summary",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
        "var",
    }
)
_GLOBAL_ALLOWED_ATTRS: frozenset[str] = frozenset({"class", "id"})
_TAG_ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title"}),
    "img": frozenset({"alt", "src", "title"}),
    "td": frozenset({"colspan", "rowspan"}),
    "th": frozenset({"colspan", "rowspan"}),
}


def _is_safe_url(url_value: str, *, allow_non_http: bool) -> bool:
    """Validate URL values for href/src attributes."""
    value = url_value.strip()
    if not value:
        return False
    if value.startswith(("#", "/", "./", "../")):
        return True
    if value.startswith("//"):
        return False

    parsed = _urlparse(value)
    if not parsed.scheme:
        return True

    allowed_schemes = {"http", "https"}
    if allow_non_http:
        allowed_schemes.update({"mailto", "tel"})
    return parsed.scheme.lower() in allowed_schemes


class _HtmlSanitizer(HTMLParser):
    """Allowlist-based HTML sanitizer for Pandoc output."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._parts: list[str] = []
        self._open_tags: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name not in _ALLOWED_TAGS:
            self._open_tags.append(None)
            return

        rendered_attrs = self._sanitize_attrs(tag_name, attrs)
        attrs_text = "".join(
            f' {name}="{html.escape(value, quote=True)}"' for name, value in rendered_attrs
        )
        self._parts.append(f"<{tag_name}{attrs_text}>")
        self._open_tags.append(tag_name)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if not self._open_tags:
            return
        open_tag = self._open_tags.pop()
        if open_tag == tag_name and tag_name not in _VOID_TAGS:
            self._parts.append(f"</{tag_name}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name not in _ALLOWED_TAGS:
            return
        rendered_attrs = self._sanitize_attrs(tag_name, attrs)
        attrs_text = "".join(
            f' {name}="{html.escape(value, quote=True)}"' for name, value in rendered_attrs
        )
        self._parts.append(f"<{tag_name}{attrs_text} />")

    def handle_data(self, data: str) -> None:
        self._parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def get_sanitized_html(self) -> str:
        return "".join(self._parts)

    def _sanitize_attrs(
        self,
        tag_name: str,
        attrs: list[tuple[str, str | None]],
    ) -> list[tuple[str, str]]:
        allowed_attrs = _GLOBAL_ALLOWED_ATTRS | _TAG_ALLOWED_ATTRS.get(tag_name, frozenset())
        sanitized: list[tuple[str, str]] = []

        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            if raw_value is None or name not in allowed_attrs:
                continue

            value = raw_value.strip()
            if name == "href" and not _is_safe_url(value, allow_non_http=True):
                continue
            if name == "src" and not _is_safe_url(value, allow_non_http=False):
                continue
            if name == "id" and not _SAFE_ID_RE.fullmatch(value):
                continue

            sanitized.append((name, value))
        return sanitized


def _sanitize_html(rendered_html: str) -> str:
    """Sanitize rendered HTML output to prevent script execution."""
    sanitizer = _HtmlSanitizer()
    sanitizer.feed(rendered_html)
    sanitizer.close()
    return sanitizer.get_sanitized_html()


_RENDER_TIMEOUT = 10.0


def init_renderer(server: PandocServer) -> None:
    """Initialize the renderer with a running PandocServer instance."""
    global _server, _http_client
    _server = server
    _http_client = httpx.AsyncClient(timeout=_RENDER_TIMEOUT)


async def close_renderer() -> None:
    """Close the httpx client and reset module state."""
    global _server, _http_client
    if _http_client is not None:
        await _http_client.aclose()
    _server = None
    _http_client = None


async def render_markdown(markdown: str) -> str:
    """Render markdown to HTML using the pandoc server HTTP API.

    Uses GFM + KaTeX math + syntax highlighting.
    Raises RuntimeError if the renderer is not initialized or pandoc fails.
    """
    if _server is None or _http_client is None:
        raise RuntimeError(
            "Pandoc renderer not initialized. Call init_renderer() during app startup."
        )

    payload = {
        "text": markdown,
        "from": "gfm+tex_math_dollars+footnotes+raw_html",
        "to": "html5",
        "html-math-method": {"method": "katex"},
        "highlight-style": "pygments",
        "wrap": "none",
    }
    headers = {"Accept": "application/json"}

    try:
        response = await _http_client.post(f"{_server.base_url}/", json=payload, headers=headers)
    except httpx.ConnectError:
        logger.warning("Pandoc server connection failed, attempting restart")
        await _server.ensure_running()
        try:
            response = await _http_client.post(
                f"{_server.base_url}/", json=payload, headers=headers
            )
        except httpx.HTTPError as retry_exc:
            raise RenderError(f"Pandoc server unreachable after restart: {retry_exc}") from None
    except httpx.ReadTimeout:
        raise RenderError(f"Pandoc rendering timed out after {_RENDER_TIMEOUT}s") from None

    try:
        data = response.json()
    except ValueError:
        raise RenderError(
            f"Pandoc server returned non-JSON response (HTTP {response.status_code})"
        ) from None
    if "error" in data:
        raise RenderError(f"Pandoc rendering error: {str(data['error'])[:200]}")

    output = data.get("output", "")
    sanitized = _sanitize_html(output)
    return _add_heading_anchors(sanitized)


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


_SKIP_PREFIXES = ("/", "#", "data:", "http:", "https:", "mailto:", "tel:")


def rewrite_relative_urls(html: str, file_path: str) -> str:
    """Rewrite relative src and href attributes in HTML to absolute /api/content/ paths.

    Args:
        html: Rendered HTML string.
        file_path: Post's path relative to the content directory,
            e.g. ``posts/2026-02-20-my-post/index.md``.

    Returns:
        HTML with relative URLs resolved to ``/api/content/{resolved_path}``.
    """
    base_dir = posixpath.dirname(file_path)

    def _replace(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote = match.group(2)
        value = match.group(3)

        if any(value.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return match.group(0)

        # Strip leading ./ if present
        relative = value.removeprefix("./")

        resolved = posixpath.normpath(posixpath.join(base_dir, relative))
        # Don't produce URLs that escape the content root
        if resolved.startswith(".."):
            return match.group(0)
        return f"{attr}={quote}/api/content/{resolved}{quote}"

    return re.sub(r"""(src|href)=(["'])([^"']*)\2""", _replace, html)
