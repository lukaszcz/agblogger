"""Label API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_content_manager, get_session, require_auth
from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import LabelDef, write_labels_config
from backend.models.user import User
from backend.schemas.label import (
    LabelCreate,
    LabelDeleteResponse,
    LabelGraphResponse,
    LabelResponse,
    LabelUpdate,
)
from backend.schemas.post import PostListResponse
from backend.services.label_service import (
    create_label,
    delete_label,
    get_all_labels,
    get_label,
    get_label_graph,
    update_label,
)
from backend.services.post_service import get_posts_by_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/labels", tags=["labels"])


@router.get("", response_model=list[LabelResponse])
async def list_labels(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[LabelResponse]:
    """List all labels."""
    return await get_all_labels(session)


@router.get("/graph", response_model=LabelGraphResponse)
async def label_graph(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LabelGraphResponse:
    """Get the full label DAG for graph visualization."""
    return await get_label_graph(session)


@router.post("", response_model=LabelResponse, status_code=201)
async def create_label_endpoint(
    body: LabelCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelResponse:
    """Create a new label."""
    # Validate parents exist
    for parent_id in body.parents:
        parent = await get_label(session, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail=f"Parent label '{parent_id}' not found")

    try:
        result = await create_label(session, body.id, body.names or None, body.parents or None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=409, detail="Label already exists")

    # Write to labels.toml so the label survives cache rebuilds (the DB is regenerable from disk)
    labels = dict(content_manager.labels)
    labels[body.id] = LabelDef(
        id=body.id,
        names=body.names if body.names else [body.id],
        parents=body.parents,
    )
    try:
        write_labels_config(content_manager.content_dir, labels)
        content_manager.reload_config()
    except Exception as exc:
        logger.error("Failed to write labels.toml for label %s: %s", body.id, exc)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to persist label to filesystem"
        ) from exc

    await session.commit()
    return result


@router.put("/{label_id}", response_model=LabelResponse)
async def update_label_endpoint(
    label_id: str,
    body: LabelUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelResponse:
    """Update a label's names and parents."""
    existing = await get_label(session, label_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Label not found")

    # Validate parents exist
    for parent_id in body.parents:
        parent = await get_label(session, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail=f"Parent label '{parent_id}' not found")

    try:
        result = await update_label(session, label_id, body.names, body.parents)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    assert result is not None  # already checked existence above

    # Persist to labels.toml
    labels = dict(content_manager.labels)
    labels[label_id] = LabelDef(id=label_id, names=body.names, parents=body.parents)
    try:
        write_labels_config(content_manager.content_dir, labels)
        content_manager.reload_config()
    except Exception as exc:
        logger.error("Failed to write labels.toml for label %s: %s", label_id, exc)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to persist label to filesystem"
        ) from exc

    await session.commit()
    return result


@router.delete("/{label_id}", response_model=LabelDeleteResponse)
async def delete_label_endpoint(
    label_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelDeleteResponse:
    """Delete a label."""
    deleted = await delete_label(session, label_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Label not found")

    # Remove from labels.toml
    labels = dict(content_manager.labels)
    labels.pop(label_id, None)
    try:
        write_labels_config(content_manager.content_dir, labels)
        content_manager.reload_config()
    except Exception as exc:
        logger.error("Failed to update labels.toml after deleting %s: %s", label_id, exc)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to persist deletion to filesystem"
        ) from exc

    await session.commit()
    return LabelDeleteResponse(id=label_id)


@router.get("/{label_id}", response_model=LabelResponse)
async def get_label_endpoint(
    label_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LabelResponse:
    """Get a single label by ID."""
    label = await get_label(session, label_id)
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    return label


@router.get("/{label_id}/posts", response_model=PostListResponse)
async def label_posts(
    label_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PostListResponse:
    """Get posts for a specific label (including descendants)."""
    return await get_posts_by_label(session, label_id, page=page, per_page=per_page)
