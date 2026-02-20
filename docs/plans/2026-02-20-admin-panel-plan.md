# Admin Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an admin panel at `/admin` that allows site administrators to edit site settings, manage top-level navigation pages (including reorder, rename, hide, add, remove, and inline markdown editing), and change the admin password.

**Architecture:** New `backend/api/admin.py` router with admin-only endpoints protected by `require_admin`. New `backend/schemas/admin.py` for request/response models. New `backend/services/admin_service.py` for business logic. A `write_site_config()` function in `toml_manager.py` for writing `index.toml`. Frontend gets `AdminPage.tsx` with three sections, `frontend/src/api/admin.ts` for API calls, and a gear icon in the Header for admin users.

**Tech Stack:** FastAPI, Pydantic, tomli-w, SQLAlchemy (async), React, TypeScript, Zustand, ky, Tailwind CSS, lucide-react icons

---

### Task 1: Add `write_site_config()` to TOML Manager

**Files:**
- Modify: `backend/filesystem/toml_manager.py:109` (after `write_labels_config`)
- Test: `tests/test_services/test_toml_manager.py` (create)

**Step 1: Write the failing test**

Create `tests/test_services/test_toml_manager.py`:

```python
"""Tests for TOML manager read/write roundtrip."""

from __future__ import annotations

from pathlib import Path

from backend.filesystem.toml_manager import (
    PageConfig,
    SiteConfig,
    parse_site_config,
    write_site_config,
)


def test_write_site_config_roundtrip(tmp_path: Path) -> None:
    config = SiteConfig(
        title="My Test Blog",
        description="A test blog",
        default_author="Test Author",
        timezone="America/New_York",
        pages=[
            PageConfig(id="timeline", title="Posts"),
            PageConfig(id="about", title="About", file="about.md"),
            PageConfig(id="labels", title="Tags"),
        ],
    )
    # Write initial index.toml so file exists
    (tmp_path / "index.toml").write_text("[site]\n")

    write_site_config(tmp_path, config)
    result = parse_site_config(tmp_path)

    assert result.title == "My Test Blog"
    assert result.description == "A test blog"
    assert result.default_author == "Test Author"
    assert result.timezone == "America/New_York"
    assert len(result.pages) == 3
    assert result.pages[0].id == "timeline"
    assert result.pages[1].id == "about"
    assert result.pages[1].file == "about.md"
    assert result.pages[2].id == "labels"
    assert result.pages[2].file is None


def test_write_site_config_preserves_pages_without_file(tmp_path: Path) -> None:
    config = SiteConfig(
        title="Blog",
        pages=[
            PageConfig(id="timeline", title="Posts"),
        ],
    )
    (tmp_path / "index.toml").write_text("[site]\n")

    write_site_config(tmp_path, config)
    result = parse_site_config(tmp_path)

    assert result.pages[0].file is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_toml_manager.py -v`
Expected: FAIL with `ImportError: cannot import name 'write_site_config'`

**Step 3: Write minimal implementation**

Add to `backend/filesystem/toml_manager.py` after `write_labels_config()`:

```python
def write_site_config(content_dir: Path, config: SiteConfig) -> None:
    """Write site configuration back to index.toml."""
    site_data: dict[str, Any] = {
        "title": config.title,
        "description": config.description,
        "default_author": config.default_author,
        "timezone": config.timezone,
    }

    pages_data: list[dict[str, Any]] = []
    for page in config.pages:
        entry: dict[str, Any] = {"id": page.id, "title": page.title}
        if page.file is not None:
            entry["file"] = page.file
        pages_data.append(entry)

    index_path = content_dir / "index.toml"
    index_path.write_bytes(
        tomli_w.dumps({"site": site_data, "pages": pages_data}).encode("utf-8")
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_toml_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/filesystem/toml_manager.py tests/test_services/test_toml_manager.py
git commit -m "feat: add write_site_config to TOML manager"
```

---

### Task 2: Add Backend Admin Schemas

**Files:**
- Create: `backend/schemas/admin.py`

**Step 1: Create the schemas**

