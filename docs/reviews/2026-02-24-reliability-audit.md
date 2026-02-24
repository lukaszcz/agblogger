# Backend Reliability Audit

**Date:** 2026-02-24
**Scope:** Backend crash resilience, unhandled exceptions, race conditions

## Findings

### 1. Missing global exception handlers (backend/main.py)

`ValueError`, `TypeError`, `subprocess.CalledProcessError`, `UnicodeDecodeError`, and `sqlalchemy.exc.OperationalError` can fall through to Starlette's default 500 handler with no app-level logging.

**Fix:** Add `@app.exception_handler()` registrations for each type.

### 2. Lifespan shutdown cascade failure (backend/main.py:241-245)

If `close_renderer()` raises, `pandoc_server.stop()` and `engine.dispose()` are skipped. Resources leak on unclean shutdown.

**Fix:** Wrap each shutdown step in individual try/except blocks.

### 3. Schema migration lacks error context (backend/main.py:94-105)

`_ensure_crosspost_user_id_column()` has no try/except. If the ALTER TABLE fails for a reason other than "column already exists", the error lacks context about what migration was attempted.

**Fix:** Wrap body in try/except that logs at ERROR level and re-raises.

### 4. Git subprocess has no timeout (backend/services/git_service.py)

`_run()` and `merge_file_content()` call `subprocess.run()` without a timeout. A hung git process blocks the event loop indefinitely.

**Fix:** Add `timeout=30` to all `subprocess.run()` calls.

### 5. verify_password crashes on malformed hashes (backend/services/auth_service.py:35-37)

`bcrypt.checkpw()` raises `ValueError` on malformed hash strings (e.g., empty string, non-bcrypt format). This propagates as an unhandled 500.

**Fix:** Wrap in try/except `(ValueError, TypeError)`, return `False`.

### 6. scan_content_files single-file failure aborts scan (backend/services/sync_service.py:84-101)

If `stat()` or `hash_file()` fails for any single file (permission denied, broken symlink), the entire scan fails and sync breaks.

**Fix:** Wrap per-file operations in try/except OSError, log warning and skip.

### 7. TOML write collision on concurrent requests (backend/filesystem/toml_manager.py)

Both `write_labels_config()` and `write_site_config()` use a fixed `.tmp` suffix. Concurrent writes to the same config collide on the temp file.

**Fix:** Use `tempfile.mkstemp()` for unique temp paths. Wrap in try/except that cleans up temp file on failure.

### 8. Health endpoint swallows errors silently (backend/api/health.py:31)

The except block catches all exceptions but doesn't log them. A recurring DB error would be invisible in logs.

**Fix:** Add `logger.warning()` in the except block.

### 9. Pandoc renderer shutdown race (backend/pandoc/renderer.py)

`render_markdown()` reads `_server` and `_http_client` module globals. If `close_renderer()` runs concurrently (e.g., during shutdown), these can become `None` between the check and the use, causing `AttributeError`.

**Fix:** Capture into local variables at function entry.

### 10a. reload_config failure during sync (backend/api/sync.py:374)

`content_manager.reload_config()` is called after sync commit. If it raises (corrupt TOML), the entire sync endpoint fails even though files are already committed.

**Fix:** Wrap in try/except, add warning to sync response.

### 10b. Symlink cleanup failure in delete_post (backend/filesystem/content_manager.py:172-175)

`parent.iterdir()` or `item.resolve()` can raise OSError (broken symlink, permission denied). This aborts the entire delete operation.

**Fix:** Wrap symlink iteration in try/except OSError per item.

### 11. Concurrency safety assumptions undocumented

`OAuthStateStore` and `InMemoryRateLimiter` rely on asyncio's single-threaded model (no await points between check-and-act). This assumption is not documented.

**Fix:** Add thread-safety docstrings.

### 12a. No file size limit on post reads (content_manager.py)

`scan_posts()` and `read_post()` call `read_text()` without size checking. A multi-GB file would exhaust memory.

**Fix:** Add `_MAX_POST_FILE_SIZE = 10MB` check before `read_text()`.

### 12b. No null byte check on post content

Null bytes in markdown files can cause subtle parsing failures downstream.

**Fix:** Check for `\x00` in content in `scan_posts()` and `read_post()`.

### 12c. Invalid timezone string not validated (toml_manager.py)

`parse_site_config()` passes the timezone string through without validation. An invalid timezone will cause failures later when used.

**Fix:** Validate with `zoneinfo.ZoneInfo()`, fall back to UTC.
