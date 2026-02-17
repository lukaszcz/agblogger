"""Label API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_session
from backend.schemas.label import LabelGraphResponse, LabelResponse
from backend.schemas.post import PostListResponse
from backend.services.label_service import get_all_labels, get_label, get_label_graph
from backend.services.post_service import get_posts_by_label

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
