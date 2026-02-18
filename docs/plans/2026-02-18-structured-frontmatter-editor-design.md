# Structured Front Matter Editor

YAML front matter should not be directly editable or visible in the editor text field. Structured UI controls above the editor handle metadata; the text field contains only the markdown body. The backend owns all YAML serialization — the frontend never constructs or parses front matter.

## Backend API Changes

### New: `GET /api/posts/{path}/edit` (auth required)

Reads the `.md` file from disk, parses front matter, returns structured JSON:

```json
{
  "file_path": "posts/2026-02-18-hello.md",
  "body": "# Hello World\n\nContent here...",
  "labels": ["swe", "cooking"],
  "is_draft": false,
  "created_at": "2026-02-18T12:00:00+00:00",
  "modified_at": "2026-02-18T12:00:00+00:00",
  "author": "Admin"
}
```

### New: `POST /api/labels` (auth required)

Creates a label by ID. Accepts `{ "id": "cooking" }`. Writes to `labels.toml`, updates DB cache. Returns `LabelResponse`. 409 if already exists.

### Modified: `POST /api/posts` (create)

New request schema — structured input instead of raw content string:

```json
{
  "file_path": "posts/2026-02-18-hello.md",
  "body": "# Hello World\n\nContent here...",
  "labels": ["swe"],
  "is_draft": false
}
```

Backend sets `author` from the authenticated user, `created_at = now()`, `modified_at = now()`. Assembles `PostData`, serializes front matter + body, writes to disk.

### Modified: `PUT /api/posts/{path}` (update)

New request schema:

```json
{
  "body": "# Updated content...",
  "labels": ["swe", "cooking"],
  "is_draft": false
}
```

Backend preserves `created_at` and `author` from the existing post. Sets `modified_at = now()`. Serializes and writes.

## Frontend Editor Redesign

### Metadata Bar (above editor)

- **Labels**: Tag-style input with typeahead dropdown showing existing labels. Typing a non-existent label shows a "Create #newlabel" option. Selecting it calls `POST /api/labels`, then adds the chip. Each label renders as a removable chip.
- **Draft toggle**: Toggle switch, defaults to off for new posts.
- **Author**: Read-only text from the logged-in user.
- **Dates**: Read-only formatted `created_at` and `modified_at`. Hidden for new posts.

### Editor Text Field

Contains only the markdown body. No YAML front matter.

### New Post Flow

1. Navigate to `/editor/new`
2. Body: `# New Post\n\nStart writing here...`
3. Labels empty, draft off, author from auth store
4. Dates hidden (not yet created)
5. Save → `POST /api/posts` with structured data

### Edit Existing Post Flow

1. Navigate to `/editor/posts/path.md`
2. `GET /api/posts/posts/path.md/edit` loads structured data
3. Body, labels, draft populate respective controls
4. Author and dates read-only
5. Save → `PUT /api/posts/{path}` with structured data

### Label Creation

1. User types non-existent label in typeahead
2. Dropdown shows "Create #newlabel" option
3. Select → `POST /api/labels` with ID
4. Success → add chip. 409 → label exists, add it anyway.
