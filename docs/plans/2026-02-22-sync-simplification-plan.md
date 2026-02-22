# Sync Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the custom merge3-based sync with git merge-file for body merging and semantic field-level merging for front matter. Simplify the protocol from 4 endpoints to 2+1 and the CLI from 5 commands to 3.

**Architecture:** The sync service splits markdown files into front matter and body before merging. Front matter fields are merged semantically (set-based for labels, server-time for modified_at, conflict-reported for title/author/created_at/draft). Body content is merged via `git merge-file`. The API is simplified to `POST /status` (manifest comparison) and `POST /commit` (multipart upload + merge), with `GET /download/{path}` kept as a utility. The CLI drops push/pull commands.

**Tech Stack:** Python, FastAPI, git CLI (`git merge-file`), python-frontmatter, pytest, httpx

**Design doc:** `docs/plans/2026-02-22-sync-simplification-design.md`

---

### Task 1: Add `merge_file_content` to GitService

Add a method wrapping `git merge-file` for three-way merge of individual file content.

**Files:**
- Modify: `backend/services/git_service.py:103-123`
- Test: `tests/test_services/test_git_merge_file.py` (create)

**Step 1: Write the failing test**

Create `tests/test_services/test_git_merge_file.py`:

```python
"""Tests for GitService.merge_file_content using git merge-file."""

from __future__ import annotations

from pathlib import Path

from backend.services.git_service import GitService


class TestMergeFileContent:
    def test_clean_merge_non_overlapping(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "line1\nline2\nline3\n"
        ours = "line1 changed\nline2\nline3\n"
        theirs = "line1\nline2\nline3 changed\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert "line1 changed" in merged
        assert "line3 changed" in merged

    def test_conflict_overlapping(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "line1\noriginal\nline3\n"
        ours = "line1\nours-version\nline3\n"
        theirs = "line1\ntheirs-version\nline3\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert conflicted

    def test_identical_changes(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "original\n"
        ours = "same change\n"
        theirs = "same change\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert merged == "same change\n"

    def test_one_side_unchanged(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = "original\n"
        ours = "original\n"
        theirs = "changed\n"
        merged, conflicted = git.merge_file_content(base, ours, theirs)
        assert not conflicted
        assert merged == "changed\n"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_services/test_git_merge_file.py -v`
Expected: FAIL with `AttributeError: 'GitService' object has no attribute 'merge_file_content'`

**Step 3: Write minimal implementation**

Add to `backend/services/git_service.py` after `show_file_at_commit()`:

```python
def merge_file_content(
    self, base: str, ours: str, theirs: str
) -> tuple[str, bool]:
    """Three-way merge of text content using git merge-file.

    Writes base/ours/theirs to temp files, runs git merge-file (result
    goes into the 'ours' file), reads back the result.

    Returns (merged_text, has_conflicts).
    """
    import tempfile

    with tempfile.TemporaryDirectory(dir=self.content_dir) as td:
        tmp = Path(td)
        base_f = tmp / "base"
        ours_f = tmp / "ours"
        theirs_f = tmp / "theirs"
        base_f.write_text(base, encoding="utf-8")
        ours_f.write_text(ours, encoding="utf-8")
        theirs_f.write_text(theirs, encoding="utf-8")

        result = subprocess.run(
            ["git", "merge-file", "-p", str(ours_f), str(base_f), str(theirs_f)],
            cwd=self.content_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        # exit 0 = clean merge, exit 1 = conflicts, exit >= 2 = error
        if result.returncode >= 2:
            raise subprocess.CalledProcessError(
                result.returncode, "git merge-file", result.stdout, result.stderr
            )
        return result.stdout, result.returncode == 1
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_services/test_git_merge_file.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/git_service.py tests/test_services/test_git_merge_file.py
git commit -m "feat: add merge_file_content to GitService using git merge-file"
```

---

### Task 2: Add front matter semantic merge logic

Create `merge_frontmatter()` in sync_service.py that merges front matter fields with semantic rules: set-based labels, server-time for modified_at, conflict reporting for title/author/created_at/draft.

