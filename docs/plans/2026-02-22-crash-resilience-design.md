# Backend Crash Resilience Design

**Date:** 2026-02-22
**Review:** docs/reviews/2026-02-22-crash-resilience-review.md
**Scope:** Fix all 42 identified crash vulnerabilities (2 critical, 12 high, 18 medium, 10 low)

## Principles

- The server must never crash from unhandled exceptions during request handling
- Startup failures should crash with clear, actionable error messages
- Filesystem operations should complete before database commits where possible
- External service failures (pandoc, git, DNS) must be caught and reported gracefully
- Invalid user input (dates, YAML, UTF-8) must return 4xx, not 500
- Config file writes must be atomic (write-to-temp-then-rename)

## Layer 1: Global Exception Handlers

Register exception handlers in `main.py` via `app.exception_handler()`:

| Exception | HTTP Status | Response |
|-----------|-------------|----------|
| `RuntimeError` | 502 | "Rendering service unavailable" |
| `OSError` | 500 | "Storage operation failed" |
| `yaml.YAMLError` | 422 | "Invalid content format" |
| `json.JSONDecodeError` | 500 | "Data integrity error" |

All handlers log the full exception with traceback at ERROR level and return structured JSON. These are the safety net, not the primary defense.

## Layer 2: Targeted Endpoint Fixes

### C1 - Render before rename (posts.py `update_post_endpoint`)

Restructure the title-change code path: call `render_markdown()` before `shutil.move()`/`os.symlink()`. If rendering fails, the post is never renamed. This eliminates the filesystem/DB inconsistency window entirely.

### H1 - Pandoc RuntimeError in endpoints

Add targeted try/except around `render_markdown()` calls in:
- `render.py:preview` - catch RuntimeError, return 502
- `pages.py:get_page` - catch RuntimeError, return 502
- `posts.py:create_post_endpoint` - catch RuntimeError, rollback session, return 502
- `posts.py:upload_post` - catch RuntimeError, clean up written files, return 502
- `posts.py:update_post_endpoint` - catch RuntimeError, rollback session, return 502

### H2 - shutil.move/os.symlink OSError

Wrap the rename+symlink sequence in try/except. If `shutil.move` succeeds but `os.symlink` fails, move the directory back.

### H3 - pendulum.ParserError

Catch `pendulum.parsing.exceptions.ParserError` in `parse_datetime` and convert to `ValueError`. Also add explicit date format validation in `post_service.list_posts` before calling `parse_datetime`.

### H8 - Labels filesystem/DB atomicity

In `_persist_labels_and_commit`: wrap `session.commit()` in try/except. On commit failure, re-write the old labels to TOML to restore consistency.

### H10 - Sync post-commit cache rebuild

Wrap `rebuild_cache` and `update_server_manifest` in try/except within `_sync_commit_inner`. On failure, log error and add a sync warning, but still return the response since files were already written and git-committed.

### M1 - Upload UTF-8 validation

Wrap `md_bytes.decode("utf-8")` in try/except, return 422 on `UnicodeDecodeError`.

### M2 - Upload YAML validation

Wrap `read_post_from_string` in try/except for `yaml.YAMLError` and `ValueError`, return 422.

### M14 - Crosspost KeyError

Use `.get()` with defaults for external API response fields in Bluesky and X OAuth callbacks. Raise HTTPException(502) when required fields are missing.

### M15 - Mastodon JSONDecodeError

Wrap `reg_resp.json()` in try/except for `json.JSONDecodeError`, return 502.

## Layer 3: Service/Library Hardening

### H4 - Config parsing OSError

Add `OSError` to the except clauses in `parse_site_config` and `parse_labels_config` in `toml_manager.py`. Return defaults with a warning, same as existing `TOMLDecodeError` handling.

### H5 - read_post error handling

Add the same try/except as `scan_posts`: catch `(UnicodeDecodeError, ValueError, yaml.YAMLError, OSError)` and return `None` with a warning log.

### H6 - Sync YAML

Add `yaml.YAMLError` to the except clause in `sync_service.normalize_post_frontmatter`.

### M7 - json.loads on DB label names

