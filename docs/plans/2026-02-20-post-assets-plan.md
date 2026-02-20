# Post Assets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable post-per-directory structure with co-located assets, file uploads in the editor, relative path resolution in rendered HTML, and directory renaming on title change with symlink preservation.

**Architecture:** New posts are created in `posts/<slug>/index.md`. A content-serving API endpoint (`GET /api/content/{path}`) serves assets publicly. Relative paths in rendered HTML are rewritten to absolute `/api/content/...` paths. The editor gains file upload with auto-insert. On title change, directories rename with symlink at old path.

**Tech Stack:** FastAPI `FileResponse`, Python `pathlib`/`shutil`/`os.symlink`, `python-multipart` for file uploads, React drag-and-drop + file input.

---

### Task 1: Slug generation utility

**Files:**
- Create: `backend/services/slug_service.py`
- Test: `tests/test_services/test_slug_service.py`

**Step 1: Write the failing tests**

```python
"""Tests for slug generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.slug_service import generate_post_slug, generate_post_path


class TestGeneratePostSlug:
    def test_basic_title(self) -> None:
        assert generate_post_slug("My Great Post") == "my-great-post"

    def test_special_characters(self) -> None:
        assert generate_post_slug("Hello, World! (2026)") == "hello-world-2026"

    def test_unicode(self) -> None:
        assert generate_post_slug("Café & Résumé") == "cafe-resume"

    def test_long_title_truncated(self) -> None:
        slug = generate_post_slug("a " * 100)
        assert len(slug) <= 80

    def test_leading_trailing_hyphens_stripped(self) -> None:
        assert generate_post_slug("---hello---") == "hello"

    def test_empty_title_fallback(self) -> None:
        slug = generate_post_slug("")
        assert slug == "untitled"

    def test_whitespace_only_fallback(self) -> None:
        slug = generate_post_slug("   ")
        assert slug == "untitled"


class TestGeneratePostPath:
    def test_basic(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        path = generate_post_path("My Post", posts_dir)
        # Should match YYYY-MM-DD-my-post/index.md
        assert path.name == "index.md"
        assert path.parent.name.endswith("-my-post")
        assert path.parent.name[:10].count("-") == 2  # date prefix

    def test_collision_appends_suffix(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        path1 = generate_post_path("My Post", posts_dir)
        path1.parent.mkdir(parents=True)
        path2 = generate_post_path("My Post", posts_dir)
        assert path1.parent != path2.parent
        assert "-2" in path2.parent.name

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        posts_dir = tmp_path / "posts"
        posts_dir.mkdir()
        for i in range(3):
            p = generate_post_path("Same Title", posts_dir)
            p.parent.mkdir(parents=True)
        # Should have created same-title, same-title-2, same-title-3
        dirs = sorted(d.name for d in posts_dir.iterdir() if d.is_dir())
        assert len(dirs) == 3
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_services/test_slug_service.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
"""Post slug generation and path utilities."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_SLUG_MAX_LENGTH = 80


def generate_post_slug(title: str) -> str:
    """Generate a URL-safe slug from a post title."""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    if not text:
        return "untitled"
    return text[:_SLUG_MAX_LENGTH].rstrip("-")


def generate_post_path(title: str, posts_dir: Path) -> Path:
    """Generate a unique post directory path under posts_dir.

    Returns the full path to the index.md file inside the new directory.
    """
    slug = generate_post_slug(title)
    date_prefix = date.today().isoformat()
    base_name = f"{date_prefix}-{slug}"

    candidate = posts_dir / base_name
    if not candidate.exists():
        return candidate / "index.md"

    counter = 2
    while True:
        candidate = posts_dir / f"{base_name}-{counter}"
        if not candidate.exists():
            return candidate / "index.md"
        counter += 1
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_services/test_slug_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/slug_service.py tests/test_services/test_slug_service.py
git commit -m "feat: add slug generation utility for post directories"
```

---

### Task 2: Content file serving endpoint

**Files:**
- Create: `backend/api/content.py`
- Modify: `backend/main.py:236-244` (register router)
- Test: `tests/test_api/test_content_api.py`

**Step 1: Write the failing tests**

