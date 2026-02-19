# Code Review: Error Handling in Three-Way Merge Fixes (f722dff)

**Date:** 2026-02-19
**Branch:** main
**Scope:** Error handling, silent failures, path validation, and code duplication in commit f722dff ("fix: address all issues from three-way merge code review")

**Files changed:** 22 modified (+2316, -84 lines)

---

## Critical

| # | Issue | Location |
|---|-------|----------|
| 1 | **`show_file_at_commit` returns `None` for genuine git errors** — three failure modes (file doesn't exist, invalid hash, git error) all return `None`. Caller in `sync.py` treats `None` as "file deleted", so a corrupt repo or disk error silently discards the server's version during merge. | `git_service.py:98-114` |

## High

| # | Issue | Location |
|---|-------|----------|
| 2 | **`try_commit` logs at `warning` without exception details** — no returncode, stderr, or traceback. Git commit failures break three-way merge correctness but the log gives no clue why. Should log at `error` with `exc` details. | `git_service.py:72-82` |
| 3 | **Sync commit git failure not surfaced to client** — if `try_commit` fails during sync, `head_commit()` returns a stale hash that the client saves as `last_sync_commit`, corrupting merge bases for all future syncs. The `warnings` response field is available but unused. | `sync.py:301` |
| 4 | **`_delete_post_fts` catches bare `Exception`** — swallows database corruption, programming bugs, session state errors. Should catch only `sqlalchemy.exc.OperationalError`. | `posts.py:119` |
| 5 | **Path traversal validation duplicated 4 times** — same `resolve()` + `is_relative_to()` pattern in `sync_upload`, `sync_download`, and `_sync_commit_inner` (×2). CLAUDE.md: "Avoid code duplication." | `sync.py` |
| 6 | **Git commit try/except boilerplate duplicated 7 times** — identical pattern across posts.py (×3), labels.py (×3), sync.py (×1). | `posts.py`, `labels.py`, `sync.py` |

## Medium

| # | Issue | Location |
|---|-------|----------|
| 7 | **`show_file_at_commit` silently returns `None` for invalid commit hash** — no logging. Corrupted `last_sync_commit` silently falls back to "no base available" (server always wins), discarding client edits. | `git_service.py:100-101` |
| 8 | **CLI `_upload_file` doesn't handle HTTP errors per-file** — one failed upload aborts the batch, leaving server with some files uploaded but no commit. Partial failure with no recovery info. | `sync_client.py:140-153` |
| 9 | **CLI path validation uses weak `".." in fp` check** — doesn't use `resolve()` + `is_relative_to()` like the server. Symlinks or encoded paths could bypass. | `sync_client.py:76-78` |
| 10 | **`normalize_post_frontmatter` has no error handling for malformed files** — invalid UTF-8 or broken YAML aborts the entire sync commit after partial modifications. | `sync_service.py:311-350` |
| 11 | **`normalize_post_frontmatter` path traversal not surfaced in warnings** — silently `continue`s, inconsistent with sync.py which raises 400. | `sync_service.py:301-305` |
| 12 | **`SyncInitRequest.last_sync_commit` field accepted but never used** — dead code in schema. CLI sends it but server ignores it. | `sync.py:63` |
| 13 | **FTS SQL strings duplicated** — same FTS delete SQL in `_upsert_post_fts` and `_delete_post_fts`. | `posts.py` |

## Resolved by code simplification

Issues 5, 6, and 13 were resolved by extracting:
- `_resolve_safe_path()` in sync.py (issue 5)
- `GitService.try_commit()` (issue 6)
- `_FTS_DELETE_SQL` / `_FTS_INSERT_SQL` constants (issue 13)
- `_is_safe_path()` in CLI sync_client.py

## Test Coverage Gaps

| Priority | Gap |
|----------|-----|
| 8/10 | CLI `sys.exit(1)` on failed merge download is untested |
| 7/10 | API endpoints succeeding when `commit_all()` raises — untested |
| 7/10 | `OSError` during merge returning HTTP 500 — untested |
| 6/10 | `init_repo()` error handling when git unavailable — untested |
| 5/10 | CLI merge result path traversal rejection — untested |
| 5/10 | `show_file_at_commit` non-128 git error logging path — untested |

## Strengths

- Commit hash regex validation (`_COMMIT_RE`) prevents CLI injection
- Path traversal protection consistently applied across sync endpoints
- Dot-file exclusion prevents `.git/` leaking into sync manifest
- Three-way merge integration tests are excellent (406 lines, all scenarios)
- `asyncio.Lock` for concurrent sync protection
- FTS cache maintenance keeps search results fresh between rebuilds
- Empty repo handling prevents startup crashes
