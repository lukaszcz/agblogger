# Backend Crash Resilience Review

**Date:** 2026-02-22
**Scope:** All backend code reviewed for potential server crashes from unhandled exceptions
**Focus:** External failure sources (database, filesystem, pandoc, git, network), invalid content handling

---

## CRITICAL (2)

### C1. Pandoc failure after directory rename leaves filesystem/DB inconsistent

- **Location:** `backend/api/posts.py:561-574`
- **Description:** In `update_post_endpoint`, after `shutil.move()` and `os.symlink()` succeed, `render_markdown()` is called. If pandoc fails, the directory is already renamed and symlinked, but the DB is not updated. The filesystem and database are left permanently inconsistent with no rollback.

### C2. Database failure during `ensure_admin_user` crashes startup

- **Location:** `backend/services/auth_service.py:313`
- **Description:** `session.commit()` during startup. If the database is locked or corrupted, the server fails to start with an unhandled `OperationalError`.

---

## HIGH (12)

### H1. `render_markdown()` RuntimeError uncaught in 5+ endpoints

- **Locations:**
  - `backend/api/render.py:35` -- preview endpoint
  - `backend/api/pages.py:36` -- page rendering
  - `backend/api/posts.py:235-236, 406-407, 504-505, 570-574` -- upload, create, update post
  - `backend/services/page_service.py:42` -- page service
- **Description:** If pandoc is unavailable, times out, or fails on input, all these endpoints crash with unhandled `RuntimeError`. Only `cache_service.rebuild_cache()` catches it.

### H2. `shutil.move()` / `os.symlink()` unhandled OSError in post title rename

- **Location:** `backend/api/posts.py:561-562`
- **Description:** If `shutil.move` succeeds but `os.symlink` fails, the old path is gone with no symlink, breaking old URLs permanently.

### H3. Unhandled `pendulum.ParserError` from user-supplied date strings

- **Locations:**
  - `backend/services/post_service.py:67-72` -- `list_posts` passes user query params (`from_date`, `to_date`) directly to `parse_datetime()`
  - `backend/services/datetime_service.py:35` -- root cause: `pendulum.parse()` raises `ParserError` which doesn't inherit from `ValueError`
- **Description:** User-supplied date strings reach `parse_datetime()` without validation. `pendulum.parse()` raises `ParserError` (not a subclass of `ValueError`) for unparseable strings, causing unhandled 500.

### H4. PermissionError/OSError not caught in config parsing

- **Location:** `backend/filesystem/toml_manager.py:57-61, 101-105`
- **Description:** `parse_site_config` and `parse_labels_config` catch `TOMLDecodeError` and `UnicodeDecodeError` but not `PermissionError`/`OSError` from `read_text()`. Since `site_config` is lazily loaded on nearly every request, a single permission error would crash all requests.

### H5. `read_post` has no error handling (unlike `scan_posts`)

- **Location:** `backend/filesystem/content_manager.py:128-135`
- **Description:** `read_text()` can raise `UnicodeDecodeError`/`OSError`, and `parse_post()` can raise `yaml.YAMLError`/`ValueError`. Unlike `scan_posts` which catches these, `read_post` has no protection. Called from multiple API endpoints.

### H6. Missing `yaml.YAMLError` in sync `normalize_post_frontmatter` except clause

- **Location:** `backend/services/sync_service.py:453-454`
- **Description:** Catches `(UnicodeDecodeError, ValueError)` but not `yaml.YAMLError`. Malformed YAML front matter in synced posts crashes the sync commit.

### H7. Stale lock file prevents server startup

- **Location:** `backend/crosspost/atproto_oauth.py:112-123`
- **Description:** If the server was previously killed (SIGKILL, power loss) between creating the lock file and the `finally` cleanup, a stale `.lock` file remains. The retry loop sleeps for 5 seconds (blocking the event loop), then raises `RuntimeError`, crashing startup.

### H8. `session.commit()` failure after TOML write in labels causes inconsistency

- **Location:** `backend/api/labels.py:47-56`
- **Description:** `write_labels_config()` writes to disk first (line 47), then `session.commit()` follows (line 56). If commit fails (`OperationalError`), the TOML file has the update but the DB does not.

### H9. Cache rebuild failures crash startup

- **Location:** `backend/services/cache_service.py:33-36, 86`
- **Description:** Database operations and `scan_posts()` / `rglob()` during startup can raise `OperationalError` or `OSError`. Since `rebuild_cache` is called in `lifespan()`, any failure crashes the server.

### H10. `rebuild_cache` / `update_server_manifest` failure after sync commit

- **Location:** `backend/api/sync.py:366-371`
- **Description:** Files have been written and git-committed, but if `rebuild_cache` or `update_server_manifest` fails, the response is lost. Client doesn't know sync succeeded and may retry.

### H11. `write_site_config` OSError unhandled across admin endpoints

- **Location:** `backend/services/admin_service.py:41-42, 93-94, 124-125, 178-179`
- **Description:** Called from `update_site_settings`, `create_page`, `update_page`, `delete_page`, `update_page_order`. None of the API handlers catch `OSError`.

### H12. `rglob()` PermissionError crashes cache rebuild

- **Location:** `backend/filesystem/content_manager.py:44-49`
- **Description:** `discover_posts()` uses `rglob("*.md")`. A single permission-denied subdirectory crashes the entire cache rebuild and thus server startup.

---

## MEDIUM (18)

### M1. UnicodeDecodeError from uploaded markdown file

