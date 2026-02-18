"""Sync service: manifest comparison, change detection, and merge logic."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter as fm
from sqlalchemy import delete, select

from backend.filesystem.frontmatter import RECOGNIZED_FIELDS
from backend.models.sync import SyncManifest
from backend.services.datetime_service import format_datetime, format_iso, now_utc, parse_datetime

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ChangeType(StrEnum):
    """Type of change detected between client, server, and manifest."""

    NO_CHANGE = "no_change"
    LOCAL_ADD = "local_add"
    LOCAL_MODIFY = "local_modify"
    LOCAL_DELETE = "local_delete"
    REMOTE_ADD = "remote_add"
    REMOTE_MODIFY = "remote_modify"
    REMOTE_DELETE = "remote_delete"
    CONFLICT = "conflict"
    DELETE_MODIFY_CONFLICT = "delete_modify_conflict"


@dataclass
class FileEntry:
    """Represents a file's state."""

    file_path: str
    content_hash: str
    file_size: int
    file_mtime: str


@dataclass
class SyncChange:
    """A single change in the sync plan."""

    file_path: str
    change_type: ChangeType
    action: str  # "push", "pull", "merge", "skip", "delete_remote", "delete_local"


@dataclass
class SyncPlan:
    """The computed sync plan."""

    to_upload: list[str] = field(default_factory=list)
    to_download: list[str] = field(default_factory=list)
    to_delete_remote: list[str] = field(default_factory=list)
    to_delete_local: list[str] = field(default_factory=list)
    conflicts: list[SyncChange] = field(default_factory=list)
    no_change: list[str] = field(default_factory=list)


