"""Post service: queries and CRUD operations."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from backend.models.label import PostLabelCache
from backend.models.post import PostCache
from backend.schemas.post import (
    PostDetail,
    PostListResponse,
    PostSummary,
    SearchResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _post_labels(session: AsyncSession, post_id: int) -> list[str]:
    """Get label IDs for a post."""
    stmt = select(PostLabelCache.label_id).where(PostLabelCache.post_id == post_id)
    result = await session.execute(stmt)
    return [r[0] for r in result.all()]


async def list_posts(
    session: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 20,
    label: str | None = None,
    labels: list[str] | None = None,
    label_mode: str = "or",
    author: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    include_drafts: bool = False,
    sort: str = "created_at",
    order: str = "desc",
) -> PostListResponse:
    """List posts with pagination and filtering."""
    stmt = select(PostCache)

    if not include_drafts:
        stmt = stmt.where(PostCache.is_draft == False)  # noqa: E712

    if author:
        stmt = stmt.where(PostCache.author == author)

    if from_date:
        stmt = stmt.where(PostCache.created_at >= from_date)

    if to_date:
        # Include the entire day by comparing against next day
        stmt = stmt.where(PostCache.created_at < to_date + "T23:59:59")

    # Label filtering
    label_ids: list[str] = []
    if label:
        label_ids.append(label)
    if labels:
        label_ids.extend(labels)

    if label_ids:
        # Get all descendant labels for each requested label
        from backend.services.label_service import get_label_descendant_ids

        if label_mode == "and":
            # AND mode: post must have ALL specified labels (or descendants)
            for lid in label_ids:
                descendants = await get_label_descendant_ids(session, lid)
                stmt = stmt.where(
                    PostCache.id.in_(
                        select(PostLabelCache.post_id).where(
                            PostLabelCache.label_id.in_(descendants)
                        )
                    )
                )
        else:
            # OR mode (default): post must have ANY specified label
            all_label_ids: set[str] = set()
            for lid in label_ids:
                descendants = await get_label_descendant_ids(session, lid)
                all_label_ids.update(descendants)

            stmt = stmt.where(
                PostCache.id.in_(
                    select(PostLabelCache.post_id).where(
                        PostLabelCache.label_id.in_(all_label_ids)
                    )
                )
            )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # Sort (validated against allowlist)
    allowed_sorts = {"created_at", "modified_at", "title", "author"}
    if sort not in allowed_sorts:
        sort = "created_at"
    sort_col = getattr(PostCache, sort, PostCache.created_at)
    if order == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # Paginate
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await session.execute(stmt)
    posts = result.scalars().all()

    # Batch load labels for all posts in one query
    post_ids = [post.id for post in posts]
    labels_map: dict[int, list[str]] = {pid: [] for pid in post_ids}
    if post_ids:
        label_stmt = select(PostLabelCache.post_id, PostLabelCache.label_id).where(
            PostLabelCache.post_id.in_(post_ids)
        )
        label_result = await session.execute(label_stmt)
        for row in label_result.all():
            labels_map[row[0]].append(row[1])

    summaries: list[PostSummary] = []
    for post in posts:
        summaries.append(
            PostSummary(
                id=post.id,
                file_path=post.file_path,
                title=post.title,
                author=post.author,
                created_at=post.created_at,
                modified_at=post.modified_at,
                is_draft=post.is_draft,
                excerpt=post.excerpt,
                labels=labels_map.get(post.id, []),
            )
        )

    total_pages = max(1, math.ceil(total / per_page))

    return PostListResponse(
        posts=summaries,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


async def get_post(
    session: AsyncSession, file_path: str, *, include_content: bool = False
) -> PostDetail | None:
    """Get a single post by file path."""
    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if post is None:
        return None

    post_label_ids = await _post_labels(session, post.id)

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=post.created_at,
        modified_at=post.modified_at,
        is_draft=post.is_draft,
        excerpt=post.excerpt,
        labels=post_label_ids,
        rendered_html=post.rendered_html or "",
        content=None,  # Only provided when authenticated
    )


async def search_posts(
    session: AsyncSession, query: str, *, limit: int = 20
) -> list[SearchResult]:
    """Full-text search for posts."""
    stmt = text("""
        SELECT p.id, p.file_path, p.title, p.excerpt, p.created_at,
               rank
        FROM posts_fts fts
        JOIN posts_cache p ON fts.rowid = p.id
        WHERE posts_fts MATCH :query
        AND p.is_draft = 0
        ORDER BY rank
        LIMIT :limit
    """)
    result = await session.execute(stmt, {"query": query, "limit": limit})
    return [
        SearchResult(
            id=r[0],
            file_path=r[1],
            title=r[2],
            excerpt=r[3],
            created_at=r[4],
            rank=float(r[5]) if r[5] else 0.0,
        )
        for r in result.all()
    ]


async def get_posts_by_label(
    session: AsyncSession, label_id: str, *, page: int = 1, per_page: int = 20
) -> PostListResponse:
    """Get posts for a specific label (including descendants)."""
    return await list_posts(session, page=page, per_page=per_page, label=label_id)
