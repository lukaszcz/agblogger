# Post Title as Front Matter Field — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the post title from being embedded as a `# Heading` in the markdown body to a dedicated `title` field in YAML front matter, with a compulsory Title input in the editor UI.

**Architecture:** The `title` field is added to YAML front matter as the authoritative source. `parse_post()` reads it from metadata (falling back to heading extraction for legacy files). `serialize_post()` writes it to front matter and strips any leading `# Heading` from the body. The editor gets a separate Title text input that auto-generates a file path slug for new posts. Sync normalization backfills `title` from the first heading when absent.

**Tech Stack:** Python (FastAPI, Pydantic, python-frontmatter), TypeScript (React, react-router-dom), Vitest, pytest

---

### Task 1: Add `title` to RECOGNIZED_FIELDS and update `parse_post()`

**Files:**
- Modify: `backend/filesystem/frontmatter.py:14-22` (RECOGNIZED_FIELDS)
- Modify: `backend/filesystem/frontmatter.py:75-119` (parse_post)
- Test: `tests/test_rendering/test_frontmatter.py`
- Test: `tests/test_services/test_content_manager.py`

**Step 1: Write failing tests**

In `tests/test_rendering/test_frontmatter.py`, add to `TestRecognizedFields`:

```python
def test_title_in_recognized_fields(self) -> None:
    assert "title" in RECOGNIZED_FIELDS
```

In `tests/test_rendering/test_frontmatter.py`, add a new test class:

```python
class TestTitleFromFrontMatter:
    def test_title_from_frontmatter_field(self) -> None:
        content = """\
---
title: My Custom Title
created_at: 2026-02-02 22:21:29.975359+00
---

Blog post content without a heading
"""
        post = parse_post(content, file_path="posts/test.md")
        assert post.title == "My Custom Title"

    def test_title_fallback_to_heading_when_not_in_frontmatter(self) -> None:
        content = """\
---
created_at: 2026-02-02 22:21:29.975359+00
---
# Heading Title

Content
"""
        post = parse_post(content, file_path="posts/test.md")
        assert post.title == "Heading Title"

    def test_title_from_frontmatter_takes_precedence_over_heading(self) -> None:
        content = """\
---
title: Front Matter Title
created_at: 2026-02-02 22:21:29.975359+00
---
# Heading Title

Content
"""
        post = parse_post(content, file_path="posts/test.md")
        assert post.title == "Front Matter Title"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py -v -k "title"`
Expected: FAIL — `test_title_in_recognized_fields` and `test_title_from_frontmatter_field` fail

**Step 3: Implement changes**

In `backend/filesystem/frontmatter.py`:

1. Add `"title"` to `RECOGNIZED_FIELDS` (line 14-22):
```python
RECOGNIZED_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "created_at",
        "modified_at",
        "author",
        "labels",
        "draft",
    }
)
```

2. Update `parse_post()` (around line 104) to read title from front matter first:
```python
    # Title: prefer front matter, fall back to heading extraction
    fm_title = post.get("title")
    if fm_title and isinstance(fm_title, str) and fm_title.strip():
        title = fm_title.strip()
    else:
        title = extract_title(post.content, file_path)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py tests/test_services/test_content_manager.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add title to recognized front matter fields and parse_post
```

---

### Task 2: Update `serialize_post()` to write title and strip leading heading

**Files:**
- Modify: `backend/filesystem/frontmatter.py:122-136` (serialize_post)
- Add helper: `backend/filesystem/frontmatter.py` (strip_leading_heading function)
- Test: `tests/test_rendering/test_frontmatter.py`

**Step 1: Write failing tests**

In `tests/test_rendering/test_frontmatter.py`, add to `TestSerializePost`:

