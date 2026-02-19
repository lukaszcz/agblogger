"""CLI sync client for AgBlogger bidirectional sync."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)

MANIFEST_FILE = ".agblogger-manifest.json"


@dataclass
class FileEntry:
    file_path: str
    content_hash: str
    file_size: int
    file_mtime: str


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def scan_local_files(content_dir: Path) -> dict[str, FileEntry]:
    """Scan local content directory."""
    entries: dict[str, FileEntry] = {}
    for root, dirs, files in os.walk(content_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
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


def load_manifest(content_dir: Path) -> dict[str, FileEntry]:
    """Load local manifest from file."""
    manifest_path = content_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return {}
    data = json.loads(manifest_path.read_text())
    return {k: FileEntry(**v) for k, v in data.items()}


def save_manifest(content_dir: Path, entries: dict[str, FileEntry]) -> None:
    """Save local manifest to file."""
    manifest_path = content_dir / MANIFEST_FILE
    data = {k: asdict(v) for k, v in entries.items()}
    manifest_path.write_text(json.dumps(data, indent=2))


class SyncClient:
    """Client for syncing with AgBlogger server."""

    def __init__(self, server_url: str, content_dir: Path, token: str) -> None:
        self.server_url = server_url.rstrip("/")
        self.content_dir = content_dir
        self.client = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> SyncClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self, username: str, password: str) -> str:
        """Login and return access token."""
        resp = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        result: str = resp.json()["access_token"]
        return result

    def _get_last_sync_commit(self) -> str | None:
        """Get the commit hash from the last sync."""
        config = load_config(self.content_dir)
        return config.get("last_sync_commit")

    def _save_commit_hash(self, commit_hash: str | None) -> None:
        """Save the commit hash from a sync response."""
        if commit_hash is None:
            return
        config = load_config(self.content_dir)
        config["last_sync_commit"] = commit_hash
        save_config(self.content_dir, config)

    def status(self) -> dict[str, Any]:
        """Show what would change without syncing."""
        local_files = scan_local_files(self.content_dir)
        manifest = [asdict(e) for e in local_files.values()]
        last_sync_commit = self._get_last_sync_commit()

        resp = self.client.post(
            "/api/sync/init",
            json={"client_manifest": manifest, "last_sync_commit": last_sync_commit},
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    def _upload_file(self, file_path: str) -> bool:
        """Upload a single file to the server. Returns True if successful."""
        full_path = self.content_dir / file_path
        if not full_path.exists():
            print(f"  Skip (missing): {file_path}")
            return False
        with open(full_path, "rb") as f:
            resp = self.client.post(
                "/api/sync/upload",
                files={"file": (file_path, f)},
                data={"file_path": file_path},
            )
            resp.raise_for_status()
        return True

    def push(self) -> None:
        """Push local changes to server."""
        plan = self.status()
        to_delete_remote = plan.get("to_delete_remote", [])
        last_sync_commit = self._get_last_sync_commit()

        uploaded_files: list[str] = []
        for file_path in plan.get("to_upload", []):
            if self._upload_file(file_path):
                print(f"  Uploaded: {file_path}")
                uploaded_files.append(file_path)

        # Commit
        resp = self.client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": uploaded_files,
                "deleted_files": to_delete_remote,
                "last_sync_commit": last_sync_commit,
            },
        )
        resp.raise_for_status()
        commit_data = resp.json()
        self._save_commit_hash(commit_data.get("commit_hash"))

        # Update local manifest
        local_files = scan_local_files(self.content_dir)
        save_manifest(self.content_dir, local_files)

        print(f"Push complete. {len(uploaded_files)} file(s) uploaded.")

    def pull(self) -> None:
        """Pull remote changes to local."""
        plan = self.status()
        last_sync_commit = self._get_last_sync_commit()

        downloaded = 0
        for file_path in plan.get("to_download", []):
            if ".." in file_path or file_path.startswith("/"):
                print(f"  Skip (invalid path): {file_path}")
                continue
            resp = self.client.get(f"/api/sync/download/{file_path}")
            resp.raise_for_status()

            local_path = self.content_dir / file_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(resp.content)
            print(f"  Downloaded: {file_path}")
            downloaded += 1

        for file_path in plan.get("to_delete_local", []):
            local_path = self.content_dir / file_path
            if local_path.exists():
                local_path.unlink()
                print(f"  Deleted: {file_path}")

        # Commit to update server manifest
        resp = self.client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": [],
                "last_sync_commit": last_sync_commit,
            },
        )
        resp.raise_for_status()
        commit_data = resp.json()
        self._save_commit_hash(commit_data.get("commit_hash"))

        # Update local manifest
        local_files = scan_local_files(self.content_dir)
        save_manifest(self.content_dir, local_files)

        print(f"Pull complete. {downloaded} file(s) downloaded.")

    def sync(self) -> None:
        """Full bidirectional sync."""
        plan = self.status()
        to_delete_remote = plan.get("to_delete_remote", [])
        last_sync_commit = self._get_last_sync_commit()

        # Push local changes
        uploaded_files: list[str] = []
        for file_path in plan.get("to_upload", []):
            if self._upload_file(file_path):
                print(f"  Pushed: {file_path}")
                uploaded_files.append(file_path)

        # Upload conflict files (client's version) for server-side merge
        conflicts = plan.get("conflicts", [])
        conflict_files: list[str] = []
        for conflict in conflicts:
            fp = conflict["file_path"]
            if self._upload_file(fp):
                conflict_files.append(fp)
                print(f"  Uploaded for merge: {fp}")

        # Pull remote changes
        for file_path in plan.get("to_download", []):
            if ".." in file_path or file_path.startswith("/"):
                print(f"  Skip (invalid path): {file_path}")
                continue
            resp = self.client.get(f"/api/sync/download/{file_path}")
            resp.raise_for_status()
            local_path = self.content_dir / file_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(resp.content)
            print(f"  Pulled: {file_path}")

        # Delete local files
        for file_path in plan.get("to_delete_local", []):
            local_path = self.content_dir / file_path
            if local_path.exists():
                local_path.unlink()
                print(f"  Deleted: {file_path}")

        # Commit with conflict files for server-side merge
        resp = self.client.post(
            "/api/sync/commit",
            json={
                "resolutions": {},
                "uploaded_files": uploaded_files,
                "deleted_files": to_delete_remote,
                "conflict_files": conflict_files,
                "last_sync_commit": last_sync_commit,
            },
        )
        resp.raise_for_status()
        commit_data = resp.json()

        # Handle merge results
        merge_results = commit_data.get("merge_results", [])
        for mr in merge_results:
            fp = mr["file_path"]
            if ".." in fp or fp.startswith("/"):
                print(f"  Skip (invalid path in merge result): {fp}")
                continue
            if mr["status"] == "merged":
                # Download the cleanly merged file from server
                dl_resp = self.client.get(f"/api/sync/download/{fp}")
                if dl_resp.status_code != 200:
                    print(
                        f"  ERROR: Failed to download merged file {fp} (HTTP {dl_resp.status_code})"
                    )
                    print("  Sync aborted. Local state may be inconsistent.")
                    sys.exit(1)
                local_path = self.content_dir / fp
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(dl_resp.content)
                print(f"  Merged: {fp}")
            elif mr["status"] == "conflicted":
                local_path = self.content_dir / fp
                # Save backup of local version
                backup_path = local_path.with_suffix(local_path.suffix + ".conflict-backup")
                if local_path.exists():
                    backup_path.write_bytes(local_path.read_bytes())
                # Write conflict markers as the main file
                if mr.get("content"):
                    local_path.write_text(mr["content"], encoding="utf-8")
                    print(f"  CONFLICT: {fp} (markers written, backup saved)")
                else:
                    print(f"  CONFLICT: {fp} (no markers available, backup saved)")

        self._save_commit_hash(commit_data.get("commit_hash"))

        # Update local manifest
        local_files = scan_local_files(self.content_dir)
        save_manifest(self.content_dir, local_files)

        total = (
            len(plan.get("to_upload", []))
            + len(plan.get("to_download", []))
            + len(to_delete_remote)
        )
        print(f"Sync complete. {total} file(s) synced, {len(conflicts)} conflict(s).")


CONFIG_FILE = ".agblogger-sync.json"


def load_config(dir_path: Path) -> dict[str, str]:
    """Load sync config from file."""
    config_path = dir_path / CONFIG_FILE
    if not config_path.exists():
        return {}
    config: dict[str, str] = json.loads(config_path.read_text())
    return config


def save_config(dir_path: Path, config: dict[str, str]) -> None:
    """Save sync config to file."""
    config_path = dir_path / CONFIG_FILE
    config_path.write_text(json.dumps(config, indent=2))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="agblogger-sync",
        description="Sync local content with AgBlogger server",
    )
    parser.add_argument("--dir", "-d", default=".", help="Content directory (default: current)")
    parser.add_argument("--server", "-s", help="Server URL")
    parser.add_argument("--username", "-u", help="Username for authentication")
    parser.add_argument("--password", "-p", help="Password for authentication")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Initialize sync configuration")
    subparsers.add_parser("status", help="Show what would change")
    subparsers.add_parser("push", help="Push local changes to server")
    subparsers.add_parser("pull", help="Pull remote changes to local")
    subparsers.add_parser("sync", help="Bidirectional sync")

    args = parser.parse_args()
    content_dir = Path(args.dir).resolve()

    if args.command == "init":
        if not args.server:
            print("Error: --server required for init")
            sys.exit(1)
        config = {
            "server": args.server,
            "content_dir": str(content_dir),
        }
        if args.username:
            config["username"] = args.username
        save_config(content_dir, config)
        print(f"Initialized sync config in {content_dir / CONFIG_FILE}")
        return

    # Load config
    config = load_config(content_dir)
    server_url = args.server or config.get("server")
    if not server_url:
        print("Error: No server configured. Run 'agblogger-sync init --server <url>' first.")
        sys.exit(1)

    username = args.username or config.get("username")
    password = args.password or config.get("password")
    if not username or not password:
        print("Error: Username and password required. Use --username/--password or set in config.")
        sys.exit(1)

    # Create client and login
    temp_client = httpx.Client(base_url=server_url, timeout=30.0)
    login_resp = temp_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    if login_resp.status_code != 200:
        print(f"Error: Login failed ({login_resp.status_code})")
        sys.exit(1)
    token = login_resp.json()["access_token"]
    temp_client.close()

    with SyncClient(server_url, content_dir, token) as client:
        if args.command == "status":
            plan = client.status()
            print("Sync Status:")
            print(f"  To upload:       {len(plan.get('to_upload', []))}")
            print(f"  To download:     {len(plan.get('to_download', []))}")
            print(f"  To delete local: {len(plan.get('to_delete_local', []))}")
            print(f"  To delete remote:{len(plan.get('to_delete_remote', []))}")
            print(f"  Conflicts:       {len(plan.get('conflicts', []))}")

            for f in plan.get("to_upload", []):
                print(f"    + {f} (upload)")
            for f in plan.get("to_download", []):
                print(f"    < {f} (download)")
            for c in plan.get("conflicts", []):
                print(f"    ! {c['file_path']} (conflict)")

        elif args.command == "push":
            client.push()
        elif args.command == "pull":
            client.pull()
        elif args.command == "sync":
            client.sync()
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