```python
"""Admin panel request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SiteSettingsUpdate(BaseModel):
    """Request to update site settings."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    default_author: str = Field(default="", max_length=100)
    timezone: str = Field(default="UTC", max_length=100)


class SiteSettingsResponse(BaseModel):
    """Site settings response."""

    title: str
    description: str
    default_author: str
    timezone: str


class AdminPageConfig(BaseModel):
    """Page config for admin panel — includes hidden flag."""

    id: str
    title: str
    file: str | None = None
    is_builtin: bool = False
    content: str | None = None


class AdminPagesResponse(BaseModel):
    """Response for admin pages listing."""

    pages: list[AdminPageConfig]


class PageCreate(BaseModel):
    """Request to create a new page."""

    id: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=200)


class PageUpdate(BaseModel):
    """Request to update a page's title and/or content."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=500_000)


class PageOrderItem(BaseModel):
    """A single page in the reorder list."""

    id: str
    title: str
    file: str | None = None


class PageOrderUpdate(BaseModel):
    """Request to update page order."""

    pages: list[PageOrderItem]


class PasswordChange(BaseModel):
    """Request to change admin password."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
```

**Step 2: Commit**

```bash
git add backend/schemas/admin.py
git commit -m "feat: add admin panel Pydantic schemas"
```

---

### Task 3: Add Backend Admin Service

**Files:**
- Create: `backend/services/admin_service.py`
- Test: `tests/test_services/test_admin_service.py` (create)

**Step 1: Write the failing tests**

Create `tests/test_services/test_admin_service.py`:

```python
"""Tests for admin service."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import PageConfig, SiteConfig, parse_site_config
from backend.services.admin_service import (
    create_page,
    delete_page,
    get_admin_pages,
    get_site_settings,
    update_page_order,
    update_site_settings,
)


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    d = tmp_path / "content"
    d.mkdir()
    (d / "posts").mkdir()
    (d / "index.toml").write_text(
        '[site]\ntitle = "Test Blog"\ntimezone = "UTC"\n\n'
        '[[pages]]\nid = "timeline"\ntitle = "Posts"\n\n'
        '[[pages]]\nid = "about"\ntitle = "About"\nfile = "about.md"\n\n'
        '[[pages]]\nid = "labels"\ntitle = "Labels"\n'
    )
    (d / "labels.toml").write_text("[labels]\n")
    (d / "about.md").write_text("# About\n\nAbout page content.\n")
    return d


@pytest.fixture
def cm(content_dir: Path) -> ContentManager:
    return ContentManager(content_dir=content_dir)


class TestGetSiteSettings:
    def test_returns_current_settings(self, cm: ContentManager) -> None:
        result = get_site_settings(cm)
        assert result.title == "Test Blog"
        assert result.timezone == "UTC"


class TestUpdateSiteSettings:
    def test_updates_settings(self, cm: ContentManager) -> None:
        result = update_site_settings(
            cm, title="New Title", description="desc", default_author="Author", timezone="US/Eastern"
        )
        assert result.title == "New Title"
        assert result.description == "desc"

        # Verify persisted
        reloaded = parse_site_config(cm.content_dir)
        assert reloaded.title == "New Title"
        assert reloaded.default_author == "Author"

    def test_preserves_pages(self, cm: ContentManager) -> None:
        update_site_settings(cm, title="Changed", description="", default_author="", timezone="UTC")
        reloaded = parse_site_config(cm.content_dir)
        assert len(reloaded.pages) == 3


class TestGetAdminPages:
    def test_returns_pages_with_content(self, cm: ContentManager) -> None:
        pages = get_admin_pages(cm)
        assert len(pages) == 3
        assert pages[0].id == "timeline"
        assert pages[0].is_builtin is True
        assert pages[1].id == "about"
        assert pages[1].content == "# About\n\nAbout page content.\n"
        assert pages[2].id == "labels"
        assert pages[2].is_builtin is True


class TestCreatePage:
    def test_creates_page(self, cm: ContentManager) -> None:
        result = create_page(cm, page_id="contact", title="Contact")
        assert result.id == "contact"
        assert (cm.content_dir / "contact.md").exists()

        reloaded = parse_site_config(cm.content_dir)
        assert any(p.id == "contact" for p in reloaded.pages)

    def test_duplicate_id_raises(self, cm: ContentManager) -> None:
        with pytest.raises(ValueError, match="already exists"):
            create_page(cm, page_id="about", title="About 2")


class TestDeletePage:
    def test_deletes_page_and_file(self, cm: ContentManager) -> None:
        delete_page(cm, page_id="about", delete_file=True)
        reloaded = parse_site_config(cm.content_dir)
        assert not any(p.id == "about" for p in reloaded.pages)
        assert not (cm.content_dir / "about.md").exists()

    def test_deletes_page_keeps_file(self, cm: ContentManager) -> None:
        delete_page(cm, page_id="about", delete_file=False)
        reloaded = parse_site_config(cm.content_dir)
        assert not any(p.id == "about" for p in reloaded.pages)
        assert (cm.content_dir / "about.md").exists()

    def test_delete_builtin_raises(self, cm: ContentManager) -> None:
        with pytest.raises(ValueError, match="Cannot delete built-in"):
            delete_page(cm, page_id="timeline", delete_file=False)

    def test_delete_nonexistent_raises(self, cm: ContentManager) -> None:
        with pytest.raises(ValueError, match="not found"):
            delete_page(cm, page_id="nope", delete_file=False)


class TestUpdatePageOrder:
    def test_reorders_pages(self, cm: ContentManager) -> None:
        new_order = [
            PageConfig(id="labels", title="Tags"),
            PageConfig(id="timeline", title="Home"),
            PageConfig(id="about", title="About", file="about.md"),
        ]
        update_page_order(cm, new_order)
        reloaded = parse_site_config(cm.content_dir)
        assert [p.id for p in reloaded.pages] == ["labels", "timeline", "about"]
        assert reloaded.pages[0].title == "Tags"
        assert reloaded.pages[1].title == "Home"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_admin_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.admin_service'`