```python
def test_title_written_to_frontmatter(self) -> None:
    now = now_utc()
    post_data = PostData(
        title="My Title",
        content="Body content here.",
        raw_content="",
        created_at=now,
        modified_at=now,
    )
    result = serialize_post(post_data)
    parsed = frontmatter.loads(result)
    assert parsed["title"] == "My Title"

def test_leading_heading_stripped_from_body(self) -> None:
    now = now_utc()
    post_data = PostData(
        title="My Title",
        content="# My Title\n\nBody content here.",
        raw_content="",
        created_at=now,
        modified_at=now,
    )
    result = serialize_post(post_data)
    parsed = frontmatter.loads(result)
    assert not parsed.content.startswith("# ")
    assert "Body content here." in parsed.content

def test_heading_not_stripped_when_different_from_title(self) -> None:
    now = now_utc()
    post_data = PostData(
        title="My Title",
        content="# Different Heading\n\nBody content.",
        raw_content="",
        created_at=now,
        modified_at=now,
    )
    result = serialize_post(post_data)
    parsed = frontmatter.loads(result)
    assert "# Different Heading" in parsed.content
```

Add a new test class for `strip_leading_heading`:

```python
from backend.filesystem.frontmatter import strip_leading_heading

class TestStripLeadingHeading:
    def test_strips_matching_heading(self) -> None:
        assert strip_leading_heading("# Hello\n\nContent", "Hello") == "\nContent"

    def test_no_strip_when_no_heading(self) -> None:
        assert strip_leading_heading("Just content", "Title") == "Just content"

    def test_no_strip_when_heading_differs(self) -> None:
        content = "# Other\n\nContent"
        assert strip_leading_heading(content, "Title") == content

    def test_strips_with_leading_whitespace(self) -> None:
        assert strip_leading_heading("\n# Hello\n\nContent", "Hello") == "\nContent"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py -v -k "title_written or leading_heading or strip_leading"`
Expected: FAIL

**Step 3: Implement changes**

Add `strip_leading_heading()` helper in `backend/filesystem/frontmatter.py` (after `extract_title`):

```python
def strip_leading_heading(content: str, title: str) -> str:
    """Remove the first # heading from content if it matches the title."""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# ") and not stripped.startswith("## "):
            heading_text = stripped.removeprefix("# ").strip()
            if heading_text == title:
                # Remove this line and any immediately following blank line
                rest = lines[i + 1 :]
                return "\n".join(rest)
        break  # First non-blank line isn't a heading — stop
    return content
```

Update `serialize_post()` to write title to front matter and strip heading:

```python
def serialize_post(post_data: PostData) -> str:
    """Serialize PostData back to markdown with YAML front matter."""
    metadata: dict[str, Any] = {
        "title": post_data.title,
        "created_at": format_datetime(post_data.created_at),
        "modified_at": format_datetime(post_data.modified_at),
    }
    if post_data.author:
        metadata["author"] = post_data.author
    if post_data.labels:
        metadata["labels"] = [f"#{label}" for label in post_data.labels]
    if post_data.is_draft:
        metadata["draft"] = True

    body = strip_leading_heading(post_data.content, post_data.title)
    post = frontmatter.Post(body, **metadata)
    return str(frontmatter.dumps(post)) + "\n"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rendering/test_frontmatter.py tests/test_services/test_content_manager.py -v`
Expected: ALL PASS (note: some existing tests may need updates since they expect no `title` in front matter — fix those)

**Step 5: Fix any existing test breakage**

Existing tests in `TestSerializePost` create `PostData` with `content="# Test\n\nBody"` and `title="Test"` — the heading will now be stripped from the serialized output. Existing roundtrip tests may need adjustment:
- `test_labels_serialized_with_hash_prefix`: verify `parsed["title"] == "Test"` exists
- `test_full_roundtrip_through_parse`: body will no longer contain `# Round Trip` after serialize, so adjust content assertion

**Step 6: Run full test suite**

Run: `uv run pytest tests/test_rendering/ tests/test_services/test_content_manager.py -v`
Expected: ALL PASS

**Step 7: Commit**

```
feat: serialize title to front matter and strip leading heading
```