- **Location:** `backend/api/posts.py:208`
- **Description:** `md_bytes.decode("utf-8")` on user-uploaded file. Should return 422, not 500.

### M2. Unhandled yaml.YAMLError/ValueError from `read_post_from_string` in upload

- **Location:** `backend/api/posts.py:210`
- **Description:** Malformed front matter in uploaded posts causes 500.

### M3. Unhandled OSError from `write_bytes` in asset upload

- **Location:** `backend/api/posts.py:345`
- **Description:** Disk full / permissions causes 500. Partial writes possible.

### M4. Unhandled OSError from file operations in admin endpoints

- **Location:** `backend/api/admin.py:108, 148, 167, 130`
- **Description:** `create_page`, `update_page`, `delete_page`, `update_page_order` filesystem writes.

### M5. OSError from `scan_content_files` in sync

- **Locations:**
  - `backend/api/sync.py:131, 365`
  - `backend/services/sync_service.py:78, 94`
- **Description:** TOCTOU races with `stat()`, broken symlinks, permission issues.

### M6. Unhandled OSError from file deletion in sync

- **Location:** `backend/api/sync.py:228`
- **Description:** `full_path.unlink()` without error handling.

### M7. json.JSONDecodeError from corrupted DB label names

- **Location:** `backend/services/label_service.py:58, 89`
- **Description:** `json.loads(label.names)` on potentially corrupted database data.

### M8. FTS5 OperationalError from corrupted index

- **Location:** `backend/services/post_service.py:207`
- **Description:** Search query on corrupted FTS table.

### M9. Non-atomic TOML writes can corrupt config files

- **Location:** `backend/filesystem/toml_manager.py:129-141, 144-161`
- **Description:** `write_bytes()` is not atomic. Server crash mid-write leaves truncated files.

### M10. AttributeError if label entry in TOML is not a dict

- **Location:** `backend/filesystem/toml_manager.py:108-126`
- **Description:** e.g., `foo = "bar"` instead of `[labels.foo]` causes crash.

### M11. `read_page` UnicodeDecodeError

- **Location:** `backend/filesystem/content_manager.py:183`
- **Description:** `read_text()` on non-UTF-8 page file.

### M12. `delete_post` partial failure from `shutil.rmtree`

- **Location:** `backend/filesystem/content_manager.py:168`
- **Description:** Partial directory deletion if one file is locked.

### M13. Missing OSError catch in pandoc subprocess

- **Location:** `backend/pandoc/renderer.py:186-218`
- **Description:** `subprocess.run()` can raise `OSError` (out of file descriptors), not caught.

### M14. Crosspost KeyError from external API responses

- **Location:** `backend/api/crosspost.py:326-335, 663-665`
- **Description:** Bluesky/X token data access without `.get()`.

### M15. Mastodon JSONDecodeError from non-JSON response

- **Location:** `backend/api/crosspost.py:425`
- **Description:** `reg_resp.json()` on non-JSON 200 response from Mastodon instance.

### M16. Database directory not auto-created

- **Location:** `backend/config.py:29`
- **Description:** Default path `data/db/agblogger.db`; directory not created automatically. First-run `OperationalError`.

### M17. Blocking `socket.getaddrinfo` in async SSRF-safe client

- **Location:** `backend/crosspost/ssrf.py:62`
- **Description:** Blocking DNS resolution freezes event loop under slow DNS conditions.

### M18. Corrupted keypair file in lock-loop path unhandled

- **Location:** `backend/crosspost/atproto_oauth.py:119-120`
- **Description:** `_load_existing()` can raise `JSONDecodeError`/`KeyError` in this code path but exceptions aren't caught here (only caught in the initial path).

---

## LOW (10)

- **L1.** Race condition in `register` (`IntegrityError`) -- `backend/api/auth.py:251`
- **L2.** `FileResponse` TOCTOU race -- `backend/api/content.py:130`
- **L3.** Unresolvable symlink in `resolve()` -- `backend/api/content.py:45`
- **L4.** OAuth state/pending `KeyError` (server-controlled data) -- `backend/api/crosspost.py:279, 432`
- **L5.** Database commit errors in login/PAT auth -- `backend/api/auth.py:200`, `backend/api/deps.py:72`
- **L6.** `PostsFTS` conflicting table creation (self-correcting) -- `backend/main.py:131-141`
- **L7.** Blocking I/O in `load_or_create_keypair` (startup only) -- `backend/crosspost/atproto_oauth.py:87-135`
- **L8.** `SocialAccountCreate.account_name` nullability mismatch -- `backend/schemas/crosspost.py:13`
- **L9.** Module-level `create_app()` import-time side effects -- `backend/main.py:290`
- **L10.** X/Facebook crossposters bypass SSRF-safe client (hardcoded URLs) -- `backend/crosspost/x.py`, `backend/crosspost/facebook.py`

---

## Key Patterns

| Pattern | Count | Impact |
|---------|-------|--------|
| `render_markdown()` RuntimeError uncaught | 6 call sites | All content endpoints crash if pandoc fails |
| Filesystem OSError not caught | ~15 locations | Disk full / permission errors cause 500s |
| Config parsing missing OSError | 2 functions | Single permission error crashes ALL requests |
| User input reaching parsers unvalidated | 3 locations | Malformed dates/YAML/UTF-8 cause 500s |
| Filesystem modified before DB commit | 3 locations | Failures leave inconsistent state |
| Non-atomic file writes | 2 config files | Server crash mid-write corrupts config |
