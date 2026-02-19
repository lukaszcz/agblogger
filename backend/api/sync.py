"""Sync API endpoints for bidirectional content synchronization."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_content_manager, get_git_service, get_session, require_auth
from backend.filesystem.content_manager import ContentManager
from backend.models.user import User
from backend.services.git_service import GitService
from backend.services.sync_service import (
    FileEntry,
    compute_sync_plan,
    get_server_manifest,
    merge_file,
    normalize_post_frontmatter,
    scan_content_files,
    update_server_manifest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_sync_lock = asyncio.Lock()


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
    last_sync_commit: str | None = None


class SyncPlanItem(BaseModel):
    """Single item in a sync plan describing a conflict."""

    file_path: str
    action: str
    change_type: str = ""


class SyncPlanResponse(BaseModel):
    """Response containing the computed sync plan."""

    to_upload: list[str]
    to_download: list[str]
    to_delete_local: list[str]
    to_delete_remote: list[str]
    conflicts: list[SyncPlanItem]
    server_commit: str | None = None


class MergeResult(BaseModel):
    """Result of a three-way merge for a conflicting file."""

    file_path: str
    status: str  # "merged" or "conflicted"
    content: str | None = None  # diff3 markers for "conflicted"


class SyncCommitRequest(BaseModel):
    """Resolution decisions for conflicts."""

    resolutions: dict[str, str]
    uploaded_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    conflict_files: list[str] = Field(default_factory=list)
    last_sync_commit: str | None = None


class SyncCommitResponse(BaseModel):
    """Response after finalizing a sync commit."""

    status: str
    files_synced: int
    warnings: list[str] = Field(default_factory=list)
    commit_hash: str | None = None
    merge_results: list[MergeResult] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────


@router.post("/init", response_model=SyncPlanResponse)
async def sync_init(
    body: SyncInitRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
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

    conflicts = [
        SyncPlanItem(
            file_path=c.file_path,
            action=c.action,
            change_type=c.change_type,
        )
        for c in plan.conflicts
    ]

    return SyncPlanResponse(
        to_upload=plan.to_upload,
        to_download=plan.to_download,
        to_delete_local=plan.to_delete_local,
        to_delete_remote=plan.to_delete_remote,
        conflicts=conflicts,
        server_commit=git_service.head_commit(),
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
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
) -> SyncCommitResponse:
    """Finalize sync: merge conflicts, normalize front matter, update manifest and caches."""
    async with _sync_lock:
        return await _sync_commit_inner(body, session, content_manager, git_service, user)


async def _sync_commit_inner(
    body: SyncCommitRequest,
    session: AsyncSession,
    content_manager: ContentManager,
    git_service: GitService,
    user: User,
) -> SyncCommitResponse:
    """Inner sync commit logic, called under _sync_lock."""
    content_dir = content_manager.content_dir

    # Load old manifest before updating (needed for new-vs-edit detection)
    old_manifest = await get_server_manifest(session)

    # Apply remote deletions requested by the client.
    for file_path in body.deleted_files:
        target_path = file_path.lstrip("/")
        full_path = (content_dir / target_path).resolve()
        if not full_path.is_relative_to(content_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid file path")
        if full_path.exists() and full_path.is_file():
            full_path.unlink()
            logger.info("Sync: deleted file %s", target_path)

    # ── Three-way merge for conflict files ──
    pre_upload_head = git_service.head_commit()
    can_merge = body.last_sync_commit is not None and git_service.commit_exists(
        body.last_sync_commit
    )

    merge_results: list[MergeResult] = []
    merged_uploaded: list[str] = []

    for conflict_path in body.conflict_files:
        target_path = conflict_path.lstrip("/")
        full_path = (content_dir / target_path).resolve()
        if not full_path.is_relative_to(content_dir.resolve()):
            raise HTTPException(
                status_code=400, detail=f"Invalid conflict file path: {conflict_path}"
            )

        # Get server version from before uploads
        if pre_upload_head is not None:
            server_content = git_service.show_file_at_commit(pre_upload_head, target_path)
        else:
            server_content = None

        # Handle delete/modify conflicts
        try:
            if not full_path.exists() and server_content is not None:
                # Client deleted, server modified → keep server version
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(server_content, encoding="utf-8")
                merge_results.append(MergeResult(file_path=target_path, status="merged"))
                merged_uploaded.append(target_path)
                continue
            if not full_path.exists():
                continue
            if server_content is None:
                # Server deleted, client modified → keep client (already on disk)
                merge_results.append(MergeResult(file_path=target_path, status="merged"))
                merged_uploaded.append(target_path)
                continue

            client_content = full_path.read_text(encoding="utf-8")
            base_content: str | None = None
            if can_merge and body.last_sync_commit is not None:
                base_content = git_service.show_file_at_commit(body.last_sync_commit, target_path)

            merged_text, has_conflicts = merge_file(base_content, server_content, client_content)

            if has_conflicts:
                # Restore server version on disk, return conflict markers to client
                full_path.write_text(server_content, encoding="utf-8")
                merge_results.append(
                    MergeResult(file_path=target_path, status="conflicted", content=merged_text)
                )
            else:
                # Clean merge — write merged result to disk
                full_path.write_text(merged_text, encoding="utf-8")
                merge_results.append(MergeResult(file_path=target_path, status="merged"))
                merged_uploaded.append(target_path)
        except OSError as exc:
            logger.error("File I/O error during merge of %s: %s", target_path, exc)
            raise HTTPException(
                status_code=500, detail=f"File I/O error during merge of {target_path}"
            ) from exc

    # Normalize front matter for uploaded + cleanly merged post files
    all_uploaded = list(dict.fromkeys(body.uploaded_files + merged_uploaded))
    fm_warnings = normalize_post_frontmatter(
        uploaded_files=all_uploaded,
        old_manifest=old_manifest,
        content_dir=content_dir,
        default_author=content_manager.site_config.default_author,
    )

    # Git commit after all file changes
    username = user.display_name or user.username
    try:
        git_service.commit_all(f"Sync commit by {username}")
    except subprocess.CalledProcessError:
        logger.warning("Git commit failed during sync commit by %s", username)

    # Scan current server state after uploads/downloads + normalization
    current_files = scan_content_files(content_dir)

    # Update manifest to match current state
    await update_server_manifest(session, current_files)

    # Reload config so newly uploaded labels/config are picked up
    content_manager.reload_config()

    # Rebuild caches
    from backend.services.cache_service import rebuild_cache

    _post_count, cache_warnings = await rebuild_cache(session, content_manager)

    return SyncCommitResponse(
        status="ok",
        files_synced=len(current_files),
        warnings=fm_warnings + cache_warnings,
        commit_hash=git_service.head_commit(),
        merge_results=merge_results,
    )