---

### Task 3: Add `title` to API schemas and endpoints

**Files:**
- Modify: `backend/schemas/post.py:29-38` (PostEditResponse — add title)
- Modify: `backend/schemas/post.py:41-56` (PostCreate — add title)
- Modify: `backend/schemas/post.py:59-68` (PostUpdate — add title)
- Modify: `backend/api/posts.py:171-189` (get_post_for_edit — return title)
- Modify: `backend/api/posts.py:204-285` (create_post — use title from request)
- Modify: `backend/api/posts.py:288-383` (update_post — use title from request)
- Test: `tests/test_api/test_api_integration.py`

**Step 1: Write failing tests**

In `tests/test_api/test_api_integration.py`, add new tests (or modify existing ones in `TestPostCRUD`):

```python
@pytest.mark.asyncio
async def test_create_post_with_title_field(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/posts",
        json={
            "file_path": "posts/title-test.md",
            "title": "My Explicit Title",
            "body": "Content without heading.",
            "labels": [],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "My Explicit Title"

@pytest.mark.asyncio
async def test_create_post_title_required(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/posts",
        json={
            "file_path": "posts/no-title.md",
            "body": "Content.",
            "labels": [],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_get_post_for_edit_returns_title(self, client: AsyncClient) -> None:
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
    assert data["title"] == "Hello World"

@pytest.mark.asyncio
async def test_update_post_with_title_field(self, client: AsyncClient) -> None:
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.put(
        "/api/posts/posts/hello.md",
        json={
            "title": "Updated Title",
            "body": "Updated content.",
            "labels": ["swe"],
            "is_draft": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_api_integration.py -v -k "title_field or title_required or edit_returns_title"`
Expected: FAIL — 422 for unrecognized `title` field in request body

**Step 3: Implement schema changes**

In `backend/schemas/post.py`:

Add `title` to `PostEditResponse` (after `file_path`):
```python
class PostEditResponse(BaseModel):
    """Structured post data for the editor."""
    file_path: str
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    is_draft: bool = False
    created_at: str
    modified_at: str
    author: str | None = None
```

Add `title` to `PostCreate` (after `file_path`):
```python
    title: str = Field(
        min_length=1,
        max_length=500,
        description="Post title",
    )
```

Add `title` to `PostUpdate` (before `body`):
```python
    title: str = Field(
        min_length=1,
        max_length=500,
        description="Post title",
    )
```

**Step 4: Implement API endpoint changes**

In `backend/api/posts.py`:

Update `get_post_for_edit` (line 181-189) to include title:
```python
    return PostEditResponse(
        file_path=file_path,
        title=post_data.title,
        body=post_data.content,
        ...
    )
```

Update `create_post_endpoint` (line 220-221) to use title from request:
```python
    post_data = PostData(
        title=body.title,
        ...
    )
```

Remove the `extract_title` import usage from create and update endpoints. Update `update_post_endpoint` (line 318) similarly:
```python
    title = body.title
```

Remove the `extract_title` import from the `backend/api/posts.py` imports if no longer needed there. (Keep it in frontmatter.py since parse_post still uses it for fallback.)

**Step 5: Fix existing tests that don't send `title`**

Update all existing API tests that create/update posts to include `"title"` in the JSON body. Key tests to update:
- `test_create_post_authenticated` — add `"title": "New Post"`
- `test_create_post_requires_auth` — add `"title": "No Auth"`
- `test_update_post_authenticated` — add `"title": "Hello World Updated"`
- `test_update_nonexistent_post_returns_404` — add `"title": "Nope"`
- `test_delete_post_authenticated` (create step) — add `"title": "Delete Me"`
- `test_create_post_structured` — add `"title": "Structured Post"`
- `test_update_post_structured` — add `"title": "Hello World Structured"`
- `test_create_and_edit_roundtrip` — add `"title": "Roundtrip"`
- `test_create_draft_post` — add `"title": "..."`
- All other tests that call POST/PUT `/api/posts`

