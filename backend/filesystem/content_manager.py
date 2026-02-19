"""Content directory scanner and file manager."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.filesystem.frontmatter import PostData, generate_markdown_excerpt, parse_post
from backend.filesystem.toml_manager import (
    LabelDef,
    SiteConfig,
    parse_labels_config,
    parse_site_config,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ContentIndex:
    """Complete index of all content in the content directory."""

    site_config: SiteConfig
    labels: dict[str, LabelDef]
    posts: list[PostData]
    pages: dict[str, str]  # page_id -> rendered content (raw md for now)


def hash_content(content: str | bytes) -> str:
    """Compute SHA-256 hash of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def discover_posts(content_dir: Path) -> list[Path]:
    """Recursively discover all markdown files under content/posts/."""
    posts_dir = content_dir / "posts"
    if not posts_dir.exists():
        return []
    return sorted(posts_dir.rglob("*.md"))


def get_directory_labels(file_path: str) -> list[str]:
    """Extract implicit labels from directory path.

    A post at posts/cooking/best-pasta.md gets label 'cooking'.
    A post at posts/tech/swe/tips.md gets labels 'tech' and 'swe'.
    """
    parts = file_path.split("/")
    # Find 'posts' in path and take directories between posts/ and the file
    try:
        posts_idx = parts.index("posts")
    except ValueError:
        return []
    # Directories between posts/ and the file
    return parts[posts_idx + 1 : -1]


@dataclass
class ContentManager:
    """Manages reading and writing content files."""

    content_dir: Path
    _site_config: SiteConfig | None = field(default=None, repr=False)
    _labels: dict[str, LabelDef] | None = field(default=None, repr=False)

    @property
    def site_config(self) -> SiteConfig:
        """Get site configuration, loading if needed."""
        if self._site_config is None:
            self._site_config = parse_site_config(self.content_dir)
        return self._site_config

    def reload_config(self) -> None:
        """Reload site configuration from disk."""
        self._site_config = parse_site_config(self.content_dir)
        self._labels = parse_labels_config(self.content_dir)

    @property
    def labels(self) -> dict[str, LabelDef]:
        """Get label definitions, loading if needed."""
        if self._labels is None:
            self._labels = parse_labels_config(self.content_dir)
        return self._labels

    def scan_posts(self) -> list[PostData]:
        """Scan all posts from the content directory."""
        post_files = discover_posts(self.content_dir)
        posts: list[PostData] = []
        for post_path in post_files:
            rel_path = str(post_path.relative_to(self.content_dir))
            try:
                raw_content = post_path.read_text(encoding="utf-8")
                post_data = parse_post(
                    raw_content,
                    file_path=rel_path,
                    default_tz=self.site_config.timezone,
                    default_author=self.site_config.default_author,
                )
            except Exception:
                logger.exception("Skipping post %s due to parse error", rel_path)
                continue
            # Add directory-based implicit labels
            dir_labels = get_directory_labels(rel_path)
            for dl in dir_labels:
                if dl not in post_data.labels:
                    post_data.labels.append(dl)
            posts.append(post_data)
        return posts

    def _validate_path(self, rel_path: str) -> Path:
        """Validate that a relative path stays within the content directory.

        Raises ValueError if the resolved path escapes content_dir.
        """
        full_path = (self.content_dir / rel_path).resolve()
        if not full_path.is_relative_to(self.content_dir.resolve()):
            raise ValueError(f"Path traversal detected: {rel_path}")
        return full_path

    def read_post(self, rel_path: str) -> PostData | None:
        """Read a single post by relative path."""
        full_path = self._validate_path(rel_path)
        if not full_path.exists() or not full_path.is_file():
            return None
        raw_content = full_path.read_text(encoding="utf-8")
        post_data = parse_post(
            raw_content,
            file_path=rel_path,
            default_tz=self.site_config.timezone,
            default_author=self.site_config.default_author,
        )
        dir_labels = get_directory_labels(rel_path)
        for dl in dir_labels:
            if dl not in post_data.labels:
                post_data.labels.append(dl)
        return post_data

    def write_post(self, rel_path: str, post_data: PostData) -> None:
        """Write a post to disk."""
        from backend.filesystem.frontmatter import serialize_post

        full_path = self._validate_path(rel_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(serialize_post(post_data), encoding="utf-8")

    def delete_post(self, rel_path: str) -> bool:
        """Delete a post from disk. Returns True if file existed."""
        full_path = self._validate_path(rel_path)
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def read_page(self, page_id: str) -> str | None:
        """Read a top-level page by its ID."""
        for page_cfg in self.site_config.pages:
            if page_cfg.id == page_id and page_cfg.file:
                page_path = self.content_dir / page_cfg.file
                if page_path.exists():
                    return page_path.read_text(encoding="utf-8")
        return None

    def build_index(self) -> ContentIndex:
        """Build a complete content index from the filesystem."""
        posts = self.scan_posts()
        pages: dict[str, str] = {}
        for page_cfg in self.site_config.pages:
            if page_cfg.file:
                page_content = self.read_page(page_cfg.id)
                if page_content:
                    pages[page_cfg.id] = page_content
        return ContentIndex(
            site_config=self.site_config,
            labels=self.labels,
            posts=posts,
            pages=pages,
        )

    def get_markdown_excerpt(self, post_data: PostData) -> str:
        """Generate a markdown excerpt for a post (to be rendered via Pandoc)."""
        return generate_markdown_excerpt(post_data.content)

    def get_plain_excerpt(self, post_data: PostData, max_length: int = 200) -> str:
        """Generate a plain-text excerpt for cross-posting.

        Strips all markdown formatting including links, bold/italic,
        inline code, headings, code blocks, and images.
        """
        lines: list[str] = []
        in_code_block = False
        for line in post_data.content.split("\n"):
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
                stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
                stripped = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", stripped)
                stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
                stripped = re.sub(r"\$[^$]+\$", "", stripped)
                lines.append(stripped)
        text = " ".join(lines)
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", maxsplit=1)[0] + "..."
        return text
