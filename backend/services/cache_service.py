"""Database cache regeneration from filesystem."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, text

from backend.filesystem.content_manager import ContentManager, hash_content
from backend.models.label import LabelCache, LabelParentCache, PostLabelCache
from backend.models.post import PostCache
from backend.pandoc.renderer import render_markdown
from backend.services.datetime_service import format_datetime

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def rebuild_cache(session: AsyncSession, content_manager: ContentManager) -> int:
    """Rebuild all cache tables from filesystem.

    Returns the number of posts indexed.
    """
    # Clear existing cache
    await session.execute(delete(PostLabelCache))
    await session.execute(delete(LabelParentCache))
    await session.execute(delete(PostCache))
    await session.execute(delete(LabelCache))

    # Drop and recreate FTS table
    await session.execute(text("DROP TABLE IF EXISTS posts_fts"))
    await session.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
            "title, excerpt, content, content='posts_cache', content_rowid='id')"
        )
    )

    # Load labels from config
    labels_config = content_manager.labels
    for label_id, label_def in labels_config.items():
        label = LabelCache(
            id=label_id,
            names=json.dumps(label_def.names),
            is_implicit=False,
        )
        session.add(label)

    await session.flush()

    # Add parent edges
    for label_id, label_def in labels_config.items():
        for parent_id in label_def.parents:
            # Ensure parent exists
            if parent_id not in labels_config:
                parent_label = LabelCache(id=parent_id, names="[]", is_implicit=True)
                session.add(parent_label)
                await session.flush()
            edge = LabelParentCache(label_id=label_id, parent_id=parent_id)
            session.add(edge)

    await session.flush()

    # Scan and index posts
    posts = content_manager.scan_posts()
    post_count = 0

    for post_data in posts:
        content_h = hash_content(post_data.raw_content)
        excerpt = content_manager.get_excerpt(post_data)

        # Render HTML
        rendered_html = render_markdown(post_data.content)

        post = PostCache(
            file_path=post_data.file_path,
            title=post_data.title,
            author=post_data.author,
            created_at=format_datetime(post_data.created_at),
            modified_at=format_datetime(post_data.modified_at),
            is_draft=post_data.is_draft,
            content_hash=content_h,
            excerpt=excerpt,
            rendered_html=rendered_html,
        )
        session.add(post)
        await session.flush()

        # Index in FTS
        await session.execute(
            text(
                "INSERT INTO posts_fts(rowid, title, excerpt, content) "
                "VALUES (:rowid, :title, :excerpt, :content)"
            ),
            {
                "rowid": post.id,
                "title": post_data.title,
                "excerpt": excerpt,
                "content": post_data.content,
            },
        )

        # Add label associations
        for label_id in post_data.labels:
            # Ensure label exists
            existing = await session.get(LabelCache, label_id)
            if not existing:
                implicit_label = LabelCache(id=label_id, names="[]", is_implicit=True)
                session.add(implicit_label)
                await session.flush()

            source = "frontmatter"
            # Check if this label came from directory
            from backend.filesystem.content_manager import get_directory_labels

            dir_labels = get_directory_labels(post_data.file_path)
            if label_id in dir_labels and label_id not in [
                lbl for lbl in post_data.labels if lbl not in dir_labels
            ]:
                source = "directory"

            post_label = PostLabelCache(
                post_id=post.id,
                label_id=label_id,
                source=source,
            )
            session.add(post_label)

        post_count += 1

    await session.commit()
    logger.info("Cache rebuilt: %d posts indexed", post_count)
    return post_count


async def ensure_tables(session: AsyncSession) -> None:
    """Create all tables if they don't exist (for development)."""
    from backend.models.base import Base

    conn = await session.connection()
    await conn.run_sync(Base.metadata.create_all)

    # Create FTS table
    await session.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
            "title, excerpt, content, content='posts_cache', content_rowid='id')"
        )
    )
    await session.commit()