**Files:**
- Modify: `backend/services/sync_service.py:246-274` (replace `merge_file()`)
- Test: `tests/test_services/test_frontmatter_merge.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_services/test_frontmatter_merge.py`:

```python
"""Tests for semantic front matter merging."""

from __future__ import annotations

from backend.services.sync_service import FrontmatterMergeResult, merge_frontmatter


class TestMergeFrontmatter:
    def test_no_changes(self) -> None:
        base = {"title": "T", "author": "A", "labels": ["#a"], "created_at": "2026-01-01"}
        server = dict(base)
        client = dict(base)
        result = merge_frontmatter(base, server, client)
        assert result.merged == base
        assert result.field_conflicts == []

    def test_labels_set_union(self) -> None:
        base = {"labels": ["#a", "#b"]}
        server = {"labels": ["#a", "#b", "#c"]}
        client = {"labels": ["#a", "#b", "#d"]}
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a", "#b", "#c", "#d"}
        assert result.field_conflicts == []

    def test_labels_removal_both_sides(self) -> None:
        base = {"labels": ["#a", "#b", "#c"]}
        server = {"labels": ["#a", "#c"]}  # removed #b
        client = {"labels": ["#a", "#b"]}  # removed #c
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a"}
        assert result.field_conflicts == []

    def test_labels_add_and_remove(self) -> None:
        base = {"labels": ["#a", "#b"]}
        server = {"labels": ["#a"]}  # removed #b
        client = {"labels": ["#a", "#b", "#c"]}  # added #c
        result = merge_frontmatter(base, server, client)
        assert set(result.merged["labels"]) == {"#a", "#c"}
        assert result.field_conflicts == []

    def test_modified_at_ignored(self) -> None:
        base = {"modified_at": "2026-01-01"}
        server = {"modified_at": "2026-01-02"}
        client = {"modified_at": "2026-01-03"}
        result = merge_frontmatter(base, server, client)
        assert "modified_at" not in result.merged
        assert result.field_conflicts == []

    def test_title_one_side_changed(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Original"}
        client = {"title": "New Title"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "New Title"
        assert result.field_conflicts == []

    def test_title_both_changed_same(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Same New"}
        client = {"title": "Same New"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "Same New"
        assert result.field_conflicts == []

    def test_title_conflict(self) -> None:
        base = {"title": "Original"}
        server = {"title": "Server Title"}
        client = {"title": "Client Title"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["title"] == "Server Title"
        assert "title" in result.field_conflicts

    def test_author_conflict(self) -> None:
        base = {"author": "Alice"}
        server = {"author": "Bob"}
        client = {"author": "Charlie"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["author"] == "Bob"
        assert "author" in result.field_conflicts

    def test_draft_conflict(self) -> None:
        base = {"draft": True}
        server = {"draft": False}
        client = {"draft": True}  # unchanged from base, so not a conflict
        result = merge_frontmatter(base, server, client)
        assert result.merged["draft"] is False
        assert result.field_conflicts == []

    def test_preserves_unrecognized_fields(self) -> None:
        base = {"title": "T", "custom": "value"}
        server = {"title": "T", "custom": "value"}
        client = {"title": "T", "custom": "new"}
        result = merge_frontmatter(base, server, client)
        assert result.merged["custom"] == "new"

    def test_no_base_returns_server_with_conflicts(self) -> None:
        server = {"title": "Server", "labels": ["#a"]}
        client = {"title": "Client", "labels": ["#b"]}
        result = merge_frontmatter(None, server, client)
        assert result.merged == server
        assert "title" in result.field_conflicts
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_services/test_frontmatter_merge.py -v`
Expected: FAIL with `ImportError: cannot import name 'FrontmatterMergeResult'`

**Step 3: Write minimal implementation**

Replace `merge_file()` in `backend/services/sync_service.py` (lines 246–274) with:

