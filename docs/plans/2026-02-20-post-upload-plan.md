# Post Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to upload markdown posts (single file or folder with assets) via the Web UI, applying the same YAML frontmatter processing as the sync protocol.

**Architecture:** A new `POST /api/posts/upload` endpoint accepts multipart files, finds the markdown file, normalizes frontmatter using the same `parse_post()` + default-filling logic as sync, generates a post-per-directory path, writes all files, and returns the created post. The frontend adds an upload button on the Timeline page with file/folder selection and a title-prompt fallback dialog.

**Tech Stack:** FastAPI `UploadFile`, existing `parse_post()` from `backend/filesystem/frontmatter.py`, existing `generate_post_path()` from slug service, React file input with `webkitdirectory`.

---

### Task 1: Backend upload endpoint — tests

**Files:**
- Create: `tests/test_api/test_post_upload.py`

**Step 1: Write the failing tests**

```python
"""Tests for post upload endpoint."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backend.config import Settings
from tests.conftest import create_test_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from httpx import AsyncClient


@pytest.fixture
def upload_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    db_path = tmp_path / "test.db"
    return Settings(
        secret_key="test-secret",
        debug=True,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        content_dir=tmp_content_dir,
        frontend_dir=tmp_path / "frontend",
        admin_username="admin",
        admin_password="admin123",
    )


@pytest.fixture
async def client(upload_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(upload_settings) as ac:
        yield ac


async def login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    return resp.json()["access_token"]


class TestPostUpload:
    @pytest.mark.asyncio
    async def test_upload_single_markdown_file(
        self, client: AsyncClient, upload_settings: Settings
    ) -> None:
        """Upload a single .md file with front matter creates a post."""
        token = await login(client)
        md_content = (
            "---\ntitle: My Uploaded Post\nlabels: []\n---\n\nHello world!\n"
        )
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("my-post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Uploaded Post"
        assert "index.md" in data["file_path"]
        assert "my-uploaded-post" in data["file_path"]
        # File exists on disk
        assert (upload_settings.content_dir / data["file_path"]).exists()

    @pytest.mark.asyncio
    async def test_upload_markdown_with_heading_title(
        self, client: AsyncClient
    ) -> None:
        """Upload markdown without title field extracts title from first heading."""
        token = await login(client)
        md_content = "# Great Heading\n\nBody text here.\n"
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Great Heading"

    @pytest.mark.asyncio
    async def test_upload_no_title_returns_422(self, client: AsyncClient) -> None:
        """Upload markdown with no title and no heading returns 422."""
        token = await login(client)
        md_content = "Just some text without any heading or front matter.\n"
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "no_title"

    @pytest.mark.asyncio
    async def test_upload_no_title_with_title_param(self, client: AsyncClient) -> None:
        """Upload markdown with no title but title query param succeeds."""
        token = await login(client)
        md_content = "Just some text without any heading.\n"
        resp = await client.post(
            "/api/posts/upload?title=User%20Provided%20Title",
            files={"files": ("post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "User Provided Title"

    @pytest.mark.asyncio
    async def test_upload_folder_with_assets(
        self, client: AsyncClient, upload_settings: Settings
    ) -> None:
        """Upload index.md + asset files creates post with assets."""
        token = await login(client)
        md_content = "---\ntitle: Folder Post\n---\n\n![photo](photo.png)\n"
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        resp = await client.post(
            "/api/posts/upload",
            files=[
                ("files", ("index.md", md_content.encode(), "text/markdown")),
                ("files", ("photo.png", png_bytes, "image/png")),
            ],
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Folder Post"
        # Asset exists in the post directory
        post_dir = (upload_settings.content_dir / data["file_path"]).parent
        assert (post_dir / "photo.png").exists()

    @pytest.mark.asyncio
    async def test_upload_no_markdown_returns_422(self, client: AsyncClient) -> None:
        """Upload with no .md file returns 422."""
        token = await login(client)
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("photo.png", b"\x89PNG", "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert "No markdown file" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, client: AsyncClient) -> None:
        """Upload without auth returns 401."""
        md_content = "---\ntitle: Test\n---\nBody\n"
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("test.md", md_content.encode(), "text/markdown")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_preserves_frontmatter_timestamps(
        self, client: AsyncClient
    ) -> None:
        """Uploaded file with existing timestamps preserves them."""
        token = await login(client)
        md_content = (
            "---\ntitle: Timestamped\n"
            "created_at: 2025-01-15 10:30:00+00:00\n"
            "modified_at: 2025-06-20 14:00:00+00:00\n"
            "---\nBody\n"
        )
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "2025-01-15" in data["created_at"]
        assert "2025-06-20" in data["modified_at"]

    @pytest.mark.asyncio
    async def test_upload_draft_post(self, client: AsyncClient) -> None:
        """Uploaded file with draft: true creates a draft post."""
        token = await login(client)
        md_content = "---\ntitle: Draft Post\ndraft: true\n---\nDraft body\n"
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("post.md", md_content.encode(), "text/markdown")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["is_draft"] is True

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, client: AsyncClient) -> None:
        """Uploading a file over 10 MB returns 413."""
        token = await login(client)
        large_data = b"\x00" * (11 * 1024 * 1024)
        resp = await client.post(
            "/api/posts/upload",
            files={"files": ("huge.bin", large_data, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 413
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api/test_post_upload.py -v`
Expected: FAIL (404 — endpoint doesn't exist)

**Step 3: Commit tests**

```bash
git add tests/test_api/test_post_upload.py
git commit -m "test: add failing tests for post upload endpoint"
```

---

### Task 2: Backend upload endpoint — implementation

**Files:**
- Modify: `backend/api/posts.py` (add upload_post endpoint)

**Step 1: Implement the upload endpoint**

Add this to `backend/api/posts.py`, after the existing `upload_assets` endpoint and before the `get_post_endpoint`:

```python
@router.post("/upload", response_model=PostDetail, status_code=201)
async def upload_post(
    files: list[UploadFile],
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
    title: str | None = Query(None),
) -> PostDetail:
    """Upload a markdown post (single file or folder with assets).

    Accepts multipart files. One file must be a ``.md`` file (prefer ``index.md``
    if multiple). Applies the same YAML frontmatter normalization as the sync
    protocol: fills missing timestamps, author, and title.
    """
    # Collect all file data
    file_data: list[tuple[str, bytes]] = []
    for upload_file in files:
        content = await upload_file.read()
        if len(content) > _MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {upload_file.filename}",
            )
        filename = FilePath(upload_file.filename or "upload").name
        file_data.append((filename, content))

    # Find the markdown file
    md_files = [(name, data) for name, data in file_data if name.endswith(".md")]
    if not md_files:
        raise HTTPException(status_code=422, detail="No markdown file found in upload")

    # Prefer index.md if present
    md_file = next(
        ((name, data) for name, data in md_files if name == "index.md"),
        md_files[0],
    )
    md_filename, md_bytes = md_file
    raw_content = md_bytes.decode("utf-8")

    # Parse post using existing frontmatter parser
    post_data = content_manager.read_post_from_string(raw_content, title_override=title)
    if not post_data:
        raise HTTPException(status_code=422, detail="Failed to parse markdown file")

    # Check if title was resolved
    if post_data.title == "Untitled" and title is None:
        raise HTTPException(status_code=422, detail="no_title")

    # Fill author if not present
    if not post_data.author:
        post_data.author = user.display_name or user.username

    # Generate post directory
    posts_dir = content_manager.content_dir / "posts"
    post_path = generate_post_path(post_data.title, posts_dir)
    file_path = str(post_path.relative_to(content_manager.content_dir))
    post_data.file_path = file_path

    # Write all files to the directory
    post_dir = post_path.parent
    post_dir.mkdir(parents=True, exist_ok=True)
    for name, data in file_data:
        if name == md_filename:
            continue  # Will be written by write_post
        dest = post_dir / FilePath(name).name
        dest.write_bytes(data)

    # Render and create cache entry
    md_excerpt = generate_markdown_excerpt(post_data.content)
    rendered_excerpt = await render_markdown(md_excerpt) if md_excerpt else ""
    rendered_html = await render_markdown(post_data.content)
    rendered_excerpt = rewrite_relative_urls(rendered_excerpt, file_path)
    rendered_html = rewrite_relative_urls(rendered_html, file_path)

    serialized = serialize_post(post_data)
    post = PostCache(
        file_path=file_path,
        title=post_data.title,
        author=post_data.author,
        created_at=post_data.created_at,
        modified_at=post_data.modified_at,
        is_draft=post_data.is_draft,
        content_hash=hash_content(serialized),
        rendered_excerpt=rendered_excerpt,
        rendered_html=rendered_html,
    )
    session.add(post)
    await session.flush()
    await _replace_post_labels(session, post_id=post.id, labels=post_data.labels)
    await _upsert_post_fts(
        session,
        post_id=post.id,
        title=post_data.title,
        content=post_data.content,
    )

    try:
        content_manager.write_post(file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write uploaded post %s: %s", file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(post)
    git_service.try_commit(f"Upload post: {file_path}")

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=format_iso(post.created_at),
        modified_at=format_iso(post.modified_at),
        is_draft=post.is_draft,
        rendered_excerpt=post.rendered_excerpt,
        labels=post_data.labels,
        rendered_html=rendered_html,
    )
```

**Step 2: Add `read_post_from_string` to ContentManager**

Add this method to `backend/filesystem/content_manager.py`:

```python
def read_post_from_string(
    self, raw_content: str, *, title_override: str | None = None
) -> PostData:
    """Parse a post from raw markdown string (for upload)."""
    post_data = parse_post(
        raw_content,
        file_path="",
        default_tz=self.site_config.timezone,
        default_author=self.site_config.default_author,
    )
    if title_override and (not post_data.title or post_data.title == "Untitled"):
        post_data.title = title_override
    return post_data
```

**IMPORTANT — Route ordering:** The `/upload` route must appear **before** `/{file_path:path}` routes in the router, otherwise FastAPI will match `upload` as a `file_path`. Place it after the existing `upload_assets` endpoint (which is `/{file_path:path}/assets`) but before the `get_post_endpoint` (`/{file_path:path}`). Actually, `upload` should be placed right after the search endpoint and before any `{file_path:path}` routes since it's a fixed path.

Move the `upload_post` endpoint to be right after `search_endpoint` and before `get_post_for_edit`.

**Step 3: Run tests**

Run: `python -m pytest tests/test_api/test_post_upload.py -v`
Expected: PASS

Run: `python -m pytest --tb=short -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/api/posts.py backend/filesystem/content_manager.py
git commit -m "feat: add post upload endpoint with frontmatter normalization"
```

---

### Task 3: Frontend — upload API function and upload UI on Timeline page

**Files:**
- Modify: `frontend/src/api/posts.ts` (add `uploadPost` function)
- Modify: `frontend/src/pages/TimelinePage.tsx` (add upload button + title dialog)

**Step 1: Add `uploadPost` function to `frontend/src/api/posts.ts`**

```typescript
export async function uploadPost(
  files: File[],
  title?: string,
): Promise<PostDetail> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  const searchParams = title ? { title } : undefined
  return api
    .post('posts/upload', { body: form, searchParams })
    .json<PostDetail>()
}
```

**Step 2: Add upload button and title dialog to TimelinePage**

Add to `TimelinePage.tsx`:

1. Import additions: `Upload` from lucide-react, `useNavigate` from react-router-dom, `uploadPost` from `@/api/posts`, `HTTPError` from `@/api/client`, `useAuthStore` from `@/stores/authStore`
2. Add state: `uploading`, `titlePrompt` (object with files + resolve callback or null)
3. Add two hidden file inputs: one for single file (`accept=".md,.markdown"`), one for folder (`webkitdirectory`)
4. Add upload handler that calls `uploadPost`, handles `no_title` 422 by showing dialog, navigates on success
5. Add title prompt modal dialog
6. Add upload button row (visible only when `user` is logged in), between the FilterPanel and the post list

The upload button should be a simple row with two buttons: "Upload file" and "Upload folder". Show only when user is authenticated. Disable during upload.

**Step 3: Verify**

Run: `cd frontend && npx tsc --noEmit`
Run: `cd frontend && npx vitest run`

**Step 4: Commit**

```bash
git add frontend/src/api/posts.ts frontend/src/pages/TimelinePage.tsx
git commit -m "feat: add post upload UI to timeline page"
```

---

### Task 4: Update ARCHITECTURE.md and run full checks

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Add upload documentation**

Add to the API Routes table:
- Update the `posts` row to mention upload

Add a new data flow section "Uploading a Post (File)":
```
POST /api/posts/upload (multipart, auth required)
    → Find .md file among uploads (prefer index.md)
    → Parse frontmatter via parse_post()
    → Fill defaults: timestamps, author, title extraction
    → Generate post-per-directory path from title
    → Write all files to new directory
    → Render HTML, create PostCache, git commit
    → Return PostDetail
```

**Step 2: Run full checks**

```bash
just check
```

Fix any issues.

**Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add post upload to architecture documentation"
```
