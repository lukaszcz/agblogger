"""Git service: content directory versioning via git CLI."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_COMMIT_RE = re.compile(r"^[0-9a-f]{4,40}$")


class GitService:
    """Wraps git CLI operations on the content directory."""

    def __init__(self, content_dir: Path) -> None:
        self.content_dir = content_dir

    def _run(
        self,
        *args: str,
        check: bool = True,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command in the content directory."""
        return subprocess.run(
            ["git", *args],
            cwd=self.content_dir,
            check=check,
            capture_output=capture_output,
            text=True,
        )

    def init_repo(self) -> None:
        """Initialize a git repo if one doesn't exist, then commit any existing files."""
        try:
            if not (self.content_dir / ".git").exists():
                self._run("init")
                self._run("config", "user.email", "agblogger@localhost")
                self._run("config", "user.name", "AgBlogger")
                logger.info("Initialized git repo in %s", self.content_dir)

            # Commit any existing files so HEAD is valid
            self._run("add", "-A")
            result = self._run("diff", "--cached", "--quiet", check=False)
            if result.returncode != 0:
                self._run("commit", "-m", "Initial commit")
                logger.info("Created initial commit for existing content")
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.error(
                "Failed to initialize git repo in %s: %s. "
                "Ensure 'git' is installed and the content directory is writable.",
                self.content_dir,
                exc,
            )
            raise

    def commit_all(self, message: str) -> str | None:
        """Stage all changes and commit. Returns commit hash or None if nothing to commit."""
        self._run("add", "-A")
        result = self._run("diff", "--cached", "--quiet", check=False)
        if result.returncode == 0:
            return None
        self._run("commit", "-m", message)
        return self.head_commit()

    def try_commit(self, message: str) -> str | None:
        """Stage and commit, logging an error on failure instead of raising.

        Convenience wrapper around commit_all() for API endpoints where a git
        failure should not abort the request.
        """
        try:
            return self.commit_all(message)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Git commit failed (exit %d): %s — %s",
                exc.returncode,
                exc.stderr.strip() if exc.stderr else "no stderr",
                message,
            )
            return None

    def head_commit(self) -> str | None:
        """Return the current HEAD commit hash, or None if the repo has no commits."""
        result = self._run("rev-parse", "HEAD", check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def commit_exists(self, commit_hash: str) -> bool:
        """Check if a commit hash exists in the repo."""
        if not _COMMIT_RE.match(commit_hash):
            return False
        result = self._run("cat-file", "-t", commit_hash, check=False)
        return result.returncode == 0 and result.stdout.strip() == "commit"

    def show_file_at_commit(self, commit_hash: str, file_path: str) -> str | None:
        """Return file content at a specific commit, or None if file doesn't exist there.

        Raises subprocess.CalledProcessError on unexpected git errors (corrupt repo,
        permission denied, etc.) so callers can distinguish "file missing" from "git broken".
        """
        if not _COMMIT_RE.match(commit_hash):
            logger.warning("Rejected invalid commit hash %r for file %s", commit_hash, file_path)
            return None
        result = self._run("show", f"{commit_hash}:{file_path}", check=False)
        if result.returncode == 0:
            return result.stdout
        stderr = result.stderr
        if result.returncode == 128 and ("does not exist" in stderr or "but not in" in stderr):
            return None
        raise subprocess.CalledProcessError(
            result.returncode,
            f"git show {commit_hash}:{file_path}",
            output=result.stdout,
            stderr=result.stderr,
        )