```python
@dataclass
class FrontmatterMergeResult:
    """Result of merging front matter fields semantically."""

    merged: dict[str, Any]
    field_conflicts: list[str]


def merge_frontmatter(
    base: dict[str, Any] | None,
    server: dict[str, Any],
    client: dict[str, Any],
) -> FrontmatterMergeResult:
    """Merge front matter fields semantically.

    Rules:
    - modified_at: always stripped (caller sets server time after merge)
    - labels: set-based merge (additions/removals relative to base from both sides)
    - title, author, created_at, draft: if both changed differently, server wins + reported
    - unrecognized fields: if one side changed, take that change; if both, server wins
    """
    if base is None:
        conflicts = [
            k for k in ("title", "author", "created_at", "draft")
            if k in server and k in client and server.get(k) != client.get(k)
        ]
        return FrontmatterMergeResult(merged=dict(server), field_conflicts=conflicts)

    merged: dict[str, Any] = {}
    field_conflicts: list[str] = []

    # Collect all keys except modified_at
    all_keys = (set(base) | set(server) | set(client)) - {"modified_at"}

    for key in all_keys:
        base_val = base.get(key)
        server_val = server.get(key)
        client_val = client.get(key)

        if key == "labels":
            # Set-based merge
            base_set = set(base_val) if isinstance(base_val, list) else set()
            server_set = set(server_val) if isinstance(server_val, list) else set()
            client_set = set(client_val) if isinstance(client_val, list) else set()

            server_added = server_set - base_set
            server_removed = base_set - server_set
            client_added = client_set - base_set
            client_removed = base_set - client_set

            result_set = (base_set | server_added | client_added) - server_removed - client_removed
            merged["labels"] = sorted(result_set)
            continue

        # For all other fields: three-way scalar merge
        server_changed = server_val != base_val
        client_changed = client_val != base_val

        if not server_changed and not client_changed:
            if base_val is not None:
                merged[key] = base_val
        elif server_changed and not client_changed:
            if server_val is not None:
                merged[key] = server_val
        elif not server_changed and client_changed:
            if client_val is not None:
                merged[key] = client_val
        else:
            # Both changed
            if server_val == client_val:
                if server_val is not None:
                    merged[key] = server_val
            else:
                # Conflict: server wins
                if server_val is not None:
                    merged[key] = server_val
                if key in ("title", "author", "created_at", "draft"):
                    field_conflicts.append(key)

    return FrontmatterMergeResult(merged=merged, field_conflicts=field_conflicts)
```

