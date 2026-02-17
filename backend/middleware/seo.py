"""SEO middleware: inject Open Graph meta tags into HTML responses for post pages."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class SEOMiddleware(BaseHTTPMiddleware):
    """Inject OG meta tags into the SPA HTML for crawlers and link previews.

    For /post/* routes, fetches post metadata from the cache and injects
    og:title, og:description, og:url, og:type, and twitter:card tags.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        response = await call_next(request)

        # Only process HTML responses for post pages
        path = request.url.path
        content_type = response.headers.get("content-type", "")

        if not path.startswith("/post/") or "text/html" not in content_type:
            return response

        # Read the response body
        body = b""
        async for chunk in response.body_iterator:  # type: ignore[union-attr]
            if isinstance(chunk, str):
                body += chunk.encode("utf-8")
            else:
                body += chunk

        body_str = body.decode("utf-8")

        # Extract post path from URL
        post_path = path.removeprefix("/post/")

        # Try to get post metadata from the database
        try:
            app = request.app
            session_factory = app.state.session_factory

            async with session_factory() as session:
                from sqlalchemy import select

                from backend.models.post import PostCache

                stmt = select(PostCache).where(PostCache.file_path == post_path)
                result = await session.execute(stmt)
                post = result.scalar_one_or_none()

                if post:
                    site_url = str(request.base_url).rstrip("/")
                    post_url = f"{site_url}/post/{post.file_path}"

                    meta_tags = _build_meta_tags(
                        title=post.title,
                        description=post.excerpt or "",
                        url=post_url,
                        author=post.author,
                    )

                    # Inject meta tags before </head>
                    body_str = body_str.replace("</head>", f"{meta_tags}\n</head>")
        except Exception:
            logger.warning("SEO meta tag injection failed for %s", path, exc_info=True)

        # Build new response with correct Content-Length
        encoded = body_str.encode("utf-8")
        headers = dict(response.headers)
        headers["content-length"] = str(len(encoded))
        return Response(
            content=encoded,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


def _build_meta_tags(
    title: str,
    description: str,
    url: str,
    author: str | None = None,
) -> str:
    """Build Open Graph and Twitter Card meta tags."""
    t = html.escape(title)
    d = html.escape(description[:200])
    u = html.escape(url)

    tags = [
        f'<meta property="og:title" content="{t}" />',
        f'<meta property="og:description" content="{d}" />',
        f'<meta property="og:url" content="{u}" />',
        '<meta property="og:type" content="article" />',
        '<meta name="twitter:card" content="summary" />',
        f'<meta name="twitter:title" content="{t}" />',
        f'<meta name="twitter:description" content="{d}" />',
    ]

    if author:
        a = html.escape(author)
        tags.append(f'<meta name="author" content="{a}" />')

    # Also set the page <title>
    tags.append(f"<title>{t}</title>")

    return "\n".join(tags)
