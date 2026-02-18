"""Sync API endpoints for bidirectional content synchronization."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_content_manager, get_session, require_auth
from backend.filesystem.content_manager import ContentManager
from backend.models.user import User
from backend.services.sync_service import (
    FileEntry,
    compute_sync_plan,
    get_server_manifest,
    scan_content_files,
    update_server_manifest,
)

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ── Schemas ──────────────────────────────────────────


class ManifestEntry(BaseModel):
    """Single file entry in a sync manifest."""

    file_path: str
    content_hash: str
    file_size: int
    file_mtime: str


class SyncInitRequest(BaseModel):
    """Request to initialize a sync session with the client manifest."""

    client_manifest: list[ManifestEntry]


class SyncPlanItem(BaseModel):
    """Single item in a sync plan describing a conflict."""

    file_path: str
    action: str


class SyncPlanResponse(BaseModel):
    """Response containing the computed sync plan."""

    to_upload: list[str]
    to_download: list[str]
    to_delete_local: list[str]
    to_delete_remote: list[str]
    conflicts: list[SyncPlanItem]


class SyncCommitRequest(BaseModel):
    """Resolution decisions for conflicts."""

    resolutions: dict[str, str]


class SyncCommitResponse(BaseModel):
    """Response after finalizing a sync commit."""

    status: str
    files_synced: int
    warnings: list[str] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────


@router.post("/init", response_model=SyncPlanResponse)
async def sync_init(
    body: SyncInitRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> SyncPlanResponse:
    """Exchange manifests and compute sync plan."""
    client_manifest: dict[str, FileEntry] = {}
    for entry in body.client_manifest:
        client_manifest[entry.file_path] = FileEntry(
            file_path=entry.file_path,
            content_hash=entry.content_hash,
            file_size=entry.file_size,
            file_mtime=entry.file_mtime,
        )

    server_manifest = await get_server_manifest(session)
    server_current = scan_content_files(content_manager.content_dir)
    plan = compute_sync_plan(client_manifest, server_manifest, server_current)

    conflicts = [SyncPlanItem(file_path=c.file_path, action=c.action) for c in plan.conflicts]

    return SyncPlanResponse(
        to_upload=plan.to_upload,
        to_download=plan.to_download,
        to_delete_local=plan.to_delete_local,
        to_delete_remote=plan.to_delete_remote,
        conflicts=conflicts,
    )


@router.post("/upload")
async def sync_upload(
    file: UploadFile,
    file_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> dict[str, str]:
    """Upload a file from client to server."""
    if file.filename is None and not file_path:
        raise HTTPException(status_code=400, detail="file_path required")

    # Security: ensure path is within content dir
    target_path = file_path.lstrip("/")
    full_path = (content_manager.content_dir / target_path).resolve()
    if not full_path.is_relative_to(content_manager.content_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Enforce max upload size (10 MB)
    max_size = 10 * 1024 * 1024
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)

    return {"status": "ok", "file_path": target_path}


@router.get("/download/{file_path:path}")
async def sync_download(
    file_path: str,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> FileResponse:
    """Download a file from server to client."""
    full_path = (content_manager.content_dir / file_path).resolve()
    if not full_path.is_relative_to(content_manager.content_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)


@router.post("/commit", response_model=SyncCommitResponse)
async def sync_commit(
    body: SyncCommitRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> SyncCommitResponse:
    """Finalize sync: update manifest and regenerate caches."""
    # Scan current server state after uploads/downloads
    current_files = scan_content_files(content_manager.content_dir)

    # Update manifest to match current state
    await update_server_manifest(session, current_files)

    # Reload config so newly uploaded labels/config are picked up
    content_manager.reload_config()

    # Rebuild caches
    from backend.services.cache_service import rebuild_cache

    _post_count, warnings = await rebuild_cache(session, content_manager)

    return SyncCommitResponse(
        status="ok",
        files_synced=len(current_files),
        warnings=warnings,
    )