**Step 3: Write the implementation**

Create `backend/services/admin_service.py`:

```python
"""Admin panel business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.filesystem.toml_manager import (
    PageConfig,
    SiteConfig,
    write_site_config,
)

if TYPE_CHECKING:
    from backend.filesystem.content_manager import ContentManager

BUILTIN_PAGE_IDS = {"timeline", "labels"}


def get_site_settings(cm: ContentManager) -> SiteConfig:
    """Return current site settings."""
    return cm.site_config


def update_site_settings(
    cm: ContentManager,
    *,
    title: str,
    description: str,
    default_author: str,
    timezone: str,
) -> SiteConfig:
    """Update site settings in index.toml and reload config."""
    cfg = cm.site_config
    updated = SiteConfig(
        title=title,
        description=description,
        default_author=default_author,
        timezone=timezone,
        pages=cfg.pages,
    )
    write_site_config(cm.content_dir, updated)
    cm.reload_config()
    return cm.site_config


def get_admin_pages(cm: ContentManager) -> list[dict]:
    """Return all pages with metadata for admin panel."""
    result = []
    for page in cm.site_config.pages:
        content = None
        if page.file:
            page_path = cm.content_dir / page.file
            if page_path.exists():
                content = page_path.read_text(encoding="utf-8")
        result.append({
            "id": page.id,
            "title": page.title,
            "file": page.file,
            "is_builtin": page.id in BUILTIN_PAGE_IDS,
            "content": content,
        })
    return result


def create_page(cm: ContentManager, *, page_id: str, title: str) -> PageConfig:
    """Create a new page entry and .md file."""
    cfg = cm.site_config
    if any(p.id == page_id for p in cfg.pages):
        msg = f"Page '{page_id}' already exists"
        raise ValueError(msg)

    file_name = f"{page_id}.md"
    md_path = cm.content_dir / file_name
    md_path.write_text(f"# {title}\n", encoding="utf-8")

    new_page = PageConfig(id=page_id, title=title, file=file_name)
    updated = SiteConfig(
        title=cfg.title,
        description=cfg.description,
        default_author=cfg.default_author,
        timezone=cfg.timezone,
        pages=[*cfg.pages, new_page],
    )
    write_site_config(cm.content_dir, updated)
    cm.reload_config()
    return new_page


def update_page(
    cm: ContentManager,
    page_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
) -> None:
    """Update a page's title and/or content."""
    cfg = cm.site_config
    page = next((p for p in cfg.pages if p.id == page_id), None)
    if page is None:
        msg = f"Page '{page_id}' not found"
        raise ValueError(msg)

    if title is not None:
        pages = [
            PageConfig(id=p.id, title=title if p.id == page_id else p.title, file=p.file)
            for p in cfg.pages
        ]
        updated = SiteConfig(
            title=cfg.title,
            description=cfg.description,
            default_author=cfg.default_author,
            timezone=cfg.timezone,
            pages=pages,
        )
        write_site_config(cm.content_dir, updated)
        cm.reload_config()

    if content is not None and page.file:
        (cm.content_dir / page.file).write_text(content, encoding="utf-8")


def delete_page(cm: ContentManager, page_id: str, *, delete_file: bool) -> None:
    """Remove a page from config and optionally delete the .md file."""
    if page_id in BUILTIN_PAGE_IDS:
        msg = f"Cannot delete built-in page '{page_id}'"
        raise ValueError(msg)

    cfg = cm.site_config
    page = next((p for p in cfg.pages if p.id == page_id), None)
    if page is None:
        msg = f"Page '{page_id}' not found"
        raise ValueError(msg)

    if delete_file and page.file:
        file_path = cm.content_dir / page.file
        if file_path.exists():
            file_path.unlink()

    updated = SiteConfig(
        title=cfg.title,
        description=cfg.description,
        default_author=cfg.default_author,
        timezone=cfg.timezone,
        pages=[p for p in cfg.pages if p.id != page_id],
    )
    write_site_config(cm.content_dir, updated)
    cm.reload_config()


def update_page_order(cm: ContentManager, pages: list[PageConfig]) -> None:
    """Replace the page list with a new ordered list."""
    cfg = cm.site_config
    updated = SiteConfig(
        title=cfg.title,
        description=cfg.description,
        default_author=cfg.default_author,
        timezone=cfg.timezone,
        pages=pages,
    )
    write_site_config(cm.content_dir, updated)
    cm.reload_config()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_admin_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/admin_service.py tests/test_services/test_admin_service.py
git commit -m "feat: add admin service with site settings and page management"
```

