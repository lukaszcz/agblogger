"""Page API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_content_manager
from backend.schemas.page import PageResponse, SiteConfigResponse
from backend.services.page_service import get_page, get_site_config

if TYPE_CHECKING:
    from backend.filesystem.content_manager import ContentManager

router = APIRouter(prefix="/api/pages", tags=["pages"])


@router.get("", response_model=SiteConfigResponse)
async def site_config(
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
) -> SiteConfigResponse:
    """Get site configuration including page list."""
    return get_site_config(content_manager)


@router.get("/{page_id}", response_model=PageResponse)
async def get_page_endpoint(
    page_id: str,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
) -> PageResponse:
    """Get a top-level page with rendered HTML."""
    page = get_page(content_manager, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