Add `from typing import Any` to imports (line 12) if not already there.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_services/test_frontmatter_merge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/sync_service.py tests/test_services/test_frontmatter_merge.py
git commit -m "feat: add semantic front matter merge with set-based labels"
```

---

### Task 3: Add hybrid merge function

Create `merge_post_file()` that splits a markdown file into front matter + body, merges them separately (front matter semantically, body via `git merge-file`), and reassembles.

**Files:**
- Modify: `backend/services/sync_service.py`
- Test: `tests/test_services/test_hybrid_merge.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_services/test_hybrid_merge.py`:

```python
"""Tests for hybrid merge: semantic front matter + git merge-file body."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from backend.services.git_service import GitService
from backend.services.sync_service import PostMergeResult, merge_post_file


class TestMergePostFile:
    def _make_post(self, meta: dict, body: str) -> str:
        post = frontmatter.Post(body, **meta)
        return frontmatter.dumps(post) + "\n"

    def test_clean_body_merge(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        meta = {"title": "T", "author": "A", "labels": ["#a"]}
        base = self._make_post(meta, "Para one.\n\nPara two.\n")
        server = self._make_post(meta, "Para one (server).\n\nPara two.\n")
        client = self._make_post(meta, "Para one.\n\nPara two (client).\n")
        result = merge_post_file(base, server, client, git)
        assert not result.body_conflicted
        assert result.field_conflicts == []
        parsed = frontmatter.loads(result.merged_content)
        assert "server" in parsed.content
        assert "client" in parsed.content

    def test_body_conflict_server_wins(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        meta = {"title": "T"}
        base = self._make_post(meta, "original line\n")
        server = self._make_post(meta, "server version\n")
        client = self._make_post(meta, "client version\n")
        result = merge_post_file(base, server, client, git)
        assert result.body_conflicted
        parsed = frontmatter.loads(result.merged_content)
        assert "server version" in parsed.content

    def test_labels_merged_as_sets(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = self._make_post({"title": "T", "labels": ["#a"]}, "body\n")
        server = self._make_post({"title": "T", "labels": ["#a", "#b"]}, "body\n")
        client = self._make_post({"title": "T", "labels": ["#a", "#c"]}, "body\n")
        result = merge_post_file(base, server, client, git)
        parsed = frontmatter.loads(result.merged_content)
        assert set(parsed["labels"]) == {"#a", "#b", "#c"}

    def test_modified_at_stripped(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = self._make_post({"title": "T", "modified_at": "2026-01-01"}, "body\n")
        server = self._make_post({"title": "T", "modified_at": "2026-01-02"}, "body\n")
        client = self._make_post({"title": "T", "modified_at": "2026-01-03"}, "body\n")
        result = merge_post_file(base, server, client, git)
        parsed = frontmatter.loads(result.merged_content)
        assert "modified_at" not in parsed.metadata

    def test_title_conflict_reported(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        base = self._make_post({"title": "Original"}, "body\n")
        server = self._make_post({"title": "Server Title"}, "body\n")
        client = self._make_post({"title": "Client Title"}, "body\n")
        result = merge_post_file(base, server, client, git)
        assert "title" in result.field_conflicts
        parsed = frontmatter.loads(result.merged_content)
        assert parsed["title"] == "Server Title"

    def test_no_base_server_wins(self, tmp_path: Path) -> None:
        git = GitService(tmp_path)
        git.init_repo()
        server = self._make_post({"title": "Server"}, "server body\n")
        client = self._make_post({"title": "Client"}, "client body\n")
        result = merge_post_file(None, server, client, git)
        assert result.body_conflicted
        assert "title" in result.field_conflicts
        parsed = frontmatter.loads(result.merged_content)
        assert parsed["title"] == "Server"
        assert "server body" in parsed.content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_services/test_hybrid_merge.py -v`
Expected: FAIL with `ImportError: cannot import name 'PostMergeResult'`

**Step 3: Write minimal implementation**

Add to `backend/services/sync_service.py`:

```python
import frontmatter as fm

@dataclass
class PostMergeResult:
    """Result of merging a complete post file (front matter + body)."""

    merged_content: str
    body_conflicted: bool
    field_conflicts: list[str]


def merge_post_file(
    base: str | None,
    server: str,
    client: str,
    git_service: GitService,
) -> PostMergeResult:
    """Merge a markdown post file using hybrid strategy.

    Front matter is merged semantically (set-based labels, server-wins scalars).
    Body is merged via git merge-file. modified_at is stripped before merge.
    """
    server_post = fm.loads(server)
    client_post = fm.loads(client)

    if base is None:
        fm_result = merge_frontmatter(None, dict(server_post.metadata), dict(client_post.metadata))
        return PostMergeResult(
            merged_content=server,
            body_conflicted=True,
            field_conflicts=fm_result.field_conflicts,
        )

    base_post = fm.loads(base)

    # Merge front matter semantically
    fm_result = merge_frontmatter(
        dict(base_post.metadata), dict(server_post.metadata), dict(client_post.metadata)
    )

    # Merge body via git merge-file
    base_body = base_post.content
    server_body = server_post.content
    client_body = client_post.content

    if server_body == client_body:
        merged_body = server_body
        body_conflicted = False
    elif server_body == base_body:
        merged_body = client_body
        body_conflicted = False
    elif client_body == base_body:
        merged_body = server_body
        body_conflicted = False
    else:
        merged_body, body_conflicted = git_service.merge_file_content(
            base_body, server_body, client_body
        )
        if body_conflicted:
            merged_body = server_body

    # Reassemble
    merged_post = fm.Post(merged_body, **fm_result.merged)
    merged_content = fm.dumps(merged_post) + "\n"

    return PostMergeResult(
        merged_content=merged_content,
        body_conflicted=body_conflicted,
        field_conflicts=fm_result.field_conflicts,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_services/test_hybrid_merge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/sync_service.py tests/test_services/test_hybrid_merge.py
git commit -m "feat: add hybrid post merge (semantic frontmatter + git merge-file body)"
```

---

### Task 4: Replace sync API endpoints

Replace `POST /init` with `POST /status`, remove `POST /upload`, update `POST /commit` to accept multipart form data with all files in one request, update schemas.

**Files:**
- Modify: `backend/api/sync.py` (full rewrite of endpoints and schemas)
- Test: `tests/test_services/test_sync_merge_integration.py` (rewrite to match new API)

**Step 1: Write the failing integration tests**

Rewrite `tests/test_services/test_sync_merge_integration.py`:

```python
"""Integration tests for simplified sync protocol."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from backend.config import Settings
from tests.conftest import create_test_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from httpx import AsyncClient


