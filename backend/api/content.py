"""Content file serving endpoint."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from backend.api.deps import get_settings
from backend.config import Settings

router = APIRouter(prefix="/api/content", tags=["content"])

_ALLOWED_PREFIXES = ("posts/", "assets/")


def _validate_path(file_path: str, content_dir: Path) -> Path:
    """Validate and resolve a content file path.

    Returns the resolved absolute path on success.
    Raises HTTPException on validation failure.
    """
    # Reject path traversal attempts
    if ".." in file_path.split("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal is not allowed",
        )

    # Check allowed prefixes
    if not file_path.startswith(_ALLOWED_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this path is not allowed",
        )

    # Resolve the full path (follows symlinks)
    full_path = (content_dir / file_path).resolve()

    # Verify resolved path stays within the content directory
    if not full_path.is_relative_to(content_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal is not allowed",
        )

    return full_path


@router.get("/{file_path:path}")
async def serve_content_file(
    file_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve a file from the content directory.

    Public endpoint — no authentication required.
    Restricted to files under posts/ and assets/ prefixes.
    """
    resolved = _validate_path(file_path, settings.content_dir)

    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(resolved))
    if content_type is None:
        content_type = "application/octet-stream"

    return FileResponse(path=resolved, media_type=content_type)