Wrap `json.loads(label.names)` in try/except in `label_service.py`.

### M10 - TOML label type check

Add `AttributeError` to handle non-dict label entries in `parse_labels_config`, or add an `isinstance` check before `.get()`.

### M11 - read_page error handling

Wrap `read_text()` in try/except for `(UnicodeDecodeError, OSError)`, return `None`.

### M13 - Pandoc subprocess OSError

Add `OSError` to the except clause in `_render_markdown_sync`, raise `RuntimeError` with a descriptive message.

### M8 - FTS5 OperationalError

Wrap the FTS5 search query in `post_service.search_posts` in try/except for `OperationalError`, return empty results with a warning log.

## Layer 4: Startup Hardening

### C2, H9, H12 - Lifespan error handling

Wrap each startup phase in the lifespan function with try/except that logs a clear, actionable message before re-raising:

```
"Failed to initialize database: {error}. Check database path and permissions."
"Failed to rebuild cache: {error}. Check content directory permissions."
"Failed to create admin user: {error}. Check database integrity."
```

The server should still crash on startup failures, but with messages that guide the operator to the fix.

### H7 - Stale lock file

In `load_or_create_keypair`: check lock file age before entering the retry loop. If the lock file is older than 30 seconds, remove it and log a warning. Also catch exceptions from `_load_existing()` in the lock-loop code path.

### M16 - Database directory

Auto-create the database directory from the `database_url` path before creating the engine.

## Layer 5: Atomic Writes & Async Fixes

### M9 - Atomic TOML writes

Replace `path.write_bytes()` with a write-to-temp-then-rename pattern in `write_labels_config` and `write_site_config`:
```python
tmp = path.with_suffix(".tmp")
tmp.write_bytes(data)
tmp.replace(path)  # atomic on POSIX
```

### M17 - Async DNS resolution

Replace `socket.getaddrinfo()` with `await loop.getaddrinfo()` in `ssrf.py`.

### M18 - Keypair load in lock loop

Wrap `_load_existing()` call inside the lock-acquisition loop with the same try/except as the initial path.

## Layer 6: Low-Severity Fixes

- **L1** - Register race: catch `IntegrityError` in register endpoint, return 409
- **L2/L3** - Content serving: these are handled acceptably by FastAPI/Starlette defaults
- **L4** - OAuth state KeyError: add defensive `.get()` checks
- **L5** - DB commit in auth: covered by global OSError handler
- **L6** - PostsFTS table: no fix needed (self-correcting)
- **L7** - Blocking I/O at startup: acceptable (startup only)
- **L8** - account_name nullability: set schema default to `""` instead of `None`
- **L9** - Import-time create_app: no fix needed
- **L10** - X/Facebook SSRF client: not a crash risk, skip

## File Change Summary

| File | Changes |
|------|---------|
| `backend/main.py` | Global exception handlers, lifespan try/except, DB dir auto-create |
| `backend/api/posts.py` | Render-before-rename, pandoc try/except, upload validation |
| `backend/api/render.py` | Pandoc try/except |
| `backend/api/pages.py` | Pandoc try/except |
| `backend/api/labels.py` | Commit failure recovery |
| `backend/api/sync.py` | Cache rebuild try/except |
| `backend/api/admin.py` | OSError handling |
| `backend/api/auth.py` | IntegrityError catch in register |
| `backend/api/crosspost.py` | KeyError/JSONDecodeError handling |
| `backend/filesystem/toml_manager.py` | OSError catch, atomic writes, type checks |
| `backend/filesystem/content_manager.py` | read_post/read_page error handling |
| `backend/pandoc/renderer.py` | OSError catch |
| `backend/services/datetime_service.py` | ParserError -> ValueError |
| `backend/services/post_service.py` | Date validation, FTS error handling |
| `backend/services/label_service.py` | json.loads error handling |
| `backend/services/sync_service.py` | yaml.YAMLError catch |
| `backend/services/admin_service.py` | Covered by API layer changes |
| `backend/crosspost/atproto_oauth.py` | Stale lock, exception handling |
| `backend/crosspost/ssrf.py` | Async DNS |
| `backend/schemas/crosspost.py` | account_name default |