---

### Task 4: Add Backend Admin API Router

**Files:**
- Create: `backend/api/admin.py`
- Modify: `backend/main.py:18-25` (add import), `backend/main.py:190-197` (register router)
- Test: `tests/test_api/test_api_integration.py` (add TestAdmin class)

**Step 1: Write the failing tests**

Add to `tests/test_api/test_api_integration.py`:

```python
class TestAdmin:
    @pytest.mark.asyncio
    async def test_get_site_settings_requires_admin(self, client: AsyncClient) -> None:
        resp = await client.get("/api/admin/site")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_site_settings(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/admin/site",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Blog"
        assert "timezone" in data

    @pytest.mark.asyncio
    async def test_update_site_settings(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/admin/site",
            json={
                "title": "Updated Blog",
                "description": "New desc",
                "default_author": "Admin",
                "timezone": "US/Eastern",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Blog"

        # Verify site config API reflects change
        config_resp = await client.get("/api/pages")
        assert config_resp.json()["title"] == "Updated Blog"

    @pytest.mark.asyncio
    async def test_get_admin_pages(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/admin/pages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "pages" in data
        assert len(data["pages"]) >= 1

    @pytest.mark.asyncio
    async def test_create_page(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/admin/pages",
            json={"id": "contact", "title": "Contact"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "contact"

    @pytest.mark.asyncio
    async def test_create_duplicate_page_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/admin/pages",
            json={"id": "dup-page", "title": "Dup"},
            headers=headers,
        )
        resp = await client.post(
            "/api/admin/pages",
            json={"id": "dup-page", "title": "Dup"},
            headers=headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_page(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a page first
        await client.post(
            "/api/admin/pages",
            json={"id": "editable", "title": "Editable"},
            headers=headers,
        )

        resp = await client.put(
            "/api/admin/pages/editable",
            json={"title": "Updated Title", "content": "# Updated\n\nNew content."},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_page(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/admin/pages",
            json={"id": "deleteme", "title": "Delete Me"},
            headers=headers,
        )
        resp = await client.delete(
            "/api/admin/pages/deleteme",
            headers=headers,
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_builtin_page_returns_400(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.delete(
            "/api/admin/pages/timeline",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_page_order(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/admin/pages/order",
            json={
                "pages": [
                    {"id": "timeline", "title": "Home"},
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/admin/password",
            json={
                "current_password": "admin123",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        # Verify new password works
        login2 = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "newpassword123"},
        )
        assert login2.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/admin/password",
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_mismatch(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/admin/password",
            json={
                "current_password": "admin123",
                "new_password": "newpassword123",
                "confirm_password": "differentpassword",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api/test_api_integration.py::TestAdmin -v`