@pytest.fixture
def merge_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    posts_dir = tmp_content_dir / "posts"
    (posts_dir / "shared.md").write_text(
        "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
        "labels:\n- '#a'\n---\n\nParagraph one.\n\nParagraph two.\n"
    )
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret-key-with-at-least-32-characters",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
        admin_username="admin",
        admin_password="admin123",
    )


@pytest.fixture
async def merge_client(merge_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(merge_settings) as ac:
        yield ac


async def _login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return resp.json()["access_token"]


class TestSyncStatus:
    @pytest.mark.asyncio
    async def test_status_returns_plan(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "to_upload" in data
        assert "to_download" in data
        assert "server_commit" in data


class TestSyncCommit:
    @pytest.mark.asyncio
    async def test_clean_body_merge(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        # Get server commit
        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server edits paragraph one via API
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "title": "Shared Post",
                "body": "Paragraph one (server edit).\n\nParagraph two.\n",
                "labels": ["a"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Client edits paragraph two
        client_content = (
            "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
            "labels:\n- '#a'\n---\n\nParagraph one.\n\nParagraph two (client edit).\n"
        )
        resp = await merge_client.post(
            "/api/sync/commit",
            data={
                "metadata": '{"deleted_files": [], "last_sync_commit": "' + server_commit + '"}'
            },
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content.encode()), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["commit_hash"] is not None
        assert len(data["conflicts"]) == 0

        # Verify merged content
        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        merged = dl_resp.content.decode()
        assert "server edit" in merged
        assert "client edit" in merged

    @pytest.mark.asyncio
    async def test_body_conflict_server_wins(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server edits paragraph one
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "title": "Shared Post",
                "body": "Server version of paragraph one.\n\nParagraph two.\n",
                "labels": ["a"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Client also edits paragraph one (conflict)
        client_content = (
            "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
            "labels:\n- '#a'\n---\n\nClient version of paragraph one.\n\nParagraph two.\n"
        )
        resp = await merge_client.post(
            "/api/sync/commit",
            data={
                "metadata": '{"deleted_files": [], "last_sync_commit": "' + server_commit + '"}'
            },
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content.encode()), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conflicts"]) == 1
        assert data["conflicts"][0]["body_conflicted"] is True

        # Server version should be on disk
        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        assert b"Server version" in dl_resp.content

    @pytest.mark.asyncio
    async def test_labels_merged_as_sets(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/status",
            json={"client_manifest": []},
            headers=headers,
        )
        server_commit = resp.json()["server_commit"]

        # Server adds label #b
        resp = await merge_client.put(
            "/api/posts/posts/shared.md",
            json={
                "title": "Shared Post",
                "body": "Paragraph one.\n\nParagraph two.\n",
                "labels": ["a", "b"],
                "is_draft": False,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        # Client adds label #c
        client_content = (
            "---\ntitle: Shared Post\ncreated_at: 2026-02-01 00:00:00+00\nauthor: Admin\n"
            "labels:\n- '#a'\n- '#c'\n---\n\nParagraph one.\n\nParagraph two.\n"
        )
        resp = await merge_client.post(
            "/api/sync/commit",
            data={
                "metadata": '{"deleted_files": [], "last_sync_commit": "' + server_commit + '"}'
            },
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content.encode()), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conflicts"]) == 0

    @pytest.mark.asyncio
    async def test_no_base_server_wins(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        client_content = b"---\ntitle: Different\nauthor: Admin\n---\n\nClient only.\n"
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": '{"deleted_files": [], "last_sync_commit": null}'},
            files=[
                ("files", ("posts/shared.md", io.BytesIO(client_content), "text/plain")),
            ],
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conflicts"]) == 1

    @pytest.mark.asyncio
    async def test_commit_no_changes(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": '{"deleted_files": []}'},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_upload_new_file(self, merge_client: AsyncClient) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        new_content = b"---\ntitle: New Post\nauthor: Admin\n---\n\nBrand new.\n"
        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": '{"deleted_files": []}'},
            files=[
                (
                    "files",
                    ("posts/2026-02-22-new/index.md", io.BytesIO(new_content), "text/plain"),
                ),
            ],
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify file exists
        dl_resp = await merge_client.get(
            "/api/sync/download/posts/2026-02-22-new/index.md", headers=headers
        )
        assert dl_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_file(
        self, merge_client: AsyncClient, merge_settings: Settings
    ) -> None:
        token = await _login(merge_client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await merge_client.post(
            "/api/sync/commit",
            data={"metadata": '{"deleted_files": ["posts/shared.md"]}'},
            headers=headers,
        )
        assert resp.status_code == 200

        dl_resp = await merge_client.get("/api/sync/download/posts/shared.md", headers=headers)
        assert dl_resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_sync_merge_integration.py -v`
Expected: FAIL (old endpoints don't match new API shape)

**Step 3: Rewrite the sync API**

Rewrite `backend/api/sync.py` with new schemas and endpoints. Key changes:
- `POST /init` → `POST /status` (same logic, renamed)
- Remove `POST /upload` endpoint
- `POST /commit` accepts multipart: `files` (UploadFile list) + `metadata` (JSON string with `deleted_files`, `last_sync_commit`)
- Merge logic uses `merge_post_file()` for `.md` files under `posts/`, falls back to server-wins for non-markdown conflicts
- Response includes `conflicts` list with `file_path`, `body_conflicted`, `field_conflicts`
- Response includes `to_download` list (files server changed or merged that client should download)

Replace the imports to use `merge_post_file` and `merge_frontmatter` instead of `merge_file`. Remove `merge_file` from the import list.

The `_sync_commit_inner()` function should:
1. Parse metadata JSON from `metadata` form field
2. Apply deletions
3. Get `pre_upload_head` from git
4. Write uploaded files to disk (replaces the separate upload endpoint)
5. For each uploaded file that also exists on the server with different content (conflict files from the plan): run `merge_post_file()` for `.md` posts, server-wins for others
6. Normalize front matter
7. Git commit, update manifest, rebuild cache
8. Return conflicts + to_download list

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_sync_merge_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/sync.py tests/test_services/test_sync_merge_integration.py
git commit -m "feat: simplify sync API to status + commit endpoints with hybrid merge"
```

---

### Task 5: Simplify CLI sync client

Remove `push()`, `pull()`, and `_upload_file()`. Rewrite `sync()` to call `POST /status` then `POST /commit` (multipart). Update `status()` to use new endpoint. Remove conflict-backup logic.

**Files:**
- Modify: `cli/sync_client.py`
- Test: `tests/test_sync/test_sync_client.py` (rewrite)

**Step 1: Write the failing tests**

Rewrite `tests/test_sync/test_sync_client.py`:

```python
"""Tests for simplified CLI sync client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cli import sync_client
from cli.sync_client import SyncClient

if TYPE_CHECKING:
    from pathlib import Path


class _DummyResponse:
    def __init__(
        self,
        json_data: dict[str, Any] | None = None,
        content: bytes = b"",
        status_code: int = 200,
    ) -> None:
        self._json_data = json_data or {}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._json_data


class _RecordingHttpClient:
    def __init__(self, responses: dict[str, _DummyResponse] | None = None) -> None:
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses or {}

    def post(self, url: str, **kwargs: Any) -> _DummyResponse:
        self.post_calls.append((url, kwargs))
        return self._responses.get(url, _DummyResponse())

    def get(self, url: str, **kwargs: Any) -> _DummyResponse:
        self.get_calls.append((url, kwargs))
        return self._responses.get(url, _DummyResponse())

    def close(self) -> None:
        return None


def _build_sync_client(
    content_dir: Path,
    responses: dict[str, _DummyResponse] | None = None,
) -> tuple[SyncClient, _RecordingHttpClient]:
    client = SyncClient("http://example.com", content_dir, "test-token")
    http_client = _RecordingHttpClient(responses)
    client.client = http_client  # type: ignore[assignment]
    return client, http_client


class TestSyncClientStatus:
    def test_status_calls_new_endpoint(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        client, http_client = _build_sync_client(content_dir)
        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        client.status()
        assert any(url == "/api/sync/status" for url, _ in http_client.post_calls)


class TestSyncClientSync:
    def test_sync_sends_files_in_commit(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "new.md").write_text("# New\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "abc123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": ["posts/new.md"],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        # Verify commit was called with multipart data
        commit_calls = [(url, kw) for url, kw in http_client.post_calls if url == "/api/sync/commit"]
        assert len(commit_calls) == 1

    def test_sync_saves_commit_hash(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "saved123",
                "conflicts": [],
                "to_download": [],
                "warnings": [],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        config = sync_client.load_config(content_dir)
        assert config["last_sync_commit"] == "saved123"

    def test_sync_downloads_server_changed_files(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "dl123",
                "conflicts": [],
                "to_download": ["posts/remote.md"],
                "warnings": [],
            }
        )
        download_resp = _DummyResponse(content=b"# Remote\n\nContent.\n")
        client, http_client = _build_sync_client(
            content_dir,
            responses={
                "/api/sync/commit": commit_resp,
                "/api/sync/download/posts/remote.md": download_resp,
            },
        )
        client.status = lambda: {
            "to_upload": [],
            "to_download": ["posts/remote.md"],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()

        assert (posts_dir / "remote.md").exists()

    def test_sync_reports_conflicts(self, tmp_path: Path, monkeypatch: Any) -> None:
        content_dir = tmp_path / "content"
        posts_dir = content_dir / "posts"
        posts_dir.mkdir(parents=True)
        (posts_dir / "conflict.md").write_text("# Client\n")

        commit_resp = _DummyResponse(
            json_data={
                "status": "ok",
                "commit_hash": "c123",
                "conflicts": [
                    {
                        "file_path": "posts/conflict.md",
                        "body_conflicted": True,
                        "field_conflicts": [],
                    }
                ],
                "to_download": [],
                "warnings": [],
            }
        )
        client, _http_client = _build_sync_client(
            content_dir, responses={"/api/sync/commit": commit_resp}
        )
        client.status = lambda: {
            "to_upload": ["posts/conflict.md"],
            "to_download": [],
            "to_delete_remote": [],
            "to_delete_local": [],
            "conflicts": [],
        }

        monkeypatch.setattr(sync_client, "scan_local_files", lambda _: {})
        monkeypatch.setattr(sync_client, "save_manifest", lambda *_: None)

        client.sync()
        # No crash; conflicts are reported via print (not tested here, just verify no exception)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync/test_sync_client.py -v`
Expected: FAIL (old methods still exist, new endpoint not called)

**Step 3: Rewrite CLI sync client**

In `cli/sync_client.py`:
- Remove `push()`, `pull()`, `_upload_file()` methods
- Update `status()` to call `/api/sync/status` instead of `/api/sync/init`
- Rewrite `sync()`:
  1. Call `self.status()` to get the plan
  2. Collect files to upload from `to_upload` and `conflicts` lists
  3. Build multipart form: `files` list + `metadata` JSON string
  4. POST to `/api/sync/commit`
  5. Download files from response `to_download` list
  6. Delete local files from plan `to_delete_local`
  7. Report conflicts from response
  8. Save commit hash, update manifest
- Remove `push` and `pull` subcommands from `main()`
- Remove conflict-backup logic (`.conflict-backup` files)

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync/test_sync_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/sync_client.py tests/test_sync/test_sync_client.py
git commit -m "feat: simplify CLI to sync-only with multipart commit"
```

---

### Task 6: Remove merge3 dependency and old merge tests

Remove the `merge3` dependency from `pyproject.toml`, delete old merge tests, clean up old imports.

**Files:**
- Modify: `pyproject.toml` (remove `merge3>=0.0.15` from dependencies and import-linter config)
- Delete: `tests/test_services/test_merge.py` (old merge3 tests)
- Modify: `backend/services/sync_service.py` (remove `from merge3 import Merge3` and old `merge_file()`)

**Step 1: Remove merge3 from pyproject.toml**

Remove `"merge3>=0.0.15"` from the `dependencies` list. Remove `"merge3.*"` from the import-linter allowed list if present.

**Step 2: Remove old merge_file function and merge3 import**

In `backend/services/sync_service.py`:
- Remove `from merge3 import Merge3` import
- Remove the old `merge_file()` function (if not already replaced in Task 2)
- Verify no remaining references to `merge_file` (the old one) exist

**Step 3: Delete old test file**

Delete `tests/test_services/test_merge.py`.

**Step 4: Run `uv sync` to update lock file**

Run: `uv sync`

**Step 5: Run full test suite**

Run: `just test`
Expected: PASS (no references to merge3 or old merge_file remain)

**Step 6: Commit**

```bash
git add pyproject.toml backend/services/sync_service.py uv.lock
git rm tests/test_services/test_merge.py
git commit -m "refactor: remove merge3 dependency, replaced by git merge-file"
```

---

### Task 7: Update existing sync tests

Update `tests/test_services/test_sync_service.py` to remove references to the old `merge_file()` function (if any) and verify `compute_sync_plan()` still works (it's unchanged). Update `tests/test_cli/test_sync_client.py` if needed.

**Files:**
- Modify: `tests/test_services/test_sync_service.py` (verify unchanged tests still pass)
- Modify: `tests/test_cli/test_sync_client.py` (verify unchanged tests still pass)
- Modify: `tests/test_cli/test_safe_path.py` (verify unchanged tests still pass)

**Step 1: Run existing sync service tests**

Run: `pytest tests/test_services/test_sync_service.py -v`
Expected: PASS (compute_sync_plan is unchanged)

**Step 2: Run existing CLI tests**

Run: `pytest tests/test_cli/ -v`
Expected: PASS

**Step 3: Run full gate**

Run: `just check`
Expected: PASS

**Step 4: Commit if any adjustments were needed**

```bash
git add -u
git commit -m "test: fix remaining test references after sync simplification"
```

---

### Task 8: Update documentation

Update ARCHITECTURE.md to reflect the simplified sync protocol and CLI.

**Files:**
- Modify: `docs/ARCHITECTURE.md` (sync protocol section, CLI section, merge section, API routes table)

**Step 1: Update the sync protocol section**

Update the "Bidirectional Sync" section:
- Describe the 2-endpoint protocol (`POST /status`, `POST /commit`, `GET /download`)
- Replace the sync protocol diagram with the simplified flow
- Document the hybrid merge strategy (semantic front matter + git merge-file body)
- Update the conflict resolution description (server wins, conflicts reported)
- Remove references to merge3, conflict markers, `.conflict-backup` files

**Step 2: Update the CLI section**

- Remove `push` and `pull` from subcommand list
- Update the sync flow description
- Note interactive password prompt

**Step 3: Update the API routes table**

- Remove `/api/sync/init` and `/api/sync/upload`
- Add `/api/sync/status`
- Update `/api/sync/commit` description

**Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: update architecture for simplified sync protocol"
```

---

### Task 9: Final verification

Run the full check gate and verify everything passes.

**Step 1: Run full gate**

Run: `just check`
Expected: PASS with no warnings, no test failures, no static analysis issues.

**Step 2: Verify no stale references**

Search for any remaining references to:
- `merge3` or `Merge3`
- `sync_upload` or `/api/sync/upload`
- `sync_init` or `/api/sync/init`
- `conflict-backup`
- `merge_file` (old function, not `merge_file_content` or `merge_post_file`)

**Step 3: Final commit if needed**

```bash
git add -u
git commit -m "chore: clean up stale references after sync simplification"
```
