# CodeRabbit Full Codebase Review

Date: 2026-02-18

## Critical (Security & Bugs)

### 1. Hardcoded default credentials in sync CLI

**File:** `cli/sync_client.py:300-301`

Hardcoded default credentials `"admin"/"admin"`. Should require explicit credentials and fail if missing.

### 2. Path traversal in sync download

**File:** `cli/sync_client.py:151`

Server-provided `file_path` is interpolated into the download URL without sanitization. A malicious server could craft paths with traversal sequences.

### 3. Page ID path traversal

**File:** `backend/api/pages.py:25-34`

No path traversal validation on `page_id` parameter passed to `get_page()`. Should validate against a strict pattern.

### 4. XSS in fallback renderer

**File:** `backend/pandoc/renderer.py:141-153`

Potential XSS in `_fallback_render` link href — no scheme validation allows `javascript:` URLs.

### 5. Plaintext credential storage

**File:** `backend/services/crosspost_service.py:44`

Social account credentials stored as plaintext JSON in the database.

### 6. Unauthenticated crosspost history

**File:** `backend/api/crosspost.py:135-155`

Cross-post history endpoint lacks authentication, exposing which platforms users post to.

### 7. Broken token refresh retry

**File:** `frontend/src/api/client.ts:35-45`

Token refresh retry pattern is incorrect: consumed request bodies can't be replayed, and `ky(request, options)` should be `ky.retry()` with a new `Request`.

### 8. DB commit before filesystem delete

**File:** `backend/api/posts.py:275-280`

DB commit happens before filesystem delete. If file deletion fails, the post reappears after cache rebuild since filesystem is source of truth.

### 9. Filesystem write before DB commit

**File:** `backend/api/labels.py:83-93`

Labels are written to `labels.toml` before `session.commit()`. If DB commit fails, filesystem and DB are inconsistent.

### 10. Partial edge insertion on cycle detection

**File:** `backend/services/label_service.py:130-139`

If cycle detected mid-iteration over parents list, earlier edges are already added to the session.

### 11. In-place mutation of shared LabelDef

**File:** `backend/api/labels.py:158-163`

In-place mutation of `LabelDef.parents` on shallow-copied dict affects `ContentManager` state before `write_labels_config` is called.

## Important (Bugs & Data Integrity)

### 12. parse_datetime TypeError on YAML objects

**File:** `backend/services/sync_service.py:276-282`

`parse_datetime()` will `TypeError` when YAML parser returns `datetime`/`date` objects instead of strings.

### 13. Unhandled ValueError in JWT user_id parsing

**File:** `backend/api/deps.py:57`

`int(user_id)` on JWT `sub` claim can raise unhandled `ValueError` on malformed tokens, producing 500 instead of 401.

### 14. Naive vs aware datetime comparison

**File:** `backend/services/auth_service.py:114-118`

Potential naive vs aware datetime comparison when parsing `expires_at` (could raise `TypeError`).

### 15. Grapheme counting for Bluesky

**File:** `backend/crosspost/bluesky.py:35-41`

Character limit uses `len()` (code points) instead of grapheme clusters. AT Protocol enforces 300 grapheme limit.

### 16. Hashtag facet position mismatch

**File:** `backend/crosspost/bluesky.py:67-83`

`text.find()` matches first occurrence, not the suffix where tags were appended.

### 17. Mastodon truncation edge case

**File:** `backend/crosspost/mastodon.py:30-36`

When `available <= 3`, truncation produces just `"..."` or a negative slice.

### 18. Index-based platform-to-result mapping

**File:** `backend/api/crosspost.py:121-132`

Assumes result order matches input order. Platform name should come from the result itself.

### 19. Stale search results on cleared query

**File:** `frontend/src/pages/SearchPage.tsx:14-28`

Previous results persist when query is cleared (no `setResults([])` on empty query).

### 20. Retry button is a no-op