Expected: FAIL (404s — no router registered yet)

**Step 3: Write the admin API router**

Create `backend/api/admin.py`:

```python
"""Admin panel API endpoints."""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    get_content_manager,
    get_git_service,
    get_session,
    require_admin,
)
from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import PageConfig
from backend.models.user import User
from backend.schemas.admin import (
    AdminPageConfig,
    AdminPagesResponse,
    PageCreate,
    PageOrderUpdate,
    PageUpdate,
    PasswordChange,
    SiteSettingsResponse,
    SiteSettingsUpdate,
)
from backend.services.admin_service import (
    create_page,
    delete_page,
    get_admin_pages,
    get_site_settings,
    update_page,
    update_page_order,
    update_site_settings,
)
from backend.services.auth_service import hash_password, verify_password
from backend.services.git_service import GitService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_PAGE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


@router.get("/site", response_model=SiteSettingsResponse)
async def get_settings(
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    _user: Annotated[User, Depends(require_admin)],
) -> SiteSettingsResponse:
    """Get current site settings."""
    cfg = get_site_settings(content_manager)
    return SiteSettingsResponse(
        title=cfg.title,
        description=cfg.description,
        default_author=cfg.default_author,
        timezone=cfg.timezone,
    )


@router.put("/site", response_model=SiteSettingsResponse)
async def update_settings(
    body: SiteSettingsUpdate,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> SiteSettingsResponse:
    """Update site settings."""
    cfg = update_site_settings(
        content_manager,
        title=body.title,
        description=body.description,
        default_author=body.default_author,
        timezone=body.timezone,
    )
    git_service.try_commit("Update site settings")
    return SiteSettingsResponse(
        title=cfg.title,
        description=cfg.description,
        default_author=cfg.default_author,
        timezone=cfg.timezone,
    )


@router.get("/pages", response_model=AdminPagesResponse)
async def list_pages(
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    _user: Annotated[User, Depends(require_admin)],
) -> AdminPagesResponse:
    """Get all pages with content for admin panel."""
    pages = get_admin_pages(content_manager)
    return AdminPagesResponse(pages=[AdminPageConfig(**p) for p in pages])


@router.post("/pages", response_model=AdminPageConfig, status_code=201)
async def create_page_endpoint(
    body: PageCreate,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AdminPageConfig:
    """Create a new page."""
    try:
        page = create_page(content_manager, page_id=body.id, title=body.title)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    git_service.try_commit(f"Create page: {body.id}")
    return AdminPageConfig(
        id=page.id,
        title=page.title,
        file=page.file,
        is_builtin=False,
        content=f"# {body.title}\n",
    )


@router.put("/pages/order", response_model=AdminPagesResponse)
async def update_order(
    body: PageOrderUpdate,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AdminPagesResponse:
    """Update page order."""
    pages = [PageConfig(id=p.id, title=p.title, file=p.file) for p in body.pages]
    update_page_order(content_manager, pages)
    git_service.try_commit("Update page order")
    admin_pages = get_admin_pages(content_manager)
    return AdminPagesResponse(pages=[AdminPageConfig(**p) for p in admin_pages])


@router.put("/pages/{page_id}")
async def update_page_endpoint(
    page_id: str,
    body: PageUpdate,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> dict[str, str]:
    """Update a page's title and/or content."""
    if not _PAGE_ID_PATTERN.match(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")
    try:
        update_page(content_manager, page_id, title=body.title, content=body.content)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    git_service.try_commit(f"Update page: {page_id}")
    return {"status": "ok"}


@router.delete("/pages/{page_id}", status_code=204)
async def delete_page_endpoint(
    page_id: str,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    git_service: Annotated[GitService, Depends(get_git_service)],
    _user: Annotated[User, Depends(require_admin)],
    delete_file: bool = Query(default=True),
) -> None:
    """Delete a page."""
    if not _PAGE_ID_PATTERN.match(page_id):
        raise HTTPException(status_code=400, detail="Invalid page ID")
    try:
        delete_page(content_manager, page_id, delete_file=delete_file)
    except ValueError as exc:
        if "built-in" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    git_service.try_commit(f"Delete page: {page_id}")


@router.put("/password")
async def change_password(
    body: PasswordChange,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_admin)],
) -> dict[str, str]:
    """Change admin password."""
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    session.add(user)
    await session.commit()
    return {"status": "ok"}
```

