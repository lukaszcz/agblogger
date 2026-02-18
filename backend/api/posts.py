"""Post API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import (
    get_content_manager,
    get_session,
    require_auth,
)
from backend.filesystem.content_manager import ContentManager, hash_content
from backend.filesystem.frontmatter import parse_post
from backend.models.post import PostCache
from backend.pandoc.renderer import render_markdown
from backend.schemas.post import (
    PostCreate,
    PostDetail,
    PostListResponse,
    PostUpdate,
    SearchResult,
)
from backend.services.datetime_service import format_datetime, now_utc
from backend.services.post_service import get_post, list_posts, search_posts

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.user import User

router = APIRouter(prefix="/api/posts", tags=["posts"])


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
    # Parse the content
    post_data = parse_post(
        body.content,
        file_path=body.file_path,
        default_tz=content_manager.site_config.timezone,
        default_author=content_manager.site_config.default_author,
    )

    from backend.filesystem.frontmatter import generate_excerpt

    excerpt = generate_excerpt(post_data.content)
    rendered_html = render_markdown(post_data.content)

    # DB first, then filesystem — rollback DB on filesystem failure
    post = PostCache(
        file_path=body.file_path,
        title=post_data.title,
        author=post_data.author,
        created_at=format_datetime(post_data.created_at),
        modified_at=format_datetime(post_data.modified_at),
        is_draft=post_data.is_draft,
        content_hash=hash_content(body.content),
        excerpt=excerpt,
        rendered_html=rendered_html,
    )
    session.add(post)
    await session.flush()

    try:
        content_manager.write_post(body.file_path, post_data)
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from None

    await session.commit()
    await session.refresh(post)

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=post.created_at,
        modified_at=post.modified_at,
        is_draft=post.is_draft,
        excerpt=post.excerpt,
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

    post_data = parse_post(
        body.content,
        file_path=file_path,
        default_tz=content_manager.site_config.timezone,
        default_author=content_manager.site_config.default_author,
    )
    post_data.modified_at = now_utc()

    from backend.filesystem.frontmatter import generate_excerpt

    existing.title = post_data.title
    existing.author = post_data.author
    existing.modified_at = format_datetime(post_data.modified_at)
    existing.is_draft = post_data.is_draft
    existing.content_hash = hash_content(body.content)
    existing.excerpt = generate_excerpt(post_data.content)
    existing.rendered_html = render_markdown(post_data.content)

    await session.flush()

    try:
        content_manager.write_post(file_path, post_data)
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from None

    await session.commit()
    await session.refresh(existing)

    return PostDetail(
        id=existing.id,
        file_path=existing.file_path,
        title=existing.title,
        author=existing.author,
        created_at=existing.created_at,
        modified_at=existing.modified_at,
        is_draft=existing.is_draft,
        excerpt=existing.excerpt,
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

    content_manager.delete_post(file_path)
    await session.delete(existing)
    await session.commit()
