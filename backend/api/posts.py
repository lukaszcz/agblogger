"""Post API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    get_content_manager,
    get_git_service,
    get_session,
    require_auth,
)
from backend.filesystem.content_manager import ContentManager, get_directory_labels, hash_content
from backend.filesystem.frontmatter import PostData, extract_title, generate_excerpt, serialize_post
from backend.models.label import LabelCache, PostLabelCache
from backend.models.post import PostCache
from backend.models.user import User
from backend.pandoc.renderer import render_markdown
from backend.schemas.post import (
    PostCreate,
    PostDetail,
    PostEditResponse,
    PostListResponse,
    PostUpdate,
    SearchResult,
)
from backend.services.datetime_service import format_iso, now_utc
from backend.services.git_service import GitService
from backend.services.post_service import get_post, list_posts, search_posts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["posts"])

_FTS_DELETE_SQL = text(
    "INSERT INTO posts_fts(posts_fts, rowid, title, excerpt, content) "
    "VALUES ('delete', :rowid, :title, :excerpt, :content)"
)

_FTS_INSERT_SQL = text(
    "INSERT INTO posts_fts(rowid, title, excerpt, content) "
    "VALUES (:rowid, :title, :excerpt, :content)"
)


def _merge_post_labels(file_path: str, explicit_labels: list[str]) -> tuple[list[str], set[str]]:
    """Combine explicit labels with implicit directory labels."""
    directory_labels = set(get_directory_labels(file_path))
    merged = list(dict.fromkeys([*explicit_labels, *directory_labels]))
    return merged, directory_labels


async def _ensure_label_cache_entry(session: AsyncSession, label_id: str) -> None:
    """Ensure a label exists in cache tables, creating an implicit label if needed."""
    existing = await session.get(LabelCache, label_id)
    if existing is None:
        session.add(LabelCache(id=label_id, names="[]", is_implicit=True))
        await session.flush()


async def _replace_post_labels(
    session: AsyncSession,
    *,
    post_id: int,
    file_path: str,
    explicit_labels: list[str],
) -> list[str]:
    """Replace all cached label mappings for a post."""
    await session.execute(delete(PostLabelCache).where(PostLabelCache.post_id == post_id))
    merged_labels, directory_labels = _merge_post_labels(file_path, explicit_labels)
    for label_id in merged_labels:
        await _ensure_label_cache_entry(session, label_id)
        source = "directory" if label_id in directory_labels else "frontmatter"
        session.add(PostLabelCache(post_id=post_id, label_id=label_id, source=source))
    return merged_labels


async def _upsert_post_fts(
    session: AsyncSession,
    *,
    post_id: int,
    title: str,
    excerpt: str,
    content: str,
    old_title: str | None = None,
    old_excerpt: str | None = None,
    old_content: str | None = None,
) -> None:
    """Keep the full-text index row in sync with post cache mutations."""
    if old_title is not None and old_excerpt is not None and old_content is not None:
        await session.execute(
            _FTS_DELETE_SQL,
            {"rowid": post_id, "title": old_title, "excerpt": old_excerpt, "content": old_content},
        )
    await session.execute(
        _FTS_INSERT_SQL,
        {"rowid": post_id, "title": title, "excerpt": excerpt, "content": content},
    )


async def _delete_post_fts(
    session: AsyncSession, *, post_id: int, title: str, excerpt: str, content: str
) -> None:
    """Delete a post row from the full-text index.

    If the exact content doesn't match what was originally inserted, the FTS delete
    silently fails. Orphaned entries are cleaned up on the next rebuild_cache().
    """
    try:
        await session.execute(
            _FTS_DELETE_SQL,
            {"rowid": post_id, "title": title, "excerpt": excerpt, "content": content},
        )
    except OperationalError as exc:
        logger.warning(
            "FTS delete failed for post %d (will be cleaned up on next cache rebuild): %s",
            post_id,
            exc,
        )


@router.get("", response_model=PostListResponse)
async def list_posts_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    label: str | None = None,
    labels: str | None = None,
    label_mode: str | None = Query(None, alias="labelMode"),
    author: str | None = None,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    sort: str = "created_at",
    order: str = "desc",
) -> PostListResponse:
    """List posts with pagination and filtering."""
    label_list = labels.split(",") if labels else None
    return await list_posts(
        session,
        page=page,
        per_page=per_page,
        label=label,
        labels=label_list,
        label_mode=label_mode or "or",
        author=author,
        from_date=from_date,
        to_date=to_date,
        sort=sort,
        order=order,
    )


@router.get("/search", response_model=list[SearchResult])
async def search_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[SearchResult]:
    """Full-text search for posts."""
    return await search_posts(session, q, limit=limit)


@router.get("/{file_path:path}/edit", response_model=PostEditResponse)
async def get_post_for_edit(
    file_path: str,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> PostEditResponse:
    """Get structured post data for the editor."""
    post_data = content_manager.read_post(file_path)
    if post_data is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostEditResponse(
        file_path=file_path,
        body=post_data.content,
        labels=post_data.labels,
        is_draft=post_data.is_draft,
        created_at=format_iso(post_data.created_at),
        modified_at=format_iso(post_data.modified_at),
        author=post_data.author,
    )


@router.get("/{file_path:path}", response_model=PostDetail)
async def get_post_endpoint(
    file_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PostDetail:
    """Get a single post by file path."""
    post = await get_post(session, file_path)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("", response_model=PostDetail, status_code=201)
async def create_post_endpoint(
    body: PostCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Create a new post."""
    now = now_utc()
    author = user.display_name or user.username

    post_data = PostData(
        title=extract_title(body.body, body.file_path),
        content=body.body,
        raw_content="",
        created_at=now,
        modified_at=now,
        author=author,
        labels=body.labels,
        is_draft=body.is_draft,
        file_path=body.file_path,
    )

    excerpt = generate_excerpt(post_data.content)
    rendered_html = await render_markdown(post_data.content)

    serialized = serialize_post(post_data)
    post = PostCache(
        file_path=body.file_path,
        title=post_data.title,
        author=post_data.author,
        created_at=post_data.created_at,
        modified_at=post_data.modified_at,
        is_draft=post_data.is_draft,
        content_hash=hash_content(serialized),
        excerpt=excerpt,
        rendered_html=rendered_html,
    )
    session.add(post)
    await session.flush()
    cached_labels = await _replace_post_labels(
        session,
        post_id=post.id,
        file_path=body.file_path,
        explicit_labels=body.labels,
    )
    await _upsert_post_fts(
        session,
        post_id=post.id,
        title=post_data.title,
        excerpt=excerpt,
        content=post_data.content,
    )

    try:
        content_manager.write_post(body.file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", body.file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(post)
    git_service.try_commit(f"Create post: {body.file_path}")

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=format_iso(post.created_at),
        modified_at=format_iso(post.modified_at),
        is_draft=post.is_draft,
        excerpt=post.excerpt,
        labels=cached_labels,
        rendered_html=rendered_html,
    )


