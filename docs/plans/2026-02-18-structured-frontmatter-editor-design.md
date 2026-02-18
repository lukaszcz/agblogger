# Structured Front Matter Editor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the raw YAML front matter editor with structured UI controls (label picker, draft toggle, read-only metadata) so the frontend never touches YAML.

**Architecture:** New backend endpoints return/accept structured post data (body + metadata separately). The backend assembles `PostData` and serializes YAML. The frontend editor splits into a metadata bar and a body-only textarea.

**Tech Stack:** FastAPI (backend), React + TypeScript + Tailwind (frontend), Pydantic schemas, SQLAlchemy, python-frontmatter (serialization stays backend-only).

---

### Task 1: Backend — New schemas for structured post editing

**Files:**
- Modify: `backend/schemas/post.py`

**Step 1: Add new Pydantic models**

Add these schemas to `backend/schemas/post.py`:

```python
class PostEditResponse(BaseModel):
    """Structured post data for the editor."""

    file_path: str
    body: str
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False
    created_at: str
    modified_at: str
    author: str | None = None


class PostCreateStructured(BaseModel):
    """Request to create a new post with structured metadata."""

    file_path: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^posts/.*\.md$",
        description="Relative path under content/, e.g. posts/my-post.md",
    )
    body: str = Field(
        max_length=500_000,
        description="Markdown body without front matter",
    )
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False


class PostUpdateStructured(BaseModel):
    """Request to update a post with structured metadata."""

    body: str = Field(
        max_length=500_000,
        description="Markdown body without front matter",
    )
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False
```

**Step 2: Verify types**