**File:** `frontend/src/pages/TimelinePage.tsx:87-89`

`setSearchParams(searchParams)` doesn't trigger re-fetch if params haven't changed.

### 21. Null connection source/target

**File:** `frontend/src/pages/LabelGraphPage.tsx:268-294`

Missing null check on `connection.source`/`connection.target` (both nullable in React Flow `Connection`).

### 22. Missing useEffect dependency

**File:** `frontend/src/pages/EditorPage.tsx:34-60`

`initialAuthor` missing from `useEffect` dependencies; author won't update if user changes while on new post page.

### 23. Silent auth check failures

**File:** `frontend/src/stores/authStore.ts:50-56`

Non-401 errors in `checkAuth` silently swallowed, leaving user in indeterminate auth state.

### 24. Active tab overlap

**File:** `frontend/src/components/layout/Header.tsx:120-139`

Labels and Graph tabs both appear active on `/labels/graph` because `startsWith('/labels/')` matches both.

### 25. Nullable column in unique constraint

**File:** `backend/models/crosspost.py:26-33`

Nullable `account_name` in `UniqueConstraint` allows duplicate NULL entries per `(user_id, platform)`.

### 26. Blocking subprocess in async context

**File:** `backend/pandoc/renderer.py:18-35`

Blocking `subprocess.run()` can block the async event loop.

### 27. Unused fallback renderer

**File:** `backend/pandoc/renderer.py:73-138`

`_fallback_render` is defined but never called from `render_markdown()`.

### 28. Unclosed httpx client

**File:** `cli/sync_client.py:75-85`

`SyncClient` never closes its `httpx.Client` (no `close()` or context manager support).

### 29. Fragile date string concatenation

**File:** `backend/services/post_service.py:56-62`

Appending time components to date strings breaks if caller passes full ISO timestamp.

### 30. Settings mismatch

**File:** `backend/main.py:137-150`

Potential settings mismatch between `cli_entry()`'s `Settings()` and module-level `app`.

## Suggestions (Code Quality)

### 31. Username max_length inconsistency

**File:** `backend/schemas/auth.py:13-14`

`LoginRequest.username` allows `max_length=100` but `RegisterRequest` limits to 50.

### 32. LabelCreate accepts empty names

**File:** `backend/schemas/label.py:48-53`

`LabelCreate.names` has no `min_length=1`, allowing labels with no display names.

### 33. Confusing label source logic

**File:** `backend/services/cache_service.py:130-138`

Confusing source determination logic with inner import. Can be simplified.

### 34. Missing page config validation

**File:** `backend/filesystem/toml_manager.py:55-62`

Missing error handling for required `id` field in page config entries.

### 35. Missing focus-visible styles

**File:** `frontend/src/index.css:48-58`

Links have hover styles but no `:focus-visible` state for keyboard accessibility.

### 36. Inaccessible overlay link

**File:** `frontend/src/pages/LabelListPage.tsx:63`

Overlay link lacks accessible text (`aria-label`).

### 37. Discarded error details

**Files:** `frontend/src/pages/TimelinePage.tsx:62-63`, `frontend/src/pages/SearchPage.tsx:22-23`

Catch blocks discard error details without logging.

### 38. Caddyfile path matcher

**File:** `Caddyfile:27-29`

Path matcher should use `/*.html` not `.html` (Caddy requires leading `/`).

### 39. List numbering skip

**File:** `docs/history.md:23-25`

Numbered list skips item 9.

### 40. Typos in initial prompt

**File:** `docs/initial_prompt.md:58`

"KeTeX" should be "KaTeX", "sings" should be "signs".

### 41. Stale architecture doc

**File:** `docs/ARCHITECTURE.md:55`

Lists `atproto` as dependency but code uses `httpx` directly.

### 42. Dagre version

**File:** `frontend/package.json:18`

`@dagrejs/dagre` version `^2.0.4` may not exist on npm; latest is `1.1.8`.