@router.put("/{file_path:path}", response_model=PostDetail)
async def update_post_endpoint(
    file_path: str,
    body: PostUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Update an existing post."""
    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # Read existing post to preserve created_at and author;
    # falls back to DB cache if file is missing
    existing_post_data = content_manager.read_post(file_path)
    if existing_post_data:
        created_at = existing_post_data.created_at
        author = existing_post_data.author
    else:
        logger.warning(
            "Post %s exists in DB cache but not on filesystem; using cached metadata", file_path
        )
        created_at = existing.created_at if existing.created_at else now_utc()
        author = existing.author or user.display_name or user.username

    now = now_utc()
    title = extract_title(body.body, file_path)

    post_data = PostData(
        title=title,
        content=body.body,
        raw_content="",
        created_at=created_at,
        modified_at=now,
        author=author,
        labels=body.labels,
        is_draft=body.is_draft,
        file_path=file_path,
    )

    serialized = serialize_post(post_data)
    excerpt = generate_excerpt(post_data.content)
    rendered_html = await render_markdown(post_data.content)
    previous_title = existing.title
    previous_excerpt = existing.excerpt or ""
    previous_content = existing_post_data.content if existing_post_data else ""

    existing.title = title
    existing.author = author
    existing.modified_at = now
    existing.is_draft = body.is_draft
    existing.content_hash = hash_content(serialized)
    existing.excerpt = excerpt
    existing.rendered_html = rendered_html
    cached_labels = await _replace_post_labels(
        session,
        post_id=existing.id,
        file_path=file_path,
        explicit_labels=body.labels,
    )
    await _upsert_post_fts(
        session,
        post_id=existing.id,
        title=title,
        excerpt=excerpt,
        content=post_data.content,
        old_title=previous_title,
        old_excerpt=previous_excerpt,
        old_content=previous_content,
    )

    await session.flush()

    try:
        content_manager.write_post(file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(existing)
    git_service.try_commit(f"Update post: {file_path}")

    return PostDetail(
        id=existing.id,
        file_path=existing.file_path,
        title=existing.title,
        author=existing.author,
        created_at=format_iso(existing.created_at),
        modified_at=format_iso(existing.modified_at),
        is_draft=existing.is_draft,
        excerpt=existing.excerpt,
        labels=cached_labels,
        rendered_html=existing.rendered_html or "",
    )


@router.delete("/{file_path:path}", status_code=204)
async def delete_post_endpoint(
    file_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
) -> None:
    """Delete a post."""
    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_post_data = content_manager.read_post(file_path)
    old_content = existing_post_data.content if existing_post_data else ""
    old_excerpt = existing.excerpt or generate_excerpt(old_content)

    try:
        content_manager.delete_post(file_path)
    except OSError as exc:
        logger.error("Failed to delete post file %s: %s", file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to delete post file") from exc

    await session.execute(delete(PostLabelCache).where(PostLabelCache.post_id == existing.id))
    await _delete_post_fts(
        session,
        post_id=existing.id,
        title=existing.title,
        excerpt=old_excerpt,
        content=old_content,
    )
    await session.delete(existing)
    await session.commit()
    git_service.try_commit(f"Delete post: {file_path}")
