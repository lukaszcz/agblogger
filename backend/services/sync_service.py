"""Sync service: manifest comparison, change detection, and merge logic."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from backend.models.sync import SyncManifest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ChangeType(str, Enum):
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

    all_paths = set(client_manifest.keys()) | set(server_manifest.keys()) | set(
        server_current.keys()
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
            # Remote deletion
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

        elif not in_client and not in_manifest and not in_server:
            pass  # impossible

        elif in_client and in_manifest and not in_server:
            # Check if client modified before server deleted
            client_hash = client_manifest[path].content_hash
            manifest_hash = server_manifest[path].content_hash
            if client_hash != manifest_hash:
                plan.conflicts.append(
                    SyncChange(
                        file_path=path,
                        change_type=ChangeType.DELETE_MODIFY_CONFLICT,
                        action="merge",
                    )
                )
            else:
                plan.to_delete_local.append(path)

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
                synced_at="",  # Will be set properly
            )
        )
    await session.commit()