Run: `uv run mypy backend/schemas/post.py`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/schemas/post.py
git commit -m "feat: add structured post edit schemas"
```

---

### Task 2: Backend — GET /api/posts/{path}/edit endpoint

**Files:**
- Modify: `backend/api/posts.py`

**Step 1: Write the test**

Add to `tests/test_api/test_api_integration.py` in class `TestPostCRUD`:

```python
@pytest.mark.asyncio
async def test_get_post_for_edit(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/posts/posts/hello.md/edit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_path"] == "posts/hello.md"
    assert "# Hello World" in data["body"]
    assert data["labels"] == ["swe"]
    assert "created_at" in data
    assert "modified_at" in data
    assert data["author"] == "Admin"

@pytest.mark.asyncio
async def test_get_post_for_edit_requires_auth(self, client: AsyncClient) -> None:
    resp = await client.get("/api/posts/posts/hello.md/edit")
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_get_post_for_edit_not_found(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/posts/posts/nonexistent.md/edit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestPostCRUD::test_get_post_for_edit -v`
Expected: FAIL (404 — endpoint doesn't exist yet)

**Step 3: Implement the endpoint**

Add to `backend/api/posts.py`, **before** the `get_post_endpoint` route (important — FastAPI matches routes top-to-bottom, and `{file_path:path}` would swallow `/edit`):

```python
from backend.schemas.post import PostEditResponse

@router.get("/{file_path:path}/edit", response_model=PostEditResponse)
async def get_post_for_edit(
    file_path: str,
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> PostEditResponse:
    """Get structured post data for the editor."""
    post_data = content_manager.read_post(file_path)
    if post_data is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostEditResponse(
        file_path=file_path,
        body=post_data.content,
        labels=post_data.labels,
        is_draft=post_data.is_draft,
        created_at=format_datetime(post_data.created_at),
        modified_at=format_datetime(post_data.modified_at),
        author=post_data.author,
    )
```

Also add `PostEditResponse` to the imports from `backend.schemas.post`.

**Important:** The `/edit` route MUST be registered before the catch-all `/{file_path:path}` route. Move it above `get_post_endpoint`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestPostCRUD -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/posts.py tests/test_api/test_api_integration.py
git commit -m "feat: add GET /api/posts/{path}/edit endpoint"
```

---

### Task 3: Backend — Modify POST /api/posts to accept structured input

**Files:**
- Modify: `backend/api/posts.py`
- Modify: `backend/schemas/post.py`

**Step 1: Write the test**

Add to `tests/test_api/test_api_integration.py` in class `TestPostCRUD`:

```python
@pytest.mark.asyncio
async def test_create_post_structured(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/posts",
        json={
            "file_path": "posts/structured-new.md",
            "body": "# Structured Post\n\nContent here.",
            "labels": ["swe"],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Structured Post"
    assert data["labels"] == ["swe"]
    assert data["is_draft"] is False
    assert data["author"] == "admin"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestPostCRUD::test_create_post_structured -v`
Expected: FAIL (validation error — current schema expects `content`, not `body`)

**Step 3: Implement**

Replace `PostCreate` schema in `backend/schemas/post.py` with the `PostCreateStructured` schema from Task 1 (rename it to `PostCreate` to avoid changing every import):

```python
class PostCreate(BaseModel):
    """Request to create a new post."""

    file_path: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^posts/.*\.md$",
        description="Relative path under content/, e.g. posts/my-post.md",
    )
    body: str = Field(
        max_length=500_000,
        description="Markdown body without front matter",
    )
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False
```

Update `create_post_endpoint` in `backend/api/posts.py`:

```python
@router.post("", response_model=PostDetail, status_code=201)
async def create_post_endpoint(
    body: PostCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Create a new post."""
    now = now_utc()
    author = user.display_name or user.username

    post_data = PostData(
        title=extract_title(body.body, body.file_path),
        content=body.body,
        raw_content="",  # Will be set by serialize
        created_at=now,
        modified_at=now,
        author=author,
        labels=body.labels,
        is_draft=body.is_draft,
        file_path=body.file_path,
    )

    excerpt = generate_excerpt(post_data.content)
    rendered_html = render_markdown(post_data.content)

    from backend.filesystem.frontmatter import serialize_post

    serialized = serialize_post(post_data)
    post = PostCache(
        file_path=body.file_path,
        title=post_data.title,
        author=post_data.author,
        created_at=format_datetime(post_data.created_at),
        modified_at=format_datetime(post_data.modified_at),
        is_draft=post_data.is_draft,
        content_hash=hash_content(serialized),
        excerpt=excerpt,
        rendered_html=rendered_html,
    )
    session.add(post)
    await session.flush()

    try:
        content_manager.write_post(body.file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", body.file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(post)

    return PostDetail(
        id=post.id,
        file_path=post.file_path,
        title=post.title,
        author=post.author,
        created_at=post.created_at,
        modified_at=post.modified_at,
        is_draft=post.is_draft,
        excerpt=post.excerpt,
        labels=post_data.labels,
        rendered_html=rendered_html,
    )
```

Add these imports to the top of `backend/api/posts.py`:

```python
from backend.filesystem.frontmatter import PostData, extract_title, generate_excerpt
```

Remove the now-unused `parse_post` import.

**Step 4: Update existing create test**

The existing `test_create_post_authenticated` sends `content` (raw YAML). Update it to send structured data:

```python
@pytest.mark.asyncio
async def test_create_post_authenticated(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/posts",
        json={
            "file_path": "posts/new-test.md",
            "body": "# New Post\n\nContent here.\n",
            "labels": [],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "New Post"
```

Also update `test_create_post_requires_auth`:

```python
@pytest.mark.asyncio
async def test_create_post_requires_auth(self, client: AsyncClient) -> None:
    resp = await client.post(
        "/api/posts",
        json={
            "file_path": "posts/no-auth.md",
            "body": "# No Auth\n",
            "labels": [],
            "is_draft": False,
        },
    )
    assert resp.status_code == 401
```

And `test_delete_post_authenticated` (creates a post before deleting):

```python
@pytest.mark.asyncio
async def test_delete_post_authenticated(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    # Create a post to delete
    await client.post(
        "/api/posts",
        json={
            "file_path": "posts/to-delete.md",
            "body": "# Delete Me\n",
            "labels": [],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.delete(
        "/api/posts/posts/to-delete.md",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
```

**Step 5: Run all tests**

Run: `uv run pytest tests/test_api/test_api_integration.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/api/posts.py backend/schemas/post.py tests/test_api/test_api_integration.py
git commit -m "feat: POST /api/posts accepts structured body+labels+is_draft"
```

---

### Task 4: Backend — Modify PUT /api/posts/{path} to accept structured input

**Files:**
- Modify: `backend/api/posts.py`
- Modify: `backend/schemas/post.py`

**Step 1: Write the test**

Add to `tests/test_api/test_api_integration.py` in class `TestPostCRUD`:

```python
@pytest.mark.asyncio
async def test_update_post_structured(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.put(
        "/api/posts/posts/hello.md",
        json={
            "body": "# Hello World Updated\n\nUpdated content.\n",
            "labels": ["swe"],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Hello World Updated"
    assert data["labels"] == ["swe"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestPostCRUD::test_update_post_structured -v`
Expected: FAIL (validation error — current schema expects `content`)

**Step 3: Implement**

Replace `PostUpdate` schema in `backend/schemas/post.py`:

```python
class PostUpdate(BaseModel):
    """Request to update an existing post."""

    body: str = Field(
        max_length=500_000,
        description="Markdown body without front matter",
    )
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False
```

Update `update_post_endpoint` in `backend/api/posts.py`:

```python
@router.put("/{file_path:path}", response_model=PostDetail)
async def update_post_endpoint(
    file_path: str,
    body: PostUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> PostDetail:
    """Update an existing post."""
    from sqlalchemy import select

    stmt = select(PostCache).where(PostCache.file_path == file_path)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # Read existing post to preserve created_at and author
    existing_post_data = content_manager.read_post(file_path)
    created_at = existing_post_data.created_at if existing_post_data else now_utc()
    author = existing_post_data.author if existing_post_data else (user.display_name or user.username)

    now = now_utc()
    title = extract_title(body.body, file_path)

    post_data = PostData(
        title=title,
        content=body.body,
        raw_content="",
        created_at=created_at,
        modified_at=now,
        author=author,
        labels=body.labels,
        is_draft=body.is_draft,
        file_path=file_path,
    )

    from backend.filesystem.frontmatter import serialize_post

    serialized = serialize_post(post_data)
    excerpt = generate_excerpt(post_data.content)
    rendered_html = render_markdown(post_data.content)

    existing.title = title
    existing.author = author
    existing.modified_at = format_datetime(now)
    existing.is_draft = body.is_draft
    existing.content_hash = hash_content(serialized)
    existing.excerpt = excerpt
    existing.rendered_html = rendered_html

    await session.flush()

    try:
        content_manager.write_post(file_path, post_data)
    except Exception as exc:
        logger.error("Failed to write post %s: %s", file_path, exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to write post file") from exc

    await session.commit()
    await session.refresh(existing)

    return PostDetail(
        id=existing.id,
        file_path=existing.file_path,
        title=existing.title,
        author=existing.author,
        created_at=existing.created_at,
        modified_at=existing.modified_at,
        is_draft=existing.is_draft,
        excerpt=existing.excerpt,
        labels=post_data.labels,
        rendered_html=existing.rendered_html or "",
    )
```

**Step 4: Update existing update test**

Update `test_update_post_authenticated` to use the new schema:

```python
@pytest.mark.asyncio
async def test_update_post_authenticated(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.put(
        "/api/posts/posts/hello.md",
        json={
            "body": "# Hello World Updated\n\nUpdated content.\n",
            "labels": ["swe"],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Hello World Updated"
```

Also update `test_update_nonexistent_post_returns_404`:

```python
@pytest.mark.asyncio
async def test_update_nonexistent_post_returns_404(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.put(
        "/api/posts/posts/nope.md",
        json={
            "body": "# Nope\n",
            "labels": [],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
```

**Step 5: Run all tests**

Run: `uv run pytest tests/test_api/test_api_integration.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/api/posts.py backend/schemas/post.py tests/test_api/test_api_integration.py
git commit -m "feat: PUT /api/posts/{path} accepts structured body+labels+is_draft"
```

---

### Task 5: Backend — POST /api/labels endpoint for creating labels

**Files:**
- Modify: `backend/api/labels.py`
- Modify: `backend/services/label_service.py`

**Step 1: Write the test**

Add a new class to `tests/test_api/test_api_integration.py`:

```python
class TestLabelCRUD:
    @pytest.mark.asyncio
    async def test_create_label(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/labels",
            json={"id": "cooking"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "cooking"
        assert data["names"] == ["cooking"]

    @pytest.mark.asyncio
    async def test_create_label_duplicate_returns_409(self, client: AsyncClient) -> None:
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        # swe already exists from fixture
        resp = await client.post(
            "/api/labels",
            json={"id": "swe"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_label_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/labels",
            json={"id": "nope"},
        )
        assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestLabelCRUD -v`
Expected: FAIL (405 Method Not Allowed — no POST handler)

**Step 3: Add create_label service function**

Add to `backend/services/label_service.py`:

```python
async def create_label(session: AsyncSession, label_id: str) -> LabelResponse | None:
    """Create a new label. Returns None if it already exists."""
    existing = await session.get(LabelCache, label_id)
    if existing is not None:
        return None

    label = LabelCache(
        id=label_id,
        names=json.dumps([label_id]),
        is_implicit=False,
    )
    session.add(label)
    await session.commit()

    return LabelResponse(
        id=label_id,
        names=[label_id],
        is_implicit=False,
        parents=[],
        children=[],
        post_count=0,
    )
```

**Step 4: Add the endpoint**

Add to `backend/api/labels.py`:

```python
from backend.api.deps import get_content_manager, require_auth
from backend.filesystem.content_manager import ContentManager
from backend.filesystem.toml_manager import LabelDef, write_labels_config
from backend.models.user import User
from backend.schemas.label import LabelCreate
from backend.services.label_service import create_label


@router.post("", response_model=LabelResponse, status_code=201)
async def create_label_endpoint(
    body: LabelCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    user: Annotated[User, Depends(require_auth)],
) -> LabelResponse:
    """Create a new label."""
    result = await create_label(session, body.id)
    if result is None:
        raise HTTPException(status_code=409, detail="Label already exists")

    # Also write to labels.toml so it persists across restarts
    labels = content_manager.labels
    if body.id not in labels:
        labels[body.id] = LabelDef(id=body.id, names=[body.id])
        write_labels_config(content_manager.content_dir, labels)
        content_manager.reload_config()

    return result
```

The `LabelCreate` schema already exists in `backend/schemas/label.py` with `id`, `names`, and `parents` fields. We only need `id` for the simple creation flow — the other fields have defaults.

**Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_api_integration.py::TestLabelCRUD -v`
Expected: PASS

**Step 6: Run all tests to check for regressions**

Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/api/labels.py backend/services/label_service.py tests/test_api/test_api_integration.py
git commit -m "feat: add POST /api/labels endpoint for creating labels"
```

---

### Task 6: Backend — Run full checks

**Step 1: Run type checking and linting**

Run: `just check-backend`
Expected: PASS (mypy, ruff check, ruff format, pytest)

Fix any issues found.

**Step 2: Commit any fixes**

```bash
git add -A
git commit -m "fix: type and lint errors from structured editor backend"
```

---

### Task 7: Frontend — API layer for structured editor

**Files:**
- Modify: `frontend/src/api/posts.ts`
- Modify: `frontend/src/api/labels.ts`
- Modify: `frontend/src/api/client.ts`

**Step 1: Add types to `frontend/src/api/client.ts`**

```typescript
export interface PostEditResponse {
  file_path: string
  body: string
  labels: string[]
  is_draft: boolean
  created_at: string
  modified_at: string
  author: string | null
}
```

**Step 2: Update `frontend/src/api/posts.ts`**

Replace `createPost` and `updatePost`, add `fetchPostForEdit`:

```typescript
import type { PostDetail, PostEditResponse, PostListResponse, SearchResult } from './client'

export async function fetchPostForEdit(filePath: string): Promise<PostEditResponse> {
  return api.get(`posts/${filePath}/edit`).json<PostEditResponse>()
}

export async function createPost(params: {
  file_path: string
  body: string
  labels: string[]
  is_draft: boolean
}): Promise<PostDetail> {
  return api.post('posts', { json: params }).json<PostDetail>()
}

export async function updatePost(
  filePath: string,
  params: { body: string; labels: string[]; is_draft: boolean },
): Promise<PostDetail> {
  return api.put(`posts/${filePath}`, { json: params }).json<PostDetail>()
}
```

**Step 3: Add `createLabel` to `frontend/src/api/labels.ts`**

```typescript
export async function createLabel(id: string): Promise<LabelResponse> {
  return api.post('labels', { json: { id } }).json<LabelResponse>()
}
```

**Step 4: Run type checking**

Run: `cd frontend && npx tsc --noEmit`
Expected: Errors in `EditorPage.tsx` (the old `createPost`/`updatePost` signatures no longer match). This is expected and will be fixed in the next task.

**Step 5: Commit**

```bash
git add frontend/src/api/posts.ts frontend/src/api/labels.ts frontend/src/api/client.ts
git commit -m "feat: add structured editor API functions"
```

---

### Task 8: Frontend — LabelInput component

**Files:**
- Create: `frontend/src/components/editor/LabelInput.tsx`

This is the tag-style input with typeahead dropdown.

**Step 1: Create the component**

Create `frontend/src/components/editor/LabelInput.tsx`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { fetchLabels } from '@/api/labels'
import { createLabel } from '@/api/labels'
import type { LabelResponse } from '@/api/client'

interface LabelInputProps {
  value: string[]
  onChange: (labels: string[]) => void
  disabled?: boolean
}

export default function LabelInput({ value, onChange, disabled }: LabelInputProps) {
  const [query, setQuery] = useState('')
  const [allLabels, setAllLabels] = useState<LabelResponse[]>([])
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchLabels().then(setAllLabels).catch(() => {})
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const filtered = allLabels.filter(
    (l) => !value.includes(l.id) && l.id.toLowerCase().includes(query.toLowerCase()),
  )

  const trimmed = query.trim().toLowerCase()
  const exactMatch = allLabels.some((l) => l.id === trimmed)
  const showCreate = trimmed.length > 0 && !exactMatch && !value.includes(trimmed)

  function addLabel(id: string) {
    if (!value.includes(id)) {
      onChange([...value, id])
    }
    setQuery('')
    setOpen(false)
    inputRef.current?.focus()
  }

  function removeLabel(id: string) {
    onChange(value.filter((l) => l !== id))
  }

  async function handleCreate() {
    if (!trimmed || creating) return
    setCreating(true)
    try {
      const label = await createLabel(trimmed)
      setAllLabels((prev) => [...prev, label])
      addLabel(label.id)
    } catch {
      // 409 = already exists, just add it
      addLabel(trimmed)
    } finally {
      setCreating(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && query === '' && value.length > 0) {
      removeLabel(value[value.length - 1])
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (showCreate) {
        void handleCreate()
      } else if (filtered.length > 0) {
        addLabel(filtered[0].id)
      }
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <div
        className="flex flex-wrap items-center gap-1.5 px-3 py-2 bg-paper-warm border border-border
                    rounded-lg focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/20
                    min-h-[2.5rem]"
      >
        {value.map((id) => (
          <span
            key={id}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium
                       bg-accent/10 text-accent rounded-full"
          >
            #{id}
            {!disabled && (
              <button
                type="button"
                onClick={() => removeLabel(id)}
                className="hover:text-accent-light"
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={value.length === 0 ? 'Add labels...' : ''}
          className="flex-1 min-w-[80px] bg-transparent text-sm text-ink outline-none
                     placeholder:text-muted disabled:opacity-50"
        />
      </div>

      {open && (filtered.length > 0 || showCreate) && (
        <div
          className="absolute z-10 mt-1 w-full bg-paper border border-border rounded-lg
                      shadow-lg max-h-48 overflow-y-auto"
        >
          {filtered.map((label) => (
            <button
              key={label.id}
              type="button"
              onClick={() => addLabel(label.id)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-paper-warm transition-colors"
            >
              <span className="font-medium">#{label.id}</span>
              {label.names.length > 0 && label.names[0] !== label.id && (
                <span className="ml-2 text-muted">{label.names[0]}</span>
              )}
            </button>
          ))}
          {showCreate && (
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={creating}
              className="w-full text-left px-3 py-2 text-sm text-accent hover:bg-paper-warm
                         transition-colors border-t border-border disabled:opacity-50"
            >
              {creating ? 'Creating...' : `Create #${trimmed}`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Run type checking**

Run: `cd frontend && npx tsc --noEmit`
Expected: Errors only in `EditorPage.tsx` (will be fixed in next task).

**Step 3: Commit**

```bash
git add frontend/src/components/editor/LabelInput.tsx
git commit -m "feat: add LabelInput component with typeahead and create"
```

---

### Task 9: Frontend — Redesign EditorPage

**Files:**
- Modify: `frontend/src/pages/EditorPage.tsx`

**Step 1: Rewrite EditorPage**

Replace the entire `frontend/src/pages/EditorPage.tsx` with the redesigned version. Key changes:

- State: `body` (string), `labels` (string[]), `isDraft` (boolean), `author` (string), `createdAt`/`modifiedAt` (string | null)
- Load: new posts initialize with empty state + author from auth store; existing posts use `fetchPostForEdit`
- Save: calls structured `createPost`/`updatePost`
- Preview: sends `body` directly (no front matter stripping needed)
- Metadata bar with LabelInput, draft toggle, read-only author/dates

```typescript
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, Eye, ArrowLeft } from 'lucide-react'
import { fetchPostForEdit, createPost, updatePost } from '@/api/posts'
import { HTTPError } from '@/api/client'
import api from '@/api/client'
import { useRenderedHtml } from '@/hooks/useKatex'
import { useAuthStore } from '@/stores/authStore'
import LabelInput from '@/components/editor/LabelInput'

export default function EditorPage() {
  const { '*': filePath } = useParams()
  const navigate = useNavigate()
  const isNew = !filePath || filePath === 'new'
  const user = useAuthStore((s) => s.user)

  const [body, setBody] = useState('')
  const [labels, setLabels] = useState<string[]>([])
  const [isDraft, setIsDraft] = useState(false)
  const [newPath, setNewPath] = useState('posts/')
  const [author, setAuthor] = useState<string | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [modifiedAt, setModifiedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const renderedPreview = useRenderedHtml(preview)

  useEffect(() => {
    if (!isNew && filePath) {
      setLoading(true)
      fetchPostForEdit(filePath)
        .then((data) => {
          setBody(data.body)
          setLabels(data.labels)
          setIsDraft(data.is_draft)
          setNewPath(data.file_path)
          setAuthor(data.author)
          setCreatedAt(data.created_at)
          setModifiedAt(data.modified_at)
        })
        .catch((err) => {
          if (err instanceof HTTPError && err.response.status === 404) {
            setError('Post not found')
          } else {
            setError('Failed to load post')
          }
        })
        .finally(() => setLoading(false))
    } else {
      setBody('# New Post\n\nStart writing here...\n')
      setAuthor(user?.display_name || user?.username || null)
    }
  }, [filePath, isNew, user])

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const path = isNew ? newPath : filePath!
      if (isNew) {
        await createPost({ file_path: path, body, labels, is_draft: isDraft })
      } else {
        await updatePost(path, { body, labels, is_draft: isDraft })
      }
      void navigate(`/post/${path}`)
    } catch (err) {
      if (err instanceof HTTPError) {
        if (err.response.status === 401) {
          setError('Session expired. Please log in again.')
        } else if (err.response.status === 409) {
          setError('Conflict: this post was modified elsewhere.')
        } else {
          setError('Failed to save post')
        }
      } else {
        setError('Failed to save post')
      }
    } finally {
      setSaving(false)
    }
  }

  async function handlePreview() {
    setPreviewing(true)
    try {
      const resp = await api
        .post('render/preview', { json: { markdown: body } })
        .json<{ html: string }>()
      setPreview(resp.html)
    } catch {
      setError('Preview failed')
    } finally {
      setPreviewing(false)
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString()
  }

  if (loading) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-muted text-sm">Loading...</span>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => void navigate(-1)}
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void handlePreview()}
            disabled={previewing || saving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                     border border-border rounded-lg hover:bg-paper-warm disabled:opacity-50 transition-colors"
          >
            <Eye size={14} />
            {previewing ? 'Loading...' : 'Preview'}
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={saving || previewing}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium
                     bg-accent text-white rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* Metadata bar */}
      <div className="mb-4 space-y-3 p-4 bg-paper border border-border rounded-lg">
        {isNew && (
          <div>
            <label htmlFor="filepath" className="block text-xs font-medium text-muted mb-1">
              File path
            </label>
            <input
              id="filepath"
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              disabled={saving}
              placeholder="posts/my-new-post.md"
              className="w-full px-3 py-2 bg-paper-warm border border-border rounded-lg
                       text-ink font-mono text-sm
                       focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                       disabled:opacity-50"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Labels</label>
          <LabelInput value={labels} onChange={setLabels} disabled={saving} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Draft toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isDraft}
                onChange={(e) => setIsDraft(e.target.checked)}
                disabled={saving}
                className="rounded border-border text-accent focus:ring-accent/20"
              />
              <span className="text-sm text-ink">Draft</span>
            </label>

            {/* Author (read-only) */}
            {author && (
              <span className="text-sm text-muted">
                Author: <span className="text-ink">{author}</span>
              </span>
            )}
          </div>

          {/* Dates (read-only, only for existing posts) */}
          {!isNew && (createdAt || modifiedAt) && (
            <div className="flex items-center gap-4 text-xs text-muted">
              {createdAt && <span>Created {formatDate(createdAt)}</span>}
              {modifiedAt && <span>Modified {formatDate(modifiedAt)}</span>}
            </div>
          )}
        </div>
      </div>

      {/* Editor + preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: '60vh' }}>
        <div>
          <textarea
            value={body}
            onChange={(e) => {
              setBody(e.target.value)
              setPreview(null)
            }}
            disabled={saving}
            className="w-full h-full min-h-[60vh] p-4 bg-paper-warm border border-border rounded-lg
                     font-mono text-sm leading-relaxed text-ink resize-none
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                     disabled:opacity-50"
            spellCheck={false}
          />
        </div>

        {preview && (
          <div className="p-6 bg-white border border-border rounded-lg overflow-y-auto">
            <div
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: renderedPreview }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Run type checking**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Run frontend tests**

Run: `cd frontend && npm test`
Expected: PASS (or address any failures)

**Step 4: Commit**

```bash
git add frontend/src/pages/EditorPage.tsx
git commit -m "feat: redesign editor with structured metadata bar"
```

---

### Task 10: Full verification

**Step 1: Run full checks**

Run: `just check`
Expected: PASS — all type checking, linting, format checks, and tests green.

Fix any issues found.

**Step 2: Manual browser test**

Use Playwright MCP to test both flows:
1. Log in
2. Create a new post via the editor — verify labels, draft toggle, author auto-fill work
3. Edit that post — verify existing metadata loads correctly
4. Verify the saved post appears correctly on the timeline

**Step 3: Update ARCHITECTURE.md**

Add documentation about the new structured editor API endpoints:
- `GET /api/posts/{path}/edit` — structured post data for editor
- `POST /api/labels` — create label by ID
- Modified `POST /api/posts` and `PUT /api/posts/{path}` schemas

**Step 4: Final commit**

```bash
git add -A
git commit -m "docs: update architecture for structured editor API"
```
