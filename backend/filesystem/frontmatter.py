"""YAML front matter parser/serializer for blog posts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import frontmatter

from backend.services.datetime_service import format_datetime, parse_datetime

RECOGNIZED_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "created_at",
        "modified_at",
        "author",
        "labels",
        "draft",
    }
)


@dataclass
class PostData:
    """Parsed blog post data."""

    title: str
    content: str
    raw_content: str
    created_at: datetime
    modified_at: datetime
    author: str | None = None
    labels: list[str] = field(default_factory=list)
    is_draft: bool = False
    file_path: str = ""


def extract_title(content: str, file_path: str = "") -> str:
    """Extract title from first # heading in markdown body.

    Falls back to deriving title from filename.
    """
    for line in content.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.removeprefix("# ").strip()
    # Fallback: derive from filename
    if file_path:
        name = file_path.rsplit("/", maxsplit=1)[-1]
        name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", name)  # strip date prefix
        name = name.removesuffix(".md")
        return name.replace("-", " ").replace("_", " ").title()
    return "Untitled"


def strip_leading_heading(content: str, title: str) -> str:
    """Remove the first # heading from content if it matches the title."""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            heading_text = stripped.removeprefix("# ").strip()
            if heading_text == title:
                rest = lines[i + 1 :]
                return "\n".join(rest)
        break  # First non-blank line isn't a heading — stop
    return content


def parse_labels(raw_labels: list[Any] | None) -> list[str]:
    """Parse label references from front matter.

    Labels are stored as '#label-id' strings.
    """
    if not raw_labels:
        return []
    result: list[str] = []
    for label in raw_labels:
        label_str = str(label).strip()
        if label_str.startswith("#"):
            result.append(label_str.removeprefix("#"))
        else:
            result.append(label_str)
    return result


def parse_post(
    raw_content: str,
    file_path: str = "",
    default_tz: str = "UTC",
    default_author: str = "",
) -> PostData:
    """Parse a markdown file with YAML front matter into PostData."""
    post = frontmatter.loads(raw_content)

    # Parse created_at
    raw_created = post.get("created_at")
    if raw_created is not None:
        if isinstance(raw_created, date) and not isinstance(raw_created, datetime):
            raw_created = datetime(raw_created.year, raw_created.month, raw_created.day)
        created_at = parse_datetime(raw_created, default_tz=default_tz)
    else:
        from backend.services.datetime_service import now_utc

        created_at = now_utc()

    # Parse modified_at
    raw_modified = post.get("modified_at")
    if raw_modified is not None:
        if isinstance(raw_modified, date) and not isinstance(raw_modified, datetime):
            raw_modified = datetime(raw_modified.year, raw_modified.month, raw_modified.day)
        modified_at = parse_datetime(raw_modified, default_tz=default_tz)
    else:
        modified_at = created_at

    # Title: prefer front matter, fall back to heading extraction
    fm_title = post.get("title")
    if fm_title and isinstance(fm_title, str) and fm_title.strip():
        title = fm_title.strip()
    else:
        title = extract_title(post.content, file_path)
    labels = parse_labels(post.get("labels"))
    author = post.get("author") or default_author or None
    is_draft = bool(post.get("draft", False))

    return PostData(
        title=title,
        content=post.content,
        raw_content=raw_content,
        created_at=created_at,
        modified_at=modified_at,
        author=author,
        labels=labels,
        is_draft=is_draft,
        file_path=file_path,
    )


def serialize_post(post_data: PostData) -> str:
    """Serialize PostData back to markdown with YAML front matter."""
    metadata: dict[str, Any] = {
        "title": post_data.title,
        "created_at": format_datetime(post_data.created_at),
        "modified_at": format_datetime(post_data.modified_at),
    }
    if post_data.author:
        metadata["author"] = post_data.author
    if post_data.labels:
        metadata["labels"] = [f"#{label}" for label in post_data.labels]
    if post_data.is_draft:
        metadata["draft"] = True

    body = strip_leading_heading(post_data.content, post_data.title)
    post = frontmatter.Post(body, **metadata)
    return str(frontmatter.dumps(post)) + "\n"


def generate_markdown_excerpt(content: str, max_length: int = 300) -> str:
    """Generate a markdown excerpt preserving inline formatting.

    Strips headings, code blocks, and images but preserves bold, italic,
    links, math expressions, and inline code so the excerpt can be rendered
    to HTML via Pandoc.  Visual truncation is handled by CSS line-clamp on
    the frontend; the backend provides enough rendered content.
    """
    lines: list[str] = []
    in_code_block = False
    for line in content.split("\n"):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if line.strip().startswith("#"):
            continue
        if line.strip().startswith("!["):
            continue
        stripped = line.strip()
        if stripped:
            lines.append(stripped)

    text = " ".join(lines)
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", maxsplit=1)[0] + "..."
    return text
