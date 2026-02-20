# Post Upload via Web UI — Design

**Goal:** Allow users to upload existing markdown posts (single file or folder with assets) through the Web UI, with the same YAML frontmatter processing as the sync protocol.

## Backend

### New endpoint: `POST /api/posts/upload`

Accepts multipart form data. Auth required. Optional query parameter `title` (used when frontend prompts the user for a missing title).

**Processing:**

1. **Find the markdown file** among uploaded files:
   - If any file is named `index.md`, use it as post content
   - Otherwise, use the single `.md` file
   - If no `.md` file or multiple `.md` files (without `index.md`), return 422
2. **Parse frontmatter** via existing `parse_post()` — same as sync/cache rebuild
3. **Normalize fields** (same rules as sync commit):
   - `title`: from frontmatter → first `# heading` → `title` query param → 422 error
   - `created_at`: from frontmatter or now
   - `modified_at`: from frontmatter or now
   - `author`: from frontmatter or authenticated user
   - `labels`: from frontmatter or empty
   - `is_draft`/`draft`: from frontmatter or `false`
4. **Generate directory** via `generate_post_path(title, posts_dir)`
5. **Write all files** — markdown rewritten with normalized frontmatter + all non-markdown files as assets
6. **Create PostCache**, render HTML with URL rewriting, update FTS index
7. **Git commit**
8. Return `PostDetail`

**Error responses:**
- No `.md` file found: `422 {"detail": "No markdown file found in upload"}`
- No title: `422 {"detail": "no_title"}` — signals frontend to prompt
- File too large (>10MB per file): `413`

## Frontend

### Timeline page

An "Upload" button on the Timeline page (visible to authenticated users, next to the "New Post" link). Clicking opens a small dropdown with two options:

- **Upload file** — opens a file picker accepting `.md` files
- **Upload folder** — opens a folder picker (via `webkitdirectory`) for a directory containing `index.md` + assets

### Upload flow

1. User selects file(s)
2. Frontend sends all files to `POST /api/posts/upload`
3. If 422 with `"no_title"` — show a title prompt dialog, resend with `?title=<user_input>`
4. On success — navigate to `/post/{result.file_path}`
5. On error — show error message inline

### Title prompt dialog

A modal with a text input: "This markdown file has no title. Please enter one:" with Upload and Cancel buttons.

## Constraints

- 10 MB per file limit (same as asset upload)
- Only creates new posts — does not update existing ones
- Slug collision handled by `generate_post_path` (appends `-2`, `-3`, etc.)
- Unrecognized frontmatter fields are preserved in the file (same as sync)