**Step 4: Register the router in `backend/main.py`**

Add import at line 18:
```python
from backend.api.admin import router as admin_router
```

Add to router registration after `app.include_router(crosspost_router)`:
```python
app.include_router(admin_router)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api/test_api_integration.py::TestAdmin -v`
Expected: PASS

**Step 6: Run full backend checks**

Run: `just check-backend`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/api/admin.py backend/main.py tests/test_api/test_api_integration.py
git commit -m "feat: add admin API router with site settings, pages, and password endpoints"
```

---

### Task 5: Add Frontend Admin API Client

**Files:**
- Create: `frontend/src/api/admin.ts`
- Modify: `frontend/src/api/client.ts` (add admin types)

**Step 1: Add types to `frontend/src/api/client.ts`**

Add after `PostEditResponse` interface (around line 208):

```typescript
export interface AdminSiteSettings {
  title: string
  description: string
  default_author: string
  timezone: string
}

export interface AdminPageConfig {
  id: string
  title: string
  file: string | null
  is_builtin: boolean
  content: string | null
}

export interface AdminPagesResponse {
  pages: AdminPageConfig[]
}
```

**Step 2: Create `frontend/src/api/admin.ts`**

```typescript
import api from './client'
import type { AdminSiteSettings, AdminPageConfig, AdminPagesResponse } from './client'

export async function fetchAdminSiteSettings(): Promise<AdminSiteSettings> {
  return api.get('admin/site').json<AdminSiteSettings>()
}

export async function updateAdminSiteSettings(
  settings: AdminSiteSettings,
): Promise<AdminSiteSettings> {
  return api.put('admin/site', { json: settings }).json<AdminSiteSettings>()
}

export async function fetchAdminPages(): Promise<AdminPagesResponse> {
  return api.get('admin/pages').json<AdminPagesResponse>()
}

export async function createAdminPage(data: {
  id: string
  title: string
}): Promise<AdminPageConfig> {
  return api.post('admin/pages', { json: data }).json<AdminPageConfig>()
}

export async function updateAdminPage(
  pageId: string,
  data: { title?: string; content?: string },
): Promise<void> {
  await api.put(`admin/pages/${pageId}`, { json: data })
}

export async function updateAdminPageOrder(
  pages: { id: string; title: string; file: string | null }[],
): Promise<AdminPagesResponse> {
  return api.put('admin/pages/order', { json: { pages } }).json<AdminPagesResponse>()
}

export async function deleteAdminPage(pageId: string, deleteFile = true): Promise<void> {
  await api.delete(`admin/pages/${pageId}`, {
    searchParams: { delete_file: String(deleteFile) },
  })
}

