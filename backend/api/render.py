"""Render API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import require_auth
from backend.models.user import User
from backend.pandoc.renderer import render_markdown, rewrite_relative_urls

router = APIRouter(prefix="/api/render", tags=["render"])


class RenderRequest(BaseModel):
    """Markdown render request."""

    markdown: str = Field(max_length=500_000)
    file_path: str | None = None


class RenderResponse(BaseModel):
    """Rendered HTML response."""

    html: str


@router.post("/preview", response_model=RenderResponse)
async def preview(
    body: RenderRequest,
    _user: Annotated[User, Depends(require_auth)],
) -> RenderResponse:
    """Render markdown to HTML for preview."""
    html = await render_markdown(body.markdown)
    if body.file_path is not None:
        html = rewrite_relative_urls(html, body.file_path)
    return RenderResponse(html=html)
