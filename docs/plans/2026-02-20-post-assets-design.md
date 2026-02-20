# Post Assets: Directories, File Uploads, and Relative Paths

## Problem

Posts cannot reference local files (images, PDFs, videos). There is no mechanism to upload assets via the web UI, no content file serving endpoint, and no relative path resolution in rendered markdown.

## Design

### Filesystem Structure

New posts created via the web UI use a post-per-directory convention:

```
content/posts/
  2026-02-20-my-great-post/
    index.md
    photo.png
    diagram.pdf
  2026-02-20-my-great-post-2/    # collision handled with suffix
    index.md
  2026-02-02-hello-world.md      # legacy flat post (still works)
```

Slug generation: `YYYY-MM-DD-<slugified-title>`. Title is lowercased, non-alphanumeric characters replaced with hyphens, collapsed and trimmed, truncated to a reasonable length. On collision, append `-2`, `-3`, etc.

The subdirectory is auto-generated and never exposed in the UI. The `file_path` (e.g., `posts/2026-02-20-my-great-post/index.md`) is an internal detail.

### Content File Serving

New public API route:

```
GET /api/content/{file_path}
```

- Public (no auth) for published post assets, matching existing read access model
- Read-only, serves files with appropriate `Content-Type`
- Restricted to safe paths (`posts/`, `assets/`) with traversal protection
- Returns `FileResponse` for efficient streaming
- Follows symlinks (important for renames)

### Relative Path Resolution

When rendering post HTML, relative paths in `<img>`, `<a>`, `<source>`, `<video>`, and `<audio>` tags are rewritten to absolute paths based on the post's directory:

- Post at `posts/2026-02-20-my-post/index.md` with `<img src="photo.png">`
- Rewritten to `<img src="/api/content/posts/2026-02-20-my-post/photo.png">`

This rewriting is a post-processing step after Pandoc rendering and HTML sanitization.

### File Upload API

New endpoint:

```
POST /api/posts/{file_path}/assets
```

- Auth required (same as post editing)
- Accepts `multipart/form-data` with one or more files
- Max 10 MB per file
- Saves to the same directory as the post's markdown file
- Returns list of uploaded filenames
- Git commit on upload

### Editor Changes

- New posts: frontend auto-generates the directory slug from the title. The `file_path` field is hidden.
- Upload button in editor toolbar: drag-and-drop or file picker. On upload, inserts `![filename](filename)` at cursor for images, `[filename](filename)` for other files.
- Asset list panel showing uploaded files for the current post.

### Directory Rename on Title Change

When an existing post's title changes via the editor:

1. Generate new slug from the new title (preserving the original date prefix)
2. Rename the directory: `posts/old-slug/` to `posts/new-slug/`
3. Create a symlink: `posts/old-slug` -> `posts/new-slug` (old URLs still resolve)
4. Update the database cache with the new file path
5. Git commit captures the rename and symlink

The content serving endpoint follows symlinks, so old URLs continue to work.

The slug only changes when the directory-name portion (derived from title) actually differs. If the title change produces the same slug, no rename occurs. If the new slug collides with an existing directory, append a numeric suffix.

### Backward Compatibility

- Existing flat posts (`posts/hello-world.md`) continue to work without changes
- The system handles both flat files and directory-based posts
- No migration required; only new posts use the directory convention
- Sync protocol works with both structures (files are tracked by path)

## Decisions

| Decision | Rationale |
|----------|-----------|
| `index.md` convention | Standard (Hugo, Gatsby). Co-located assets with simple relative paths. |
| Public content serving | Blog images must be visible to all readers |
| Symlinks on rename | Preserves old URLs without HTTP redirects |
| No migration of old posts | Backward compatibility; no disruption to sync clients |
| 10 MB file size limit | Matches existing sync upload limit |
| Path rewriting in renderer | Single place to handle; works for both preview and published view |
