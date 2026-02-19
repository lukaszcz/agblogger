"""Post API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    get_content_manager,
    get_session,
    require_auth,
)
from backend.filesystem.content_manager import ContentManager, hash_content
from backend.filesystem.frontmatter import (
    PostData,
    extract_title,
    generate_markdown_excerpt,
    serialize_post,
)
from backend.models.label import PostLabelCache
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
from backend.services.post_service import get_post, list_posts, search_posts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/posts", tags=["posts"])


async def _sync_post_labels(
    session: AsyncSession,
    post_id: int,
    labels: list[str],
    file_path: str,
) -> None:
    """Sync post_labels_cache for a post, replacing existing entries."""
    from backend.filesystem.content_manager import get_directory_labels

    await session.execute(delete(PostLabelCache).where(PostLabelCache.post_id == post_id))
    dir_labels = get_directory_labels(file_path)
    for label_id in labels:
        source = "directory" if label_id in dir_labels else "frontmatter"
        session.add(PostLabelCache(post_id=post_id, label_id=label_id, source=source))


async def _delete_post_fts(
    session: AsyncSession,
    post_id: int,
    old_title: str,
    old_content: str,
) -> None:
    """Remove FTS index entry using the special delete command.

    The posts_fts table uses content='posts_cache' but posts_cache has no
    'content' column, so plain DELETE FROM posts_fts fails.  The FTS5 special
    'delete' command accepts explicit old values and works correctly.
    """
    await session.execute(
        text(
            "INSERT INTO posts_fts(posts_fts, rowid, title, content) "
            "VALUES ('delete', :rowid, :title, :content)"
        ),
        {"rowid": post_id, "title": old_title, "content": old_content},
    )


async def _insert_post_fts(
    session: AsyncSession,
    post_id: int,
    title: str,
    content: str,
) -> None:
    """Insert a new FTS index entry for a post."""
    await session.execute(
        text("INSERT INTO posts_fts(rowid, title, content) VALUES (:rowid, :title, :content)"),
        {"rowid": post_id, "title": title, "content": content},
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
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Create a new post."""
    from sqlalchemy import select

    existing = await session.execute(select(PostCache).where(PostCache.file_path == body.file_path))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A post with this file path already exists")

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

    md_excerpt = generate_markdown_excerpt(post_data.content)
    rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
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
        rendered_excerpt=rendered_excerpt,
        rendered_html=rendered_html,
    )
    session.add(post)
    await session.flush()

    await _sync_post_labels(session, post.id, post_data.labels, body.file_path)
    await _insert_post_fts(session, post.id, post_data.title, post_data.content)

    try:
        content_manager.write_post(body.file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", body.file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(post)

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=format_iso(post.created_at),
        modified_at=format_iso(post.modified_at),
        is_draft=post.is_draft,
        rendered_excerpt=post.rendered_excerpt,
        labels=post_data.labels,
        rendered_html=rendered_html,
    )


@router.put("/{file_path:path}", response_model=PostDetail)
async def update_post_endpoint(
    file_path: str,
    body: PostUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Update an existing post."""
    from sqlalchemy import select

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
        old_content = existing_post_data.content
    else:
        logger.warning(
            "Post %s exists in DB cache but not on filesystem; using cached metadata", file_path
        )
        created_at = existing.created_at if existing.created_at else now_utc()
        author = existing.author or user.display_name or user.username
        old_content = ""

    # Remove old FTS entry before modifying PostCache
    await _delete_post_fts(session, existing.id, existing.title, old_content)

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
    md_excerpt = generate_markdown_excerpt(post_data.content)
    rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
    rendered_html = await render_markdown(post_data.content)

    existing.title = title
    existing.author = author
    existing.modified_at = now
    existing.is_draft = body.is_draft
    existing.content_hash = hash_content(serialized)
    existing.rendered_excerpt = rendered_excerpt
    existing.rendered_html = rendered_html

    await session.flush()

    await _sync_post_labels(session, existing.id, post_data.labels, file_path)
    await _insert_post_fts(session, existing.id, title, post_data.content)

    try:
        content_manager.write_post(file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(existing)

    return PostDetail(
        id=existing.id,
        file_path=existing.file_path,
        title=existing.title,
        author=existing.author,
        created_at=format_iso(existing.created_at),
        modified_at=format_iso(existing.modified_at),
        is_draft=existing.is_draft,
        rendered_excerpt=existing.rendered_excerpt,
        labels=post_data.labels,
        rendered_html=existing.rendered_html or "",
    )


@router.delete("/{file_path:path}", status_code=204)
async def delete_post_endpoint(
    file_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> None:
    """Delete a post."""
    from sqlalchemy import select

    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # Read post content for FTS cleanup before deleting the file
    old_post_data = content_manager.read_post(file_path)
    old_content = old_post_data.content if old_post_data else ""

    try:
        content_manager.delete_post(file_path)
    except OSError as exc:
        logger.error("Failed to delete post file %s: %s", file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to delete post file") from exc

    await _delete_post_fts(session, existing.id, existing.title, old_content)
    await session.delete(existing)
    await session.commit()