export async function changeAdminPassword(data: {
  current_password: string
  new_password: string
  confirm_password: string
}): Promise<void> {
  await api.put('admin/password', { json: data })
}
```

**Step 3: Commit**

```bash
git add frontend/src/api/admin.ts frontend/src/api/client.ts
git commit -m "feat: add frontend admin API client and types"
```

---

### Task 6: Create AdminPage Component

**Files:**
- Create: `frontend/src/pages/AdminPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

**Step 1: Create the AdminPage component**

Use the **frontend-design** skill to design and build `AdminPage.tsx`. The page should:

- Check `user?.is_admin` and redirect to `/` if not admin
- Have three sections: Site Settings, Pages Management, Change Password
- Follow existing patterns from `LabelSettingsPage.tsx` and `EditorPage.tsx`
- Use `disabled={busy}` pattern on all controls during async operations
- Use error banner pattern from existing pages
- Section styling: `p-5 bg-paper border border-border rounded-lg` (from LabelSettingsPage)
- Use lucide-react icons: `Settings`, `FileText`, `Lock`, `ArrowUp`, `ArrowDown`, `Plus`, `Trash2`, `Pencil`, `ChevronDown`, `ChevronRight`

**Site Settings section:**
- Text inputs for title, description, default_author, timezone
- Save button

**Pages section:**
- List of pages with up/down arrows for reordering
- Built-in pages (timeline, labels) marked with a badge
- Add new page: form with id + title inputs
- Each page expandable to show inline markdown editor with preview (like EditorPage)
- Delete button for non-builtin pages (with confirmation)
- Save Order button to persist reordering

**Password section:**
- Current password, new password, confirm password inputs
- Save button
- Success/error messages

**Step 2: Add route to `App.tsx`**

Add import and route:
```typescript
import AdminPage from '@/pages/AdminPage'
// In Routes:
<Route path="/admin" element={<AdminPage />} />
```

**Step 3: Commit**

```bash
git add frontend/src/pages/AdminPage.tsx frontend/src/App.tsx
git commit -m "feat: add AdminPage with site settings, pages management, and password change"
```

---

### Task 7: Add Admin Gear Icon to Header

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

**Step 1: Add gear icon for admin users**

In Header.tsx, add `Settings` to the lucide-react import and add a gear icon link between the Write button and Logout button, visible only when `user.is_admin`:

```typescript
import { Settings } from 'lucide-react'

// Between Write link and Logout button (after line 81, before line 82):
{user.is_admin && (
  <Link
    to="/admin"
    className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
    aria-label="Admin"
    title="Admin panel"
  >
    <Settings size={18} />
  </Link>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "feat: add admin gear icon to header for admin users"
```

---

### Task 8: Update Site Store to Refresh After Admin Changes

**Files:**
- Modify: `frontend/src/stores/siteStore.ts` (no changes needed — it already has `fetchConfig`)

The AdminPage should call `useSiteStore.getState().fetchConfig()` after successfully saving site settings or page order changes, so the header navigation updates immediately. This is handled within the AdminPage component (Task 6) — no store changes needed.

**This task is informational only — verify this is done in Task 6.**

---

### Task 9: Update ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update the documentation**

Add to the API Routes table:
```markdown
| `admin` | `/api/admin` | Site settings, page management, password change (admin-only) |
```

Add to the Frontend Routing table:
```markdown
| `/admin` | AdminPage | Admin panel: site settings, pages, password (admin required) |
```

**Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add admin panel to architecture documentation"
```

---

### Task 10: End-to-End Browser Testing

**Step 1: Start dev server**

Run: `just start`

**Step 2: Test in browser using Playwright MCP**

- Navigate to `http://localhost:5173/login`
- Log in as admin
- Verify gear icon appears in header
- Click gear icon, verify `/admin` page loads
- Test site settings: change title, save, verify header updates
- Test pages: reorder, add a new page, edit content, delete
- Test password change: change password, verify can log in with new password
- Verify non-admin user cannot access /admin

**Step 3: Clean up**

Run: `just stop`
Remove any leftover `*.png` screenshot files.

---

### Task 11: Final Verification

**Step 1: Run all checks**

Run: `just check`
Expected: All type checking, linting, format checks, and tests pass.

**Step 2: Fix any issues found**

**Step 3: Final commit if any fixes were needed**