Also update `test_get_post_for_edit` to check for `"title"` in response.

**Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_api_integration.py -v`
Expected: ALL PASS

**Step 7: Commit**

```
feat: add title field to post API schemas and endpoints
```

---

### Task 4: Update sync normalization to backfill title from heading

**Files:**
- Modify: `backend/services/sync_service.py:277-362` (normalize_post_frontmatter)
- Test: `tests/test_sync/test_normalize_frontmatter.py`
- Test: `tests/test_services/test_sync_normalization.py`

**Step 1: Write failing tests**

In `tests/test_sync/test_normalize_frontmatter.py`, add a new test class:

```python
class TestNormalizeTitleBackfill:
    """Tests for title backfill during sync normalization."""

    def test_title_backfilled_from_heading(self, tmp_path: Path) -> None:
        """Post without title in front matter gets it from first heading."""
        content_dir = tmp_path / "content"
        (content_dir / "posts").mkdir(parents=True)
        _write_post(content_dir, "posts/hello.md", "---\n---\n# My Post Title\n\nContent.\n")

        with patch("backend.services.sync_service.now_utc") as mock_now:
            from datetime import UTC, datetime
            mock_now.return_value = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
            normalize_post_frontmatter(
                uploaded_files=["posts/hello.md"],
                old_manifest={},
                content_dir=content_dir,
                default_author="Admin",
            )

        post = _read_post(content_dir, "posts/hello.md")
        assert post["title"] == "My Post Title"
        # Heading should be stripped from body
        assert not post.content.lstrip().startswith("# ")

    def test_title_preserved_when_already_present(self, tmp_path: Path) -> None:
        """Post with title in front matter keeps it unchanged."""
        content_dir = tmp_path / "content"
        (content_dir / "posts").mkdir(parents=True)
        _write_post(
            content_dir,
            "posts/hello.md",
            "---\ntitle: Explicit Title\n---\n\nContent.\n",
        )

        with patch("backend.services.sync_service.now_utc") as mock_now:
            from datetime import UTC, datetime
            mock_now.return_value = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
            normalize_post_frontmatter(
                uploaded_files=["posts/hello.md"],
                old_manifest={},
                content_dir=content_dir,
                default_author="Admin",
            )

        post = _read_post(content_dir, "posts/hello.md")
        assert post["title"] == "Explicit Title"

    def test_title_from_filename_when_no_heading(self, tmp_path: Path) -> None:
        """Post without title or heading gets title derived from filename."""
        content_dir = tmp_path / "content"
        (content_dir / "posts").mkdir(parents=True)
        _write_post(content_dir, "posts/my-cool-post.md", "---\n---\nJust content.\n")

        with patch("backend.services.sync_service.now_utc") as mock_now:
            from datetime import UTC, datetime
            mock_now.return_value = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
            normalize_post_frontmatter(
                uploaded_files=["posts/my-cool-post.md"],
                old_manifest={},
                content_dir=content_dir,
                default_author="Admin",
            )

        post = _read_post(content_dir, "posts/my-cool-post.md")
        assert post["title"] == "My Cool Post"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sync/test_normalize_frontmatter.py -v -k "title"`
Expected: FAIL

**Step 3: Implement changes**

In `backend/services/sync_service.py`, add import at top:
```python
from backend.filesystem.frontmatter import extract_title, strip_leading_heading
```

In `normalize_post_frontmatter()`, after the existing `is_edit` block and before writing the file back (around line 354), add title normalization:

```python
        # Backfill title from first heading if not present
        if "title" not in post.metadata or not post.get("title"):
            title = extract_title(post.content, file_path)
            post["title"] = title
            # Strip the heading from the body since title is now in front matter
            new_content = strip_leading_heading(post.content, title)
            if new_content != post.content:
                post.content = new_content
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sync/test_normalize_frontmatter.py tests/test_services/test_sync_normalization.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: backfill title from heading during sync normalization
```

---

### Task 5: Update frontend API types and functions

**Files:**
- Modify: `frontend/src/api/client.ts:200-208` (PostEditResponse type — add title)
- Modify: `frontend/src/api/posts.ts:41-48` (createPost — add title param)
- Modify: `frontend/src/api/posts.ts:50-55` (updatePost — add title param)

**Step 1: Implement changes**

In `frontend/src/api/client.ts`, add `title` to `PostEditResponse`:
```typescript
export interface PostEditResponse {
  file_path: string
  title: string
  body: string
  labels: string[]
  is_draft: boolean
  created_at: string
  modified_at: string
  author: string | null
}
```

In `frontend/src/api/posts.ts`, add `title` to `createPost` params:
```typescript
export async function createPost(params: {
  file_path: string
  title: string
  body: string
  labels: string[]
  is_draft: boolean
}): Promise<PostDetail> {
  return api.post('posts', { json: params }).json<PostDetail>()
}
```

Add `title` to `updatePost` params:
```typescript
export async function updatePost(
  filePath: string,
  params: { title: string; body: string; labels: string[]; is_draft: boolean },
): Promise<PostDetail> {
  return api.put(`posts/${filePath}`, { json: params }).json<PostDetail>()
}
```

**Step 2: Run type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: Type errors in EditorPage.tsx (doesn't pass `title` yet) — that's expected, fixed in Task 6.

**Step 3: Commit**

```
feat: add title to frontend API types and functions
```

---

### Task 6: Add `title` to `DraftData` and `useEditorAutoSave`

**Files:**
- Modify: `frontend/src/hooks/useEditorAutoSave.ts:6-12` (DraftData — add title)
- Modify: `frontend/src/hooks/useEditorAutoSave.ts:30-39` (statesEqual — compare title)
- Test: `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`

**Step 1: Write failing test**

In `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`, update `baseState` to include `title`:
```typescript
const baseState: DraftData = {
  title: 'Hello',
  body: '# Hello\n\nWorld',
  labels: ['swe'],
  isDraft: false,
}
```

Add a new test in `dirty tracking`:
```typescript
it('is dirty when title changes', () => {
  const onRestore = vi.fn()
  const { result, rerender } = renderHook(
    ({ state }) => useEditorAutoSave({ key: 'test-key', currentState: state, onRestore }),
    { wrapper: createWrapper(), initialProps: { state: baseState } },
  )

  rerender({ state: { ...baseState, title: 'Changed Title' } })
  expect(result.current.isDirty).toBe(true)
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: FAIL — `title` not in DraftData type

**Step 3: Implement changes**

In `frontend/src/hooks/useEditorAutoSave.ts`:

Add `title` to `DraftData`:
```typescript
export interface DraftData {
  title: string
  body: string
  labels: string[]
  isDraft: boolean
  newPath?: string
  savedAt?: string
}
```

Add `title` comparison to `statesEqual`:
```typescript
function statesEqual(a: DraftData, b: DraftData): boolean {
  if (a.title !== b.title) return false
  if (a.body !== b.body) return false
  ...
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add title to DraftData for auto-save dirty tracking
```

---

### Task 7: Update EditorPage with Title input and auto-slug

**Files:**
- Modify: `frontend/src/pages/EditorPage.tsx`
- Test: `frontend/src/pages/__tests__/EditorPage.test.tsx`

**Step 1: Write failing tests**

In `frontend/src/pages/__tests__/EditorPage.test.tsx`:

Update `editResponse` to include `title`:
```typescript
const editResponse: PostEditResponse = {
  file_path: 'posts/existing.md',
  title: 'Existing Post',
  body: 'Content here.',
  ...
}
```

Add new tests:
```typescript
it('renders title input for new post', async () => {
  renderEditor('/editor/new')
  await waitFor(() => {
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
  })
})

it('title input is required - save disabled when empty', async () => {
  renderEditor('/editor/new')
  await waitFor(() => {
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
  })
  const titleInput = screen.getByLabelText('Title')
  // Clear default and verify save button state
  await userEvent.clear(titleInput)
  const saveButton = screen.getByRole('button', { name: /save/i })
  expect(saveButton).toBeDisabled()
})

it('auto-generates file path from title for new post', async () => {
  const user = userEvent.setup()
  renderEditor('/editor/new')
  await waitFor(() => {
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
  })
  await user.clear(screen.getByLabelText('Title'))
  await user.type(screen.getByLabelText('Title'), 'My Great Post')
  await waitFor(() => {
    const filePathInput = screen.getByLabelText('File path')
    expect(filePathInput).toHaveValue(expect.stringContaining('my-great-post'))
  })
})

it('loads title for existing post', async () => {
  mockFetchPostForEdit.mockResolvedValue(editResponse)
  renderEditor('/editor/posts/existing.md')
  await waitFor(() => {
    const titleInput = screen.getByLabelText('Title')
    expect(titleInput).toHaveValue('Existing Post')
  })
})
```

Update existing tests:
- `test_default_body_for_new_post`: body should no longer contain `# New Post`
- `test_restores_draft_content`: draft should include `title`
- Other draft-related tests: include `title` in draft data

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.tsx`
Expected: FAIL

**Step 3: Implement EditorPage changes**

In `frontend/src/pages/EditorPage.tsx`:

1. Add `title` state:
```typescript
const [title, setTitle] = useState('')
```

2. Update default body for new posts (line 22):
```typescript
const [body, setBody] = useState('')
```

3. Add slug generation helper (inside the component or as a module-level function):
```typescript
function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}
```

4. Add `title` to `currentState` for auto-save:
```typescript
const currentState = useMemo<DraftData>(
  () => ({ title, body, labels, isDraft, ...(isNew ? { newPath } : {}) }),
  [title, body, labels, isDraft, isNew, newPath],
)
```

5. Update `handleRestore` to restore title:
```typescript
const handleRestore = useCallback((draft: DraftData) => {
  setTitle(draft.title)
  setBody(draft.body)
  setLabels(draft.labels)
  setIsDraft(draft.isDraft)
  if (draft.newPath) setNewPath(draft.newPath)
}, [])
```

6. When loading existing post, set title:
```typescript
fetchPostForEdit(filePath)
  .then((data) => {
    setTitle(data.title)
    setBody(data.body)
    ...
  })
```

7. Auto-generate file path when title changes (for new posts only). Add a `useRef` to track whether user has manually edited the path:
```typescript
const pathManuallyEdited = useRef(false)

// Auto-generate path from title for new posts
useEffect(() => {
  if (isNew && !pathManuallyEdited.current && title) {
    const date = new Date().toISOString().slice(0, 10)
    const slug = slugify(title)
    if (slug) {
      setNewPath(`posts/${date}-${slug}.md`)
    }
  }
}, [isNew, title])
```

Update file path `onChange` to set the manual flag:
```typescript
onChange={(e) => {
  pathManuallyEdited.current = true
  setNewPath(e.target.value)
}}
```

8. Update `handleSave` to pass title:
```typescript
if (isNew) {
  await createPost({ file_path: path, title, body, labels, is_draft: isDraft })
} else {
  await updatePost(path, { title, body, labels, is_draft: isDraft })
}
```

9. Disable Save when title is empty:
```typescript
disabled={saving || !title.trim()}
```

10. Render Title input in the metadata bar, above file path:
```typescript
<div>
  <label htmlFor="title" className="block text-xs font-medium text-muted mb-1">
    Title
  </label>
  <input
    id="title"
    type="text"
    value={title}
    onChange={(e) => setTitle(e.target.value)}
    disabled={saving}
    placeholder="Post title"
    className="w-full px-3 py-2 bg-paper-warm border border-border rounded-lg
             text-ink text-sm
             focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
             disabled:opacity-50"
  />
</div>
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.tsx`
Expected: ALL PASS

**Step 5: Commit**

```
feat: add title input to editor with auto-slug file path generation
```

---

### Task 8: Update PostPage to render title from metadata

**Files:**
- Modify: `frontend/src/pages/PostPage.tsx:159-164` (remove h1 strip hack)
- Test: `frontend/src/pages/__tests__/PostPage.test.tsx`

**Step 1: Write tests to verify current behavior**

In `frontend/src/pages/__tests__/PostPage.test.tsx`:

Update `postDetail` to have `rendered_html` without the `<h1>` (since backend will no longer include it once body has no heading):
```typescript
const postDetail: PostDetail = {
  ...
  rendered_html: '<p>Content here</p>',
  content: 'Content here',
}
```

The existing test `renders post content` already checks that `'Hello World'` (the title) and `'Content here'` appear — this should still pass because the title is rendered from `post.title` in the header.

Add a test:
```typescript
it('renders title from metadata not from rendered HTML', async () => {
  const postWithNoH1 = {
    ...postDetail,
    rendered_html: '<p>Just body content</p>',
  }
  mockFetchPost.mockResolvedValue(postWithNoH1)
  renderPostPage()

  await waitFor(() => {
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Hello World')
  })
  expect(screen.getByText('Just body content')).toBeInTheDocument()
})
```

**Step 2: Implement changes**

In `frontend/src/pages/PostPage.tsx`, remove the `.replace(/<h1[^>]*>[\s\S]*?<\/h1>\s*/i, '')` regex (line 162). The title is already rendered in the `<header>` as `<h1>{post.title}</h1>` (line 104-106), and the body will no longer contain `<h1>`:

```typescript
<div
  className="prose max-w-none"
  dangerouslySetInnerHTML={{
    __html: renderedHtml,
  }}
/>
```

**Step 3: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/PostPage.test.tsx`
Expected: ALL PASS

**Step 4: Commit**

```
fix: render post title from metadata instead of stripping from HTML
```

---

### Task 9: Run full test suite and fix any remaining issues

**Step 1: Run backend checks**

Run: `just check-backend`
Expected: ALL PASS. Fix any issues that arise.

**Step 2: Run frontend checks**

Run: `just check-frontend`
Expected: ALL PASS. Fix any issues that arise.

**Step 3: Run full checks**

Run: `just check`
Expected: ALL PASS

**Step 4: Commit any fixes**

```
fix: address remaining test and lint issues for title field
```

---

### Task 10: Update ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update relevant sections**

Update the YAML front matter example to include `title`:
```yaml
---
title: Post Title
created_at: 2026-02-02 22:21:29.975359+00
modified_at: 2026-02-02 22:21:35.000000+00
author: Admin
labels: ["#swe"]
---

Content here...
```

Update the bullet point about title extraction:
- **Title** is stored in the `title` front matter field. For legacy files without a `title` field, it is extracted from the first `# Heading` in the body (falling back to filename derivation). Sync normalization backfills the `title` field and strips the heading from the body.

Update recognized front matter fields list to include `title`.

Update "Creating a Post (Editor)" data flow to show title as a separate field:
```
Frontend sends structured data: { file_path, title, body, labels, is_draft }
```

Update "Updating a Post (Editor)" similarly.

**Step 2: Commit**

```
docs: update architecture for title as front matter field
```

---

### Task 11: Browser test end-to-end

**Step 1: Start dev server**

Run: `just start`

**Step 2: Test in browser**

Use Playwright MCP to:
1. Log in
2. Create a new post — verify Title input is present and required
3. Type a title and verify file path auto-generates
4. Save the post
5. View the post — verify title renders correctly
6. Edit the post — verify title loads in the input
7. Update the title and save
8. Verify the updated title appears on the post page

**Step 3: Stop dev server**

Run: `just stop`

**Step 4: Clean up any screenshots**

Remove any `*.png` files created during testing.
