"""Render API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import require_auth
from backend.models.user import User
from backend.pandoc.renderer import render_markdown

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/render", tags=["render"])


class RenderRequest(BaseModel):
    """Markdown render request."""

    markdown: str = Field(max_length=500_000)


class RenderResponse(BaseModel):
    """Rendered HTML response."""

    html: str


@router.post("/preview", response_model=RenderResponse)
async def preview(
    body: RenderRequest,
    _user: Annotated[User, Depends(require_auth)],
) -> RenderResponse:
    """Render markdown to HTML for preview."""
    try:
        html = await render_markdown(body.markdown)
    except RuntimeError as exc:
        logger.error("Pandoc rendering failed in preview: %s", exc)
        raise HTTPException(status_code=502, detail="Markdown rendering failed") from exc
    return RenderResponse(html=html)