```python
"""Tests for the content file serving API."""
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
def content_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
    posts_dir = tmp_content_dir / "posts"
    post_dir = posts_dir / "2026-02-20-test-post"
    post_dir.mkdir()
    (post_dir / "index.md").write_text(
        "---\ntitle: Test Post\ncreated_at: 2026-02-20 00:00:00+00\n---\nContent\n"
    )
    (post_dir / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

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
async def client(content_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(content_settings) as ac:
        yield ac


class TestContentServing:
    @pytest.mark.asyncio
    async def test_serve_image(self, client: AsyncClient) -> None:
        resp = await client.get("/api/content/posts/2026-02-20-test-post/photo.png")
        assert resp.status_code == 200
        assert "image/png" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_serve_nonexistent_file(self, client: AsyncClient) -> None:
        resp = await client.get("/api/content/posts/2026-02-20-test-post/nope.jpg")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, client: AsyncClient) -> None:
        resp = await client.get("/api/content/posts/../../etc/passwd")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_disallowed_prefix_blocked(self, client: AsyncClient) -> None:
        resp = await client.get("/api/content/index.toml")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_no_auth_required(self, client: AsyncClient) -> None:
        """Content serving is public — no auth needed."""
        resp = await client.get("/api/content/posts/2026-02-20-test-post/photo.png")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_follows_symlinks(
        self, client: AsyncClient, content_settings: Settings
    ) -> None:
        posts_dir = content_settings.content_dir / "posts"
        (posts_dir / "old-link").symlink_to(posts_dir / "2026-02-20-test-post")
        resp = await client.get("/api/content/posts/old-link/photo.png")
        assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api/test_content_api.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Create `backend/api/content.py`:

```python
"""Content file serving API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.deps import get_settings
from backend.config import Settings

router = APIRouter(prefix="/api/content", tags=["content"])

_ALLOWED_PREFIXES = ("posts/", "assets/")


@router.get("/{file_path:path}")
async def serve_content_file(
    file_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve a file from the content directory (public, read-only)."""
    if ".." in file_path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not any(file_path.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        raise HTTPException(status_code=403, detail="Access denied")

    full_path = (settings.content_dir / file_path).resolve()
    if not full_path.is_relative_to(settings.content_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)
```

Register in `backend/main.py` — add import and `app.include_router(content_router)` alongside other routers:

```python
from backend.api.content import router as content_router
# ... in create_app():
app.include_router(content_router)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api/test_content_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/content.py backend/main.py tests/test_api/test_content_api.py
git commit -m "feat: add public content file serving endpoint"
```

---

### Task 3: Relative path rewriting in rendered HTML

**Files:**
- Modify: `backend/pandoc/renderer.py` (add `rewrite_relative_urls` function)
- Modify: `backend/api/posts.py` (apply rewriting after render)
- Modify: `backend/services/cache_service.py` (apply rewriting during cache rebuild)
- Test: `tests/test_rendering/test_url_rewriting.py`

**Step 1: Write the failing tests**

```python
"""Tests for relative URL rewriting in rendered HTML."""
from __future__ import annotations

from backend.pandoc.renderer import rewrite_relative_urls


class TestRewriteRelativeUrls:
    def test_rewrite_img_src(self) -> None:
        html = '<img src="photo.png" alt="pic">'
        result = rewrite_relative_urls(html, "posts/2026-02-20-my-post/index.md")
        assert result == '<img src="/api/content/posts/2026-02-20-my-post/photo.png" alt="pic">'

    def test_rewrite_relative_dot_slash(self) -> None:
        html = '<img src="./photo.png" alt="pic">'
        result = rewrite_relative_urls(html, "posts/2026-02-20-my-post/index.md")
        assert result == '<img src="/api/content/posts/2026-02-20-my-post/photo.png" alt="pic">'

    def test_skip_absolute_url(self) -> None:
        html = '<img src="https://example.com/img.png" alt="pic">'
        result = rewrite_relative_urls(html, "posts/2026-02-20-my-post/index.md")
        assert 'src="https://example.com/img.png"' in result

    def test_skip_data_uri(self) -> None:
        html = '<img src="data:image/png;base64,abc" alt="pic">'
        result = rewrite_relative_urls(html, "posts/my-post/index.md")
        assert 'src="data:image/png;base64,abc"' in result

    def test_skip_fragment(self) -> None:
        html = '<a href="#section1">link</a>'
        result = rewrite_relative_urls(html, "posts/my-post/index.md")
        assert 'href="#section1"' in result

    def test_skip_absolute_path(self) -> None:
        html = '<a href="/about">link</a>'
        result = rewrite_relative_urls(html, "posts/my-post/index.md")
        assert 'href="/about"' in result

    def test_rewrite_a_href(self) -> None:
        html = '<a href="doc.pdf">Download</a>'
        result = rewrite_relative_urls(html, "posts/my-post/index.md")
        assert 'href="/api/content/posts/my-post/doc.pdf"' in result

    def test_flat_post_no_rewrite(self) -> None:
        """Flat posts (e.g. posts/hello.md) have no directory for relative assets."""
        html = '<img src="photo.png" alt="pic">'
        result = rewrite_relative_urls(html, "posts/hello.md")
        assert 'src="/api/content/posts/photo.png"' in result

    def test_multiple_attributes(self) -> None:
        html = '<img src="a.png" alt="a"><a href="b.pdf">b</a>'
        result = rewrite_relative_urls(html, "posts/my-post/index.md")
        assert 'src="/api/content/posts/my-post/a.png"' in result
        assert 'href="/api/content/posts/my-post/b.pdf"' in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rendering/test_url_rewriting.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Add to `backend/pandoc/renderer.py`:

```python
def rewrite_relative_urls(html: str, file_path: str) -> str:
    """Rewrite relative src/href URLs in HTML to absolute /api/content/ paths.

    file_path is the post's path relative to the content directory,
    e.g. "posts/2026-02-20-my-post/index.md".
    """
    from posixpath import dirname, normpath

    base_dir = dirname(file_path)

    def _replace(match: re.Match[str]) -> str:
        attr = match.group(1)  # src or href
        url = match.group(2)
        if url.startswith(("/", "#", "data:", "http:", "https:", "mailto:", "tel:")):
            return match.group(0)
        # Normalize ./foo to foo
        clean = url.removeprefix("./")
        resolved = normpath(f"{base_dir}/{clean}")
        return f'{attr}="/api/content/{resolved}"'

    return re.sub(r'(src|href)="([^"]*)"', _replace, html)
```

Modify `backend/api/posts.py` — in `create_post_endpoint` and `update_post_endpoint`, apply `rewrite_relative_urls` to `rendered_html` and `rendered_excerpt` before storing:

```python
from backend.pandoc.renderer import render_markdown, rewrite_relative_urls

# In create_post_endpoint, after rendering:
rendered_excerpt = rewrite_relative_urls(rendered_excerpt, body.file_path) if rendered_excerpt else ""
rendered_html = rewrite_relative_urls(rendered_html, body.file_path)

# In update_post_endpoint, similarly after rendering:
rendered_excerpt = rewrite_relative_urls(rendered_excerpt, file_path) if rendered_excerpt else ""
rendered_html = rewrite_relative_urls(rendered_html, file_path)
```

Modify `backend/services/cache_service.py` — in `rebuild_cache`, after rendering:

```python
from backend.pandoc.renderer import render_markdown, rewrite_relative_urls

# After render_markdown calls:
rendered_html = rewrite_relative_urls(rendered_html, post_data.file_path)
rendered_excerpt = rewrite_relative_urls(rendered_excerpt, post_data.file_path)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rendering/test_url_rewriting.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/pandoc/renderer.py backend/api/posts.py backend/services/cache_service.py tests/test_rendering/test_url_rewriting.py
git commit -m "feat: rewrite relative URLs in rendered HTML to /api/content/ paths"
```

---

### Task 4: Post-per-directory creation in backend

**Files:**
- Modify: `backend/schemas/post.py:42-68` (PostCreate — remove file_path, return generated path)
- Modify: `backend/api/posts.py:190-266` (create endpoint uses slug service)
- Test: `tests/test_api/test_post_directory.py`

The `PostCreate` schema currently requires the client to supply `file_path`. With post-per-directory, the server generates the path from the title. Remove `file_path` from `PostCreate`. The create endpoint generates the path using `generate_post_path`.

**Step 1: Write the failing tests**

```python
"""Tests for post-per-directory creation."""
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
def dir_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
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
async def client(dir_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(dir_settings) as ac:
        yield ac


async def login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    return resp.json()["access_token"]


class TestPostDirectoryCreation:
    @pytest.mark.asyncio
    async def test_create_post_generates_directory(
        self, client: AsyncClient, dir_settings: Settings
    ) -> None:
        token = await login(client)
        resp = await client.post(
            "/api/posts",
            json={"title": "My New Post", "body": "Hello world", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "/index.md" in data["file_path"]
        assert "my-new-post" in data["file_path"]
        # Verify file exists on disk
        full_path = dir_settings.content_dir / data["file_path"]
        assert full_path.exists()

    @pytest.mark.asyncio
    async def test_create_post_collision_handling(
        self, client: AsyncClient
    ) -> None:
        token = await login(client)
        resp1 = await client.post(
            "/api/posts",
            json={"title": "Duplicate", "body": "First", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201
        resp2 = await client.post(
            "/api/posts",
            json={"title": "Duplicate", "body": "Second", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 201
        assert resp1.json()["file_path"] != resp2.json()["file_path"]

    @pytest.mark.asyncio
    async def test_created_post_accessible(self, client: AsyncClient) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Accessible Post", "body": "Content here", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        file_path = create_resp.json()["file_path"]
        get_resp = await client.get(f"/api/posts/{file_path}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Accessible Post"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api/test_post_directory.py -v`
Expected: FAIL (422 because file_path missing)

**Step 3: Write implementation**

Modify `backend/schemas/post.py` — remove `file_path` from `PostCreate`:

```python
class PostCreate(BaseModel):
    """Request to create a new post."""

    title: str = Field(min_length=1, max_length=500, description="Post title")
    body: str = Field(min_length=1, max_length=500_000, description="Markdown body without front matter")
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v
```

Modify `backend/api/posts.py` `create_post_endpoint`:

```python
from backend.services.slug_service import generate_post_path

# Replace body.file_path usage with:
post_path = generate_post_path(body.title, content_manager.content_dir / "posts")
file_path = str(post_path.relative_to(content_manager.content_dir))

# Use file_path everywhere body.file_path was used
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api/test_post_directory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/schemas/post.py backend/api/posts.py tests/test_api/test_post_directory.py
git commit -m "feat: auto-generate post-per-directory on create"
```

---

### Task 5: File upload endpoint

**Files:**
- Modify: `backend/api/posts.py` (add upload endpoint)
- Test: `tests/test_api/test_post_assets_upload.py`

**Step 1: Write the failing tests**

```python
"""Tests for post asset upload."""
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


class TestAssetUpload:
    @pytest.mark.asyncio
    async def test_upload_file(
        self, client: AsyncClient, upload_settings: Settings
    ) -> None:
        token = await login(client)
        # Create a post first
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Upload Test", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        file_path = create_resp.json()["file_path"]

        # Upload a file
        resp = await client.post(
            f"/api/posts/{file_path}/assets",
            files={"files": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "photo.png" in data["uploaded"]

        # Verify file exists on disk
        post_dir = (upload_settings.content_dir / file_path).parent
        assert (post_dir / "photo.png").exists()

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/posts/posts/fake/index.md/assets",
            files={"files": ("photo.png", b"data", "image/png")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_post(self, client: AsyncClient) -> None:
        token = await login(client)
        resp = await client.post(
            "/api/posts/posts/nonexistent/index.md/assets",
            files={"files": ("photo.png", b"data", "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, client: AsyncClient) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Large Upload", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        file_path = create_resp.json()["file_path"]

        large_data = b"\x00" * (11 * 1024 * 1024)  # 11 MB
        resp = await client.post(
            f"/api/posts/{file_path}/assets",
            files={"files": ("huge.bin", large_data, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_uploaded_file_accessible_via_content_api(
        self, client: AsyncClient
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Serve Test", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        file_path = create_resp.json()["file_path"]

        await client.post(
            f"/api/posts/{file_path}/assets",
            files={"files": ("img.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Access via content API
        post_dir = "/".join(file_path.split("/")[:-1])  # remove index.md
        resp = await client.get(f"/api/content/{post_dir}/img.png")
        assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api/test_post_assets_upload.py -v`
Expected: FAIL (404 or 405)

**Step 3: Write implementation**

Add to `backend/api/posts.py`:

```python
from fastapi import UploadFile, File

_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/{file_path:path}/assets")
async def upload_assets(
    file_path: str,
    files: list[UploadFile],
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    user: Annotated[User, Depends(require_auth)],
) -> dict[str, list[str]]:
    """Upload asset files to a post's directory."""
    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Post not found")

    post_dir = (content_manager.content_dir / file_path).parent
    uploaded: list[str] = []

    for upload_file in files:
        content = await upload_file.read()
        if len(content) > _MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large: {upload_file.filename}")
        filename = Path(upload_file.filename or "upload").name  # strip directory components
        if not filename or filename.startswith("."):
            raise HTTPException(status_code=400, detail=f"Invalid filename: {upload_file.filename}")
        dest = post_dir / filename
        dest.write_bytes(content)
        uploaded.append(filename)

    if uploaded:
        git_service.try_commit(f"Upload assets to {file_path}: {', '.join(uploaded)}")

    return {"uploaded": uploaded}
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api/test_post_assets_upload.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/posts.py tests/test_api/test_post_assets_upload.py
git commit -m "feat: add asset upload endpoint for posts"
```

---

### Task 6: Directory rename with symlink on title change

**Files:**
- Modify: `backend/api/posts.py:269-359` (update endpoint — rename logic)
- Test: `tests/test_api/test_post_rename.py`

**Step 1: Write the failing tests**

```python
"""Tests for post directory rename on title change."""
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
def rename_settings(tmp_content_dir: Path, tmp_path: Path) -> Settings:
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
async def client(rename_settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with create_test_client(rename_settings) as ac:
        yield ac


async def login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    return resp.json()["access_token"]


class TestPostRename:
    @pytest.mark.asyncio
    async def test_rename_changes_directory(
        self, client: AsyncClient, rename_settings: Settings
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Original Title", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        old_path = create_resp.json()["file_path"]

        update_resp = await client.put(
            f"/api/posts/{old_path}",
            json={"title": "New Title", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_resp.status_code == 200
        new_path = update_resp.json()["file_path"]
        assert "new-title" in new_path
        assert new_path != old_path

    @pytest.mark.asyncio
    async def test_rename_creates_symlink(
        self, client: AsyncClient, rename_settings: Settings
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Symlink Test", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        old_path = create_resp.json()["file_path"]
        old_dir = (rename_settings.content_dir / old_path).parent

        await client.put(
            f"/api/posts/{old_path}",
            json={"title": "Renamed Post", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Old directory should be a symlink
        assert old_dir.is_symlink()

    @pytest.mark.asyncio
    async def test_rename_preserves_assets(
        self, client: AsyncClient, rename_settings: Settings
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Asset Keep", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        old_path = create_resp.json()["file_path"]

        # Upload asset
        await client.post(
            f"/api/posts/{old_path}/assets",
            files={"files": ("img.png", b"\x89PNG" + b"\x00" * 10, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )

        update_resp = await client.put(
            f"/api/posts/{old_path}",
            json={"title": "Asset Renamed", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        new_path = update_resp.json()["file_path"]
        new_dir = (rename_settings.content_dir / new_path).parent
        assert (new_dir / "img.png").exists()

    @pytest.mark.asyncio
    async def test_no_rename_when_slug_unchanged(
        self, client: AsyncClient
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Same Slug", "body": "Content", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        old_path = create_resp.json()["file_path"]

        # Same title, different case — slug is the same
        update_resp = await client.put(
            f"/api/posts/{old_path}",
            json={"title": "Same Slug", "body": "Updated", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_resp.json()["file_path"] == old_path

    @pytest.mark.asyncio
    async def test_old_url_still_works_via_symlink(
        self, client: AsyncClient
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "URL Compat", "body": "Hello", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        old_path = create_resp.json()["file_path"]

        update_resp = await client.put(
            f"/api/posts/{old_path}",
            json={"title": "URL Compat Renamed", "body": "Hello", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        new_path = update_resp.json()["file_path"]
        assert new_path != old_path

        # Old path should still be accessible via content API
        old_dir = "/".join(old_path.split("/")[:-1])
        resp = await client.get(f"/api/content/{old_dir}/index.md")
        assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api/test_post_rename.py -v`
Expected: FAIL

**Step 3: Write implementation**

Modify `backend/api/posts.py` `update_post_endpoint` to detect title slug change and rename:

```python
import os
import shutil
from backend.services.slug_service import generate_post_slug

# In update_post_endpoint, after writing the post but before commit:
# Check if directory should rename (only for index.md posts)
new_file_path = file_path
if file_path.endswith("/index.md"):
    old_dir = (content_manager.content_dir / file_path).parent
    old_dir_name = old_dir.name
    # Extract date prefix from current directory name
    date_prefix = old_dir_name[:10] if len(old_dir_name) > 10 else ""
    old_slug = old_dir_name[11:] if len(old_dir_name) > 11 else old_dir_name
    new_slug = generate_post_slug(body.title)

    if new_slug != old_slug:
        new_dir_name = f"{date_prefix}-{new_slug}" if date_prefix else new_slug
        new_dir = old_dir.parent / new_dir_name
        # Handle collision
        if new_dir.exists():
            counter = 2
            while new_dir.exists():
                new_dir = old_dir.parent / f"{new_dir_name}-{counter}"
                counter += 1
        shutil.move(str(old_dir), str(new_dir))
        os.symlink(new_dir.name, str(old_dir))
        new_file_path = str(new_dir.relative_to(content_manager.content_dir)) + "/index.md"
        # Update DB cache with new path
        existing.file_path = new_file_path
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api/test_post_rename.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/posts.py tests/test_api/test_post_rename.py
git commit -m "feat: rename post directory on title change with symlink"
```

---

### Task 7: Frontend — remove file_path field, auto-generate slug

**Files:**
- Modify: `frontend/src/pages/EditorPage.tsx` (remove file_path input for new posts)
- Modify: `frontend/src/api/posts.ts` (remove file_path from createPost params)

**Step 1: Modify EditorPage.tsx**

Remove the file_path input field, the `newPath` state, `pathManuallyEdited` ref, and the slug generation `useEffect`. The server now handles path generation.

Remove from `PostCreate` params in `api/posts.ts`:
```typescript
export async function createPost(params: {
  title: string
  body: string
  labels: string[]
  is_draft: boolean
}): Promise<PostDetail> {
  return api.post('posts', { json: params }).json<PostDetail>()
}
```

In `EditorPage.tsx`, update `handleSave`:
```typescript
if (isNew) {
  const result = await createPost({ title, body, labels, is_draft: isDraft })
  markSaved()
  void navigate(`/post/${result.file_path}`)
} else {
  const result = await updatePost(filePath, { title, body, labels, is_draft: isDraft })
  markSaved()
  void navigate(`/post/${result.file_path}`)
}
```

Note: For updates, navigate to `result.file_path` since it may have changed due to rename.

Remove the file path display/edit section entirely from the JSX.

**Step 2: Update auto-save state**

Remove `newPath` from `DraftData` interface and auto-save usage since path is server-generated.

**Step 3: Commit**

```bash
git add frontend/src/pages/EditorPage.tsx frontend/src/api/posts.ts frontend/src/hooks/useEditorAutoSave.ts
git commit -m "feat: remove file_path from editor, server generates post path"
```

---

### Task 8: Frontend — file upload in editor

**Files:**
- Modify: `frontend/src/api/posts.ts` (add uploadAssets function)
- Modify: `frontend/src/pages/EditorPage.tsx` (add upload button + drag-drop)

**Step 1: Add API function**

```typescript
export async function uploadAssets(
  filePath: string,
  files: File[],
): Promise<{ uploaded: string[] }> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  return api.post(`posts/${filePath}/assets`, { body: form }).json<{ uploaded: string[] }>()
}
```

**Step 2: Add upload UI to EditorPage**

Add an upload button in the editor toolbar (between the metadata panel and the editor grid). The button triggers a hidden `<input type="file">`. On file selection or drag-and-drop onto the textarea:

1. Upload files via `uploadAssets()`
2. For each uploaded file, insert markdown at cursor:
   - Images (png, jpg, gif, webp, svg): `![filename](filename)`
   - Other files: `[filename](filename)`

Add drag-and-drop handler on the textarea.

The upload button should be disabled when `saving` is true or when `isNew` (must save post first).

**Step 3: Commit**

```bash
git add frontend/src/pages/EditorPage.tsx frontend/src/api/posts.ts
git commit -m "feat: add file upload button and drag-drop to editor"
```

---

### Task 9: Delete post — clean up directory and symlinks

**Files:**
- Modify: `backend/api/posts.py:362-397` (delete endpoint — remove directory)
- Modify: `backend/filesystem/content_manager.py:131-137` (enhance delete_post)
- Test: `tests/test_api/test_post_directory.py` (add delete test)

Currently `delete_post` only removes the single `.md` file. For directory-based posts, we need to remove the entire directory and any symlinks pointing to it.

**Step 1: Write the failing test**

Add to `tests/test_api/test_post_directory.py`:

```python
class TestPostDirectoryDeletion:
    @pytest.mark.asyncio
    async def test_delete_removes_directory(
        self, client: AsyncClient, dir_settings: Settings
    ) -> None:
        token = await login(client)
        create_resp = await client.post(
            "/api/posts",
            json={"title": "Delete Me", "body": "Gone", "labels": [], "is_draft": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        file_path = create_resp.json()["file_path"]
        post_dir = (dir_settings.content_dir / file_path).parent

        # Upload an asset
        await client.post(
            f"/api/posts/{file_path}/assets",
            files={"files": ("img.png", b"\x89PNG" + b"\x00" * 10, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.delete(
            f"/api/posts/{file_path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        assert not post_dir.exists()
```

**Step 2: Write implementation**

Modify `ContentManager.delete_post` to handle directory-based posts:

```python
def delete_post(self, rel_path: str) -> bool:
    """Delete a post from disk. For index.md posts, removes the entire directory."""
    import shutil

    full_path = self._validate_path(rel_path)
    if not full_path.exists():
        return False

    if full_path.name == "index.md":
        post_dir = full_path.parent
        # Remove symlinks pointing to this directory
        parent = post_dir.parent
        for item in parent.iterdir():
            if item.is_symlink() and item.resolve() == post_dir.resolve():
                item.unlink()
        shutil.rmtree(post_dir)
    else:
        full_path.unlink()
    return True
```

**Step 3: Run tests, commit**

```bash
python -m pytest tests/test_api/test_post_directory.py -v
git add backend/filesystem/content_manager.py tests/test_api/test_post_directory.py
git commit -m "feat: delete entire directory for index.md posts"
```

---

### Task 10: Update ARCHITECTURE.md and run full checks

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update ARCHITECTURE.md**

Add sections covering:
- Post-per-directory structure under "Markdown as Source of Truth"
- Content file serving endpoint under "API Routes"
- File upload endpoint under "API Routes"
- Relative URL rewriting under "Rendering Pipeline"
- Directory rename with symlink under "Updating a Post"

**Step 2: Run full checks**

```bash
just check
```

Fix any issues.

**Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: update architecture for post directories and file uploads"
```

---

### Task 11: Browser testing with Playwright MCP

**Files:** None (testing only)

**Step 1: Start dev server**

```bash
just start
```

**Step 2: Test the flow**

Using Playwright MCP:
1. Log in
2. Create a new post — verify no file_path input, post is created successfully
3. Upload an image in the editor — verify it appears and markdown is inserted
4. View the post — verify the image renders correctly
5. Edit the post title — verify the URL changes, old URL still works via symlink
6. Delete the post — verify the directory is cleaned up

**Step 3: Stop dev server and clean up screenshots**

```bash
just stop
```

Remove any leftover `*.png` files.
