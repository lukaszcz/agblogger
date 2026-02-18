# Sync Front Matter Normalization

Auto-fill missing YAML front matter fields when markdown posts are synced to the server, and switch PostCache timestamps to proper DateTime columns.

## Problem

When a user syncs a markdown post file via the CLI, the server writes raw bytes to disk with no validation. If the file has missing or incomplete YAML front matter, the in-memory defaults applied during `rebuild_cache()` never persist back to the file. The filesystem (source of truth) and DB cache can drift.

Additionally, `PostCache` stores timestamps as `Text` columns, making date-range filtering unreliable when timezone offsets vary.

## Design Decisions

- **Timing**: Normalize during `sync_commit`, after all uploads complete but before `scan_content_files()` and `rebuild_cache()`. This ensures the manifest captures post-rewrite hashes.
- **New vs edit detection**: Load the old server manifest at commit time (before updating it). Files in the old manifest are edits; files not in it are new.
- **Uploaded file tracking**: Client sends `uploaded_files: list[str]` in `SyncCommitRequest`. Server only normalizes these files.
- **Scope**: Only `.md` files under `posts/`. Other markdown files (e.g., `about.md`) are not touched.
- **Unrecognized fields**: Preserved in the file, warning returned in sync commit response.
- **DB timestamps**: Switch `PostCache.created_at` and `modified_at` from `Text` to `DateTime(timezone=True)`, stored as UTC. No migration needed since the DB is a regenerable cache.
- **Frontend**: No changes needed — already converts UTC ISO strings to local timezone.

## Recognized Front Matter Fields

| Field | Type | Default (new post) | Default (edit) |
|-------|------|---------------------|----------------|
| `created_at` | datetime with tz | `now_utc()` | Preserved from file |
| `modified_at` | datetime with tz | Same as `created_at` | `now_utc()` (file changed) |
| `author` | string | Site config `default_author` | Preserved from file |
| `labels` | list of `#id` strings | `[]` | Preserved from file |
| `draft` | bool | `false` | Preserved from file |

## Sync Commit Flow (Revised)

```
load old manifest
→ normalize_post_frontmatter(uploaded_files, old_manifest, content_dir, default_author)
→ scan_content_files()
→ update_server_manifest()
→ reload_config()
→ rebuild_cache()
```

## `normalize_post_frontmatter()` Logic

```
Input:  uploaded_files, old_manifest, content_dir, default_author
Output: list of warnings

For each path in uploaded_files:
  1. Skip if not under posts/ or not .md
  2. Read file from disk
  3. Parse front matter via frontmatter.loads()
  4. Collect unrecognized field names → warning per field
  5. Determine new vs edit (path in old_manifest → edit, else → new)
  6. Fill missing recognized fields with defaults
  7. For edits: always set modified_at = now_utc()
  8. Rewrite file on disk via frontmatter.dumps() (preserving unrecognized fields)
```

Operates on the raw front matter dict directly (not through `PostData` / `serialize_post()`) to preserve unrecognized fields.

## PostCache DateTime Migration

```python
# Before
created_at: Mapped[str] = mapped_column(Text, nullable=False)
modified_at: Mapped[str] = mapped_column(Text, nullable=False)

# After
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Ripple effects:
- `cache_service.py`: pass `datetime` objects to `PostCache`
- `api/posts.py`: pass `datetime` objects to `PostCache`; format to ISO at response boundary
- `post_service.py`: datetime-based filtering; parse `from_date`/`to_date` into datetimes
- `schemas/post.py`: ensure response models serialize datetimes to ISO strings

## Files Changed

**New code:**
- `normalize_post_frontmatter()` function
- Recognized fields constant in `frontmatter.py`

**Modified:**
- `backend/api/sync.py` — `uploaded_files` in `SyncCommitRequest`; call normalization
- `backend/services/sync_service.py` — `normalize_post_frontmatter()`
- `backend/filesystem/frontmatter.py` — recognized field set constant
- `backend/models/post.py` — DateTime columns
- `backend/services/cache_service.py` — datetime objects
- `backend/api/posts.py` — datetime objects, format at boundary
- `backend/services/post_service.py` — datetime filtering
- `backend/schemas/post.py` — datetime serialization

**Tests:**
- New tests for `normalize_post_frontmatter()`
- Update existing tests for datetime objects instead of strings
