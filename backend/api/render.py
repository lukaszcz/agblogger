"""Render API endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter

from backend.pandoc.renderer import render_markdown

router = APIRouter(prefix="/api/render", tags=["render"])


class RenderRequest(BaseModel):
    """Markdown render request."""

    markdown: str


class RenderResponse(BaseModel):
    """Rendered HTML response."""

    html: str


@router.post("/preview", response_model=RenderResponse)
async def preview(body: RenderRequest) -> RenderResponse:
    """Render markdown to HTML for preview."""
    html = render_markdown(body.markdown)
    return RenderResponse(html=html)
