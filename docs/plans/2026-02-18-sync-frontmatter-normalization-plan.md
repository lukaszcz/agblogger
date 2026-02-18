# Sync Front Matter Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-fill missing YAML front matter on synced posts, and switch PostCache timestamps to DateTime columns stored as UTC.

**Architecture:** During `sync_commit`, before scanning files and updating the manifest, normalize front matter for uploaded `.md` files under `posts/`. New posts get default values; edited posts preserve existing values except `modified_at` (set to now). PostCache switches from Text to DateTime(timezone=True) for timestamps.

**Tech Stack:** Python, FastAPI, SQLAlchemy, python-frontmatter, pendulum, pytest

---

### Task 1: Add recognized fields constant to frontmatter.py

**Files:**
- Modify: `backend/filesystem/frontmatter.py:1-10`
- Test: `tests/test_rendering/test_frontmatter.py`

**Step 1: Write the failing test**

Add to `tests/test_rendering/test_frontmatter.py`:

```python
from backend.filesystem.frontmatter import RECOGNIZED_FIELDS

class TestRecognizedFields:
    def test_recognized_fields_contains_expected(self) -> None:
        assert "created_at" in RECOGNIZED_FIELDS
        assert "modified_at" in RECOGNIZED_FIELDS
        assert "author" in RECOGNIZED_FIELDS
        assert "labels" in RECOGNIZED_FIELDS
        assert "draft" in RECOGNIZED_FIELDS

    def test_recognized_fields_is_frozenset(self) -> None:
        assert isinstance(RECOGNIZED_FIELDS, frozenset)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py::TestRecognizedFields -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `backend/filesystem/frontmatter.py` after the imports:

```python
RECOGNIZED_FIELDS: frozenset[str] = frozenset({
    "created_at",
    "modified_at",
    "author",
    "labels",
    "draft",
})
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py::TestRecognizedFields -v`
Expected: PASS

**Step 5: Commit**

```
git add backend/filesystem/frontmatter.py tests/test_rendering/test_frontmatter.py
git commit -m "feat: add RECOGNIZED_FIELDS constant to frontmatter module"
```

---

### Task 2: Implement normalize_post_frontmatter()

**Files:**
- Modify: `backend/services/sync_service.py`
- Test: `tests/test_sync/test_normalize_frontmatter.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_sync/test_normalize_frontmatter.py`:

```python
"""Tests for front matter normalization during sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frontmatter

from backend.services.sync_service import FileEntry, normalize_post_frontmatter


def _entry(path: str, hash_: str = "abc") -> FileEntry:
    return FileEntry(file_path=path, content_hash=hash_, file_size=100, file_mtime="1.0")


class TestNormalizeNewPost:
    """Tests for normalizing a new post (not in old manifest)."""

    def test_fills_missing_created_at(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "new.md").write_text("# Hello\n\nContent.\n")

        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/new.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="Admin",
        )

        post = frontmatter.loads((posts_dir / "new.md").read_text())
        assert "created_at" in post.metadata
        assert "modified_at" in post.metadata
        assert post["author"] == "Admin"
        assert warnings == []

    def test_fills_missing_fields_preserves_existing(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "partial.md").write_text(
            "---\nauthor: Alice\n---\n# Hello\n\nContent.\n"
        )

        normalize_post_frontmatter(
            uploaded_files=["posts/partial.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="Admin",
        )

        post = frontmatter.loads((posts_dir / "partial.md").read_text())
        assert post["author"] == "Alice"  # Preserved, not overwritten
        assert "created_at" in post.metadata  # Filled in

    def test_new_post_created_at_equals_modified_at(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "new.md").write_text("# Hello\n\nContent.\n")

        normalize_post_frontmatter(
            uploaded_files=["posts/new.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        post = frontmatter.loads((posts_dir / "new.md").read_text())
        assert post["created_at"] == post["modified_at"]

    def test_default_labels_empty_list(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "new.md").write_text("# Hello\n\nContent.\n")

        normalize_post_frontmatter(
            uploaded_files=["posts/new.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        post = frontmatter.loads((posts_dir / "new.md").read_text())
        # Labels field should not be added if empty (matches serialize_post behavior)
        assert post.get("labels") is None or post.get("labels") == []

    def test_default_draft_false(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "new.md").write_text("# Hello\n\nContent.\n")

        normalize_post_frontmatter(
            uploaded_files=["posts/new.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        post = frontmatter.loads((posts_dir / "new.md").read_text())
        # Draft false means field omitted (matches serialize_post behavior)
        assert post.get("draft") is None or post.get("draft") is False


class TestNormalizeEditedPost:
    """Tests for normalizing an edited post (in old manifest)."""

    def test_edit_sets_modified_at_to_now(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "existing.md").write_text(
            "---\ncreated_at: 2026-01-01 00:00:00.000000+00:00\n"
            "modified_at: 2026-01-01 00:00:00.000000+00:00\n"
            "author: Admin\n---\n# Hello\n\nUpdated content.\n"
        )

        normalize_post_frontmatter(
            uploaded_files=["posts/existing.md"],
            old_manifest={"posts/existing.md": _entry("posts/existing.md")},
            content_dir=tmp_path,
            default_author="Admin",
        )

        post = frontmatter.loads((posts_dir / "existing.md").read_text())
        # modified_at should be updated (not the original 2026-01-01)
        from backend.services.datetime_service import parse_datetime
        modified = parse_datetime(post["modified_at"])
        assert modified.year >= 2026
        # created_at should be preserved
        created = parse_datetime(post["created_at"])
        assert created.year == 2026
        assert created.month == 1

    def test_edit_preserves_existing_author(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "existing.md").write_text(
            "---\ncreated_at: 2026-01-01 00:00:00.000000+00:00\n"
            "author: OriginalAuthor\n---\n# Hello\n\nContent.\n"
        )

        normalize_post_frontmatter(
            uploaded_files=["posts/existing.md"],
            old_manifest={"posts/existing.md": _entry("posts/existing.md")},
            content_dir=tmp_path,
            default_author="Admin",
        )

        post = frontmatter.loads((posts_dir / "existing.md").read_text())
        assert post["author"] == "OriginalAuthor"

    def test_edit_fills_missing_created_at(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "existing.md").write_text("# Hello\n\nContent.\n")

        normalize_post_frontmatter(
            uploaded_files=["posts/existing.md"],
            old_manifest={"posts/existing.md": _entry("posts/existing.md")},
            content_dir=tmp_path,
            default_author="Admin",
        )

        post = frontmatter.loads((posts_dir / "existing.md").read_text())
        assert "created_at" in post.metadata
        assert "modified_at" in post.metadata


class TestNormalizeUnrecognizedFields:
    """Tests for handling unrecognized front matter fields."""

    def test_unrecognized_field_warns(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "custom.md").write_text(
            "---\ncustom_field: hello\ntags: [a, b]\n---\n# Hello\n\nContent.\n"
        )

        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/custom.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        assert len(warnings) == 2
        assert any("custom_field" in w for w in warnings)
        assert any("tags" in w for w in warnings)

    def test_unrecognized_field_preserved_in_file(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        (posts_dir / "custom.md").write_text(
            "---\ncustom_field: hello\n---\n# Hello\n\nContent.\n"
        )

        normalize_post_frontmatter(
            uploaded_files=["posts/custom.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        post = frontmatter.loads((posts_dir / "custom.md").read_text())
        assert post["custom_field"] == "hello"


class TestNormalizeSkipNonPosts:
    """Tests that non-post files are skipped."""

    def test_skips_non_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "posts").mkdir()
        (tmp_path / "index.toml").write_text("[site]\ntitle = 'Test'\n")

        warnings = normalize_post_frontmatter(
            uploaded_files=["index.toml"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        assert warnings == []

    def test_skips_md_outside_posts(self, tmp_path: Path) -> None:
        (tmp_path / "about.md").write_text("# About\n\nPage content.\n")

        warnings = normalize_post_frontmatter(
            uploaded_files=["about.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )

        # File should not be modified
        content = (tmp_path / "about.md").read_text()
        assert content == "# About\n\nPage content.\n"
        assert warnings == []

    def test_skips_nonexistent_file(self, tmp_path: Path) -> None:
        warnings = normalize_post_frontmatter(
            uploaded_files=["posts/missing.md"],
            old_manifest={},
            content_dir=tmp_path,
            default_author="",
        )
        assert warnings == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sync/test_normalize_frontmatter.py -v`
Expected: FAIL with ImportError (normalize_post_frontmatter doesn't exist)

**Step 3: Write the implementation**

Add to `backend/services/sync_service.py`:

```python
import logging
from datetime import datetime

import frontmatter as fm

from backend.filesystem.frontmatter import RECOGNIZED_FIELDS
from backend.services.datetime_service import format_datetime, now_utc, parse_datetime

logger = logging.getLogger(__name__)


def normalize_post_frontmatter(
    uploaded_files: list[str],
    old_manifest: dict[str, FileEntry],
    content_dir: Path,
    default_author: str,
) -> list[str]:
    """Normalize front matter for uploaded post files.

    For new posts (not in old_manifest): fills missing fields with defaults.
    For edited posts (in old_manifest): preserves existing fields, sets modified_at to now.
    Unrecognized fields are preserved in the file but generate warnings.

    Returns a list of warning messages.
    """
    warnings: list[str] = []
    now = now_utc()

    for file_path in uploaded_files:
        if not file_path.startswith("posts/") or not file_path.endswith(".md"):
            continue

        full_path = (content_dir / file_path).resolve()
        if not full_path.is_relative_to(content_dir.resolve()):
            continue
        if not full_path.exists():
            continue

        raw = full_path.read_text(encoding="utf-8")
        post = fm.loads(raw)
        metadata = post.metadata
        is_edit = file_path in old_manifest

        # Warn on unrecognized fields
        for key in list(metadata.keys()):
            if key not in RECOGNIZED_FIELDS:
                warnings.append(
                    f"Unrecognized front matter field '{key}' in {file_path}"
                )

        # Fill defaults for recognized fields
        if "created_at" not in metadata:
            metadata["created_at"] = format_datetime(now)
        else:
            # Normalize existing timestamp to strict format
            parsed = parse_datetime(metadata["created_at"])
            metadata["created_at"] = format_datetime(parsed)

        if is_edit:
            # Always update modified_at for edits
            metadata["modified_at"] = format_datetime(now)
        elif "modified_at" not in metadata:
            metadata["modified_at"] = metadata["created_at"]
        else:
            parsed = parse_datetime(metadata["modified_at"])
            metadata["modified_at"] = format_datetime(parsed)

        if "author" not in metadata and default_author:
            metadata["author"] = default_author

        # labels and draft: only set if missing, using serialize_post conventions
        # (empty labels and draft=false are omitted, so we don't add them)

        # Rewrite file
        full_path.write_text(fm.dumps(post) + "\n", encoding="utf-8")

    return warnings
```

Also add `from pathlib import Path` to the TYPE_CHECKING imports (it's already used there).

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sync/test_normalize_frontmatter.py -v`
Expected: PASS

**Step 5: Commit**

```
git add backend/services/sync_service.py tests/test_sync/test_normalize_frontmatter.py
git commit -m "feat: add normalize_post_frontmatter for sync uploads"
```

---

### Task 3: Wire normalization into sync_commit endpoint

**Files:**
- Modify: `backend/api/sync.py:60-65` (SyncCommitRequest)
- Modify: `backend/api/sync.py:155-181` (sync_commit endpoint)
- Modify: `cli/sync_client.py:131-134` (push commit), `cli/sync_client.py:165-169` (pull commit), `cli/sync_client.py:222-225` (sync commit)
- Test: `tests/test_api/test_api_integration.py`

**Step 1: Write the failing integration test**

Add to `tests/test_api/test_api_integration.py`, in class `TestSync`:

```python
@pytest.mark.asyncio
async def test_sync_upload_normalizes_frontmatter(self, client: AsyncClient) -> None:
    """Uploading a post with missing front matter gets defaults filled."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload a post with no front matter
    content = b"# New Synced Post\n\nContent here.\n"
    resp = await client.post(
        "/api/sync/upload",
        params={"file_path": "posts/synced-new.md"},
        files={"file": ("synced-new.md", io.BytesIO(content), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200

    # Commit with uploaded_files
    resp = await client.post(
        "/api/sync/commit",
        json={"resolutions": {}, "uploaded_files": ["posts/synced-new.md"]},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify the post is accessible and has timestamps
    resp = await client.get("/api/posts/posts/synced-new.md")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Synced Post"
    assert data["created_at"] is not None
    assert data["modified_at"] is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestSync::test_sync_upload_normalizes_frontmatter -v`
Expected: FAIL (uploaded_files not accepted or normalization not called)

**Step 3: Implement the changes**

In `backend/api/sync.py`, update `SyncCommitRequest`:

```python
class SyncCommitRequest(BaseModel):
    """Resolution decisions for conflicts."""

    resolutions: dict[str, str]
    uploaded_files: list[str] = Field(default_factory=list)
```

In `backend/api/sync.py`, update `sync_commit`:

```python
@router.post("/commit", response_model=SyncCommitResponse)
async def sync_commit(
    body: SyncCommitRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> SyncCommitResponse:
    """Finalize sync: normalize front matter, update manifest and regenerate caches."""
    # Load old manifest before updating (needed for new-vs-edit detection)
    old_manifest = await get_server_manifest(session)

    # Normalize front matter for uploaded post files
    fm_warnings = normalize_post_frontmatter(
        uploaded_files=body.uploaded_files,
        old_manifest=old_manifest,
        content_dir=content_manager.content_dir,
        default_author=content_manager.site_config.default_author,
    )

    # Scan current server state after uploads/downloads + normalization
    current_files = scan_content_files(content_manager.content_dir)

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
    )
```

Add the import at the top of `backend/api/sync.py`:

```python
from backend.services.sync_service import normalize_post_frontmatter
```

In `cli/sync_client.py`, update the three commit calls to include `uploaded_files`:

For `push()` (line ~131): track which files were uploaded, pass to commit:

```python
def push(self) -> None:
    """Push local changes to server."""
    plan = self.status()

    uploaded_files: list[str] = []
    for file_path in plan.get("to_upload", []):
        full_path = self.content_dir / file_path
        if not full_path.exists():
            print(f"  Skip (missing): {file_path}")
            continue
        with open(full_path, "rb") as f:
            resp = self.client.post(
                "/api/sync/upload",
                files={"file": (file_path, f)},
                data={"file_path": file_path},
            )
            resp.raise_for_status()
        print(f"  Uploaded: {file_path}")
        uploaded_files.append(file_path)

    # Commit
    resp = self.client.post(
        "/api/sync/commit",
        json={"resolutions": {}, "uploaded_files": uploaded_files},
    )
    resp.raise_for_status()

    # Update local manifest
    local_files = scan_local_files(self.content_dir)
    save_manifest(self.content_dir, local_files)

    print(f"Push complete. {len(uploaded_files)} file(s) uploaded.")
```

For `pull()` (line ~165): no uploads, pass empty list:

```python
json={"resolutions": {}, "uploaded_files": []},
```

For `sync()` (line ~222): track uploaded files similarly to push:

```python
# Track uploads
uploaded_files: list[str] = []
for file_path in plan.get("to_upload", []):
    ...
    uploaded_files.append(file_path)

# ...

# Commit
resp = self.client.post(
    "/api/sync/commit",
    json={"resolutions": resolutions, "uploaded_files": uploaded_files},
)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestSync -v`
Expected: PASS

**Step 5: Commit**

```
git add backend/api/sync.py cli/sync_client.py tests/test_api/test_api_integration.py
git commit -m "feat: wire front matter normalization into sync commit"
```

---

### Task 4: Switch PostCache timestamps to DateTime columns

**Files:**
- Modify: `backend/models/post.py:1-39`
- Modify: `backend/services/cache_service.py:94-104`
- Modify: `backend/api/posts.py:111-173` (create), `backend/api/posts.py:176-256` (update)
- Test: `tests/test_api/test_api_integration.py`

**Step 1: Run existing tests to confirm they pass before changes**

Run: `uv run pytest tests/ -v`
Expected: PASS (baseline)

**Step 2: Update the PostCache model**

In `backend/models/post.py`, change:

```python
from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
```

And update the timestamp columns:

```python
from datetime import datetime

class PostCache(Base):
    ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**Step 3: Update cache_service.py**

In `backend/services/cache_service.py`, change how PostCache rows are created (lines 94-104). Remove `format_datetime` import and usage:

```python
post = PostCache(
    file_path=post_data.file_path,
    title=post_data.title,
    author=post_data.author,
    created_at=post_data.created_at,
    modified_at=post_data.modified_at,
    is_draft=post_data.is_draft,
    content_hash=content_h,
    excerpt=excerpt,
    rendered_html=rendered_html,
)
```

Remove the `format_datetime` import from `cache_service.py` if it's no longer used there.

**Step 4: Update api/posts.py**

In `create_post_endpoint` (line ~138): pass datetime objects directly:

```python
post = PostCache(
    file_path=body.file_path,
    title=post_data.title,
    author=post_data.author,
    created_at=post_data.created_at,
    modified_at=post_data.modified_at,
    ...
)
```

In `update_post_endpoint` (line ~227): pass datetime objects:

```python
existing.modified_at = now
```

In both create and update response construction, format at the boundary:

```python
from backend.services.datetime_service import format_iso

return PostDetail(
    ...
    created_at=format_iso(post_data.created_at),
    modified_at=format_iso(post_data.modified_at),
    ...
)
```

In `get_post_for_edit` (line ~88): format at the boundary:

```python
return PostEditResponse(
    ...
    created_at=format_iso(post_data.created_at),
    modified_at=format_iso(post_data.modified_at),
    ...
)
```

**Step 5: Update post_service.py**

In `list_posts` (lines 54-59), parse date strings to datetimes for filtering:

```python
from backend.services.datetime_service import parse_datetime

if from_date:
    from_dt = parse_datetime(from_date + " 00:00:00", default_tz="UTC")
    stmt = stmt.where(PostCache.created_at >= from_dt)

if to_date:
    to_dt = parse_datetime(to_date + " 23:59:59", default_tz="UTC")
    stmt = stmt.where(PostCache.created_at <= to_dt)
```

In `list_posts` PostSummary construction (lines 129-139), format datetimes:

```python
from backend.services.datetime_service import format_iso

PostSummary(
    ...
    created_at=format_iso(post.created_at),
    modified_at=format_iso(post.modified_at),
    ...
)
```

In `get_post` (lines 166-178), format datetimes:

```python
return PostDetail(
    ...
    created_at=format_iso(post.created_at),
    modified_at=format_iso(post.modified_at),
    ...
)
```

In `search_posts` (lines 196-206): the raw SQL returns text from SQLite. Parse it:

```python
SearchResult(
    ...
    created_at=format_iso(r[4]) if isinstance(r[4], datetime) else str(r[4]),
    ...
)
```

Note: The FTS join uses raw SQL (`p.created_at`), and SQLAlchemy will return datetime objects since the column type is now DateTime. Verify this works.

**Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: PASS. Some tests may need minor adjustments to timestamp assertions (the API now returns ISO format like `2026-02-02T22:21:29.975359+00:00` instead of `2026-02-02 22:21:29.975359+00:00`).

**Step 7: Commit**

```
git add backend/models/post.py backend/services/cache_service.py backend/api/posts.py backend/services/post_service.py
git commit -m "refactor: switch PostCache timestamps to DateTime columns stored as UTC"
```

---

### Task 5: Add integration test for front matter normalization with unrecognized fields

**Files:**
- Modify: `tests/test_api/test_api_integration.py`

**Step 1: Write the test**

Add to `TestSync` in `tests/test_api/test_api_integration.py`:

```python
@pytest.mark.asyncio
async def test_sync_commit_warns_on_unrecognized_fields(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    content = b"---\ncustom_field: hello\n---\n# Post\n\nContent.\n"
    resp = await client.post(
        "/api/sync/upload",
        params={"file_path": "posts/custom-fields.md"},
        files={"file": ("custom-fields.md", io.BytesIO(content), "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/sync/commit",
        json={"resolutions": {}, "uploaded_files": ["posts/custom-fields.md"]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any("custom_field" in w for w in data["warnings"])

@pytest.mark.asyncio
async def test_sync_commit_backward_compatible_no_uploaded_files(
    self, client: AsyncClient
) -> None:
    """Commit without uploaded_files field still works (backward compatibility)."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/sync/commit",
        json={"resolutions": {}},
        headers=headers,
    )
    assert resp.status_code == 200
```

**Step 2: Run tests**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestSync -v`
Expected: PASS

**Step 3: Commit**

```
git add tests/test_api/test_api_integration.py
git commit -m "test: add integration tests for sync front matter normalization"
```

---

### Task 6: Fix existing tests and run full check

**Files:**
- Modify: various test files if assertions on timestamp format changed

**Step 1: Run full check**

Run: `just check`

**Step 2: Fix any failures**

Common issues:
- Tests asserting on string timestamp format (`"2026-02-02 22:21:29..."`) may need updating to ISO format (`"2026-02-02T22:21:29..."`)
- Type checker may flag datetime vs string mismatches
- Ruff may flag unused imports

**Step 3: Run full check again**

Run: `just check`
Expected: All checks pass

**Step 4: Commit any fixes**

```
git add -A
git commit -m "fix: update tests for DateTime column changes"
```

---

### Task 7: Update ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update the relevant sections**

Add to the Sync Protocol section a note about front matter normalization:

> During `sync_commit`, before scanning files and updating the manifest, the server normalizes front matter for uploaded `.md` files under `posts/`. New posts get default values (timestamps, author from site config). Edited posts preserve existing values except `modified_at`, which is set to the current server time. Unrecognized front matter fields are preserved but generate warnings in the commit response.

Update the Database Models section to note:

> `PostCache` timestamps (`created_at`, `modified_at`) are stored as `DateTime(timezone=True)` in UTC.

Update the CLI Sync Client section to note that `uploaded_files` is sent in the commit request.

**Step 2: Commit**

```
git add docs/ARCHITECTURE.md
git commit -m "docs: update architecture for sync front matter normalization"
```

---

### Task 8: Final verification

**Step 1: Run full check**

Run: `just check`
Expected: All checks pass (mypy, ruff, pytest, tsc, eslint, vitest)

**Step 2: Manual browser test**

Start dev server with `just dev`. Use the Playwright MCP to:
1. Navigate to the timeline page, verify posts display with timestamps
2. Create a new post via the editor, verify timestamps appear
3. Verify date filtering still works on the timeline