def hash_file(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def scan_content_files(content_dir: Path) -> dict[str, FileEntry]:
    """Scan content directory and build file entry map."""
    entries: dict[str, FileEntry] = {}
    for root, _dirs, files in os.walk(content_dir):
        for filename in files:
            full = Path(root) / filename
            rel = str(full.relative_to(content_dir))
            stat = full.stat()
            entries[rel] = FileEntry(
                file_path=rel,
                content_hash=hash_file(full),
                file_size=stat.st_size,
                file_mtime=str(stat.st_mtime),
            )
    return entries


def compute_sync_plan(
    client_manifest: dict[str, FileEntry],
    server_manifest: dict[str, FileEntry],
    server_current: dict[str, FileEntry],
) -> SyncPlan:
    """Compute sync plan by comparing client manifest, server manifest, and server current state.

    For a "push" scenario (client -> server), client_manifest is the client's view,
    server_manifest is the agreed-upon manifest from last sync, and server_current is
    what the server has right now.
    """
    plan = SyncPlan()

    all_paths = (
        set(client_manifest.keys()) | set(server_manifest.keys()) | set(server_current.keys())
    )

    for path in sorted(all_paths):
        in_client = path in client_manifest
        in_manifest = path in server_manifest
        in_server = path in server_current

        if in_client and in_manifest and in_server:
            client_hash = client_manifest[path].content_hash
            manifest_hash = server_manifest[path].content_hash
            server_hash = server_current[path].content_hash

            client_changed = client_hash != manifest_hash
            server_changed = server_hash != manifest_hash

            if not client_changed and not server_changed:
                plan.no_change.append(path)
            elif client_changed and not server_changed:
                plan.to_upload.append(path)
            elif not client_changed and server_changed:
                plan.to_download.append(path)
            else:
                # Both changed
                if client_hash == server_hash:
                    plan.no_change.append(path)
                else:
                    plan.conflicts.append(
                        SyncChange(
                            file_path=path,
                            change_type=ChangeType.CONFLICT,
                            action="merge",
                        )
                    )

        elif in_client and not in_manifest and not in_server:
            # New local file
            plan.to_upload.append(path)

        elif not in_client and not in_manifest and in_server:
            # New remote file
            plan.to_download.append(path)

        elif in_client and in_manifest and not in_server:
            # Server deleted the file — check if client modified it
            client_hash = client_manifest[path].content_hash
            manifest_hash = server_manifest[path].content_hash
            if client_hash != manifest_hash:
                # Client modified a file the server deleted
                plan.conflicts.append(
                    SyncChange(
                        file_path=path,
                        change_type=ChangeType.DELETE_MODIFY_CONFLICT,
                        action="merge",
                    )
                )
            else:
                plan.to_delete_local.append(path)

        elif not in_client and in_manifest and in_server:
            # Local deletion
            plan.to_delete_remote.append(path)

        elif in_client and not in_manifest and in_server:
            # Both added independently
            client_hash = client_manifest[path].content_hash
            server_hash = server_current[path].content_hash
            if client_hash == server_hash:
                plan.no_change.append(path)
            else:
                plan.conflicts.append(
                    SyncChange(
                        file_path=path,
                        change_type=ChangeType.CONFLICT,
                        action="merge",
                    )
                )

        elif not in_client and in_manifest and not in_server:
            # Both deleted
            plan.no_change.append(path)

    return plan


async def get_server_manifest(session: AsyncSession) -> dict[str, FileEntry]:
    """Load the server's sync manifest from DB."""
    stmt = select(SyncManifest)
    result = await session.execute(stmt)
    entries: dict[str, FileEntry] = {}
    for row in result.scalars().all():
        entries[row.file_path] = FileEntry(
            file_path=row.file_path,
            content_hash=row.content_hash,
            file_size=row.file_size,
            file_mtime=row.file_mtime,
        )
    return entries


async def update_server_manifest(
    session: AsyncSession,
    entries: dict[str, FileEntry],
) -> None:
    """Replace the server manifest with new entries."""
    await session.execute(delete(SyncManifest))
    for entry in entries.values():
        session.add(
            SyncManifest(
                file_path=entry.file_path,
                content_hash=entry.content_hash,
                file_size=entry.file_size,
                file_mtime=entry.file_mtime,
                synced_at=format_iso(now_utc()),
            )
        )
    await session.commit()


def normalize_post_frontmatter(
    uploaded_files: list[str],
    old_manifest: dict[str, FileEntry],
    content_dir: Path,
    default_author: str,
) -> list[str]:
    """Normalize YAML front matter for uploaded post files during sync.

    Fills missing fields (timestamps, author) with defaults, normalizes existing
    timestamps to strict format, and warns about unrecognized front matter fields.

    Returns a list of warning strings.
    """
    warnings: list[str] = []
    current_time = format_datetime(now_utc())

    for file_path in uploaded_files:
        # Skip non-post files
        if not file_path.startswith("posts/") or not file_path.endswith(".md"):
            continue

        full_path = (content_dir / file_path).resolve()

        # Validate path stays within content_dir
        try:
            full_path.relative_to(content_dir.resolve())
        except ValueError:
            logger.warning("Path traversal attempt: %s", file_path)
            continue

        # Skip if file doesn't exist on disk
        if not full_path.is_file():
            continue

        raw = full_path.read_text(encoding="utf-8")
        post = fm.loads(raw)

        # Check for unrecognized fields
        for key in post.metadata:
            if key not in RECOGNIZED_FIELDS:
                warnings.append(f"{file_path}: unrecognized front matter field '{key}'")

        # Determine new vs edit
        is_edit = file_path in old_manifest

        # Normalize timestamps that already exist
        for ts_field in ("created_at", "modified_at"):
            raw_value = post.get(ts_field)
            if raw_value is not None:
                if isinstance(raw_value, date) and not isinstance(raw_value, datetime):
                    raw_value = datetime(raw_value.year, raw_value.month, raw_value.day)
                if isinstance(raw_value, datetime):
                    post[ts_field] = format_datetime(raw_value)
                else:
                    post[ts_field] = format_datetime(parse_datetime(raw_value))

        if is_edit:
            # Edited post: always update modified_at, fill missing fields
            post["modified_at"] = current_time
            if "created_at" not in post.metadata:
                post["created_at"] = current_time
            if "author" not in post.metadata and default_author:
                post["author"] = default_author
        else:
            # New post: fill missing timestamps and author
            if "created_at" not in post.metadata:
                post["created_at"] = current_time
            if "modified_at" not in post.metadata:
                post["modified_at"] = post["created_at"]
            if "author" not in post.metadata and default_author:
                post["author"] = default_author

        # Rewrite file on disk
        full_path.write_text(fm.dumps(post) + "\n", encoding="utf-8")

    return warnings
