# CodeRabbit Code Review — 21 Commits

**Date:** 2026-02-20
**Scope:** Last 21 commits (`ba86828..9062621`): slug generation, content serving, post assets, draft visibility, directory rename, post upload, delete dialog
**Tool:** CodeRabbit CLI v0.3.5

## Verification Summary

| Status | Count |
|--------|-------|
| Already fixed | 20 |
| Fixed in this pass | 2 |
| Not applicable | 3 |
| **Total** | **25** |

## Critical — Security (5)

### 1. Default credentials in sync CLI — ALREADY FIXED

**File:** `cli/sync_client.py:300-301`

Code falls back to `"admin"/"admin"` when credentials are omitted from args and config. If users forget to configure credentials, the CLI silently authenticates with well-known defaults.

**Fix:** Remove hardcoded defaults; require explicit credentials or fail fast.

### 2. Path traversal in page endpoint — ALREADY FIXED

**File:** `backend/api/pages.py:25-34`

`page_id` is passed directly to `get_page` without validation. A crafted ID like `../../../etc/passwd` could escape the content directory.

**Fix:** Validate `page_id` against a strict pattern (e.g., `^[a-zA-Z0-9_-]+$`) before passing to `get_page`.

### 3. XSS via link href in fallback renderer — ALREADY FIXED

**File:** `backend/pandoc/renderer.py:141-153`

`_inline_format` inserts captured href directly into HTML. A `javascript:alert(1)` scheme would be rendered as-is.

**Fix:** Validate href scheme against an allowlist (`http`, `https`, `mailto`) before inserting into the `<a>` tag.

### 4. Credentials stored in plain text — ALREADY FIXED

**File:** `backend/services/crosspost_service.py:44`

Social account OAuth credentials are stored as plain JSON in the database.

**Fix:** Encrypt credentials at rest using a symmetric key (e.g., Fernet).

### 5. `int(user_id)` ValueError on malformed JWT — ALREADY FIXED

**File:** `backend/api/deps.py:53-58`

If a tampered JWT has a non-integer `sub` claim, `int(user_id)` raises an unhandled `ValueError`, producing a 500 instead of a 401.

**Fix:** Wrap in try/except `ValueError` and return `None`.

## Bugs (6)

### 6. Hashtag facet position mismatch in Bluesky cross-poster — ALREADY FIXED

**File:** `backend/crosspost/bluesky.py:67-83`

`text.find(tag_text)` returns the first occurrence in the full text. If the same hashtag appears in the excerpt, the facet byte offsets will be wrong, pointing to the excerpt occurrence instead of the appended tag.

**Fix:** Use `rfind` or search with a start index based on the known suffix region.

### 7. Grapheme vs code point counting for Bluesky character limit — FIXED

**File:** `backend/crosspost/bluesky.py:35-41`

Bluesky enforces a 300-grapheme limit (UAX #29 extended grapheme clusters). Python `len()` counts code points, so emoji with modifiers (e.g., family emoji) are miscounted.

**Fix:** Replaced `len()` with `grapheme.length()` and string slicing with `grapheme.slice()` for counting and truncation.

### 8. Naive vs aware datetime comparison in token expiry — ALREADY FIXED

**File:** `backend/services/auth_service.py:114-118`

`datetime.fromisoformat(stored_token.expires_at)` may return a naive datetime if the stored string lacks timezone info. Comparing with `datetime.now(UTC)` would raise `TypeError`.

**Fix:** After parsing, check `expires.tzinfo is None` and set to UTC if naive.

### 9. DB commit before filesystem delete — ALREADY FIXED

**File:** `backend/api/posts.py:275-280`

`session.commit()` runs before `content_manager.delete_post()`. If file deletion fails, the post is gone from the database but the file remains on disk.

**Fix:** Delete the file first, then commit the DB change. On file deletion failure, rollback and raise 500.

### 10. Token refresh retry uses consumed request body — ALREADY FIXED

**File:** `frontend/src/api/client.ts:36-42`

The `afterResponse` hook calls `ky(request, options)` directly. Ky consumes the request body on the first attempt, so the retry will fail for POST/PUT requests with a body.

**Fix:** Use `state.retryCount` guard and `new Request(request, { headers })` with `ky.retry()`.

### 11. Missing null check in React Flow `onConnect` — ALREADY FIXED

**File:** `frontend/src/pages/LabelGraphPage.tsx:268-294`

`Connection.source` and `Connection.target` can be `string | null`. The code assigns them directly without null checks and passes potentially null values to `fetchLabel()`.

**Fix:** Add `if (!connection.target || !connection.source) return` early guard.

## Suggestions (9)

### 12. Stale `initialAuthor` in EditorPage useEffect — ALREADY FIXED

**File:** `frontend/src/pages/EditorPage.tsx:34-60`

The useEffect that sets author for new posts depends on `[filePath, isNew]` but uses `initialAuthor` computed from `user` outside the effect. If the user changes after mount, the author won't update.

**Fix:** Add `user` to the dependency array or compute author inline.

### 13. Non-401 errors silently ignored in `checkAuth` — ALREADY FIXED

**File:** `frontend/src/stores/authStore.ts:50-56`

If `fetchMe()` fails with a network error or 500, the catch block only handles 401. Other errors leave the user in an indeterminate auth state.

**Fix:** Set `user: null` and clear tokens for all error types.

### 14. Retry button may not trigger refetch — ALREADY FIXED

**File:** `frontend/src/pages/TimelinePage.tsx:87-89`

`setSearchParams(searchParams)` with the same params may not trigger React Router's change detection.

**Fix:** Use a retry counter state variable to force the fetch effect to re-run.

### 15. Overlay link lacks accessible text — ALREADY FIXED

**File:** `frontend/src/pages/LabelListPage.tsx:63`

The `<Link>` covering the label card has no text content, making it invisible to screen readers.

**Fix:** Add `aria-label={`View label ${label.name}`}`.

### 16. Missing focus state for keyboard accessibility — ALREADY FIXED

**File:** `frontend/src/index.css:48-58`

`.prose a` has hover styles but no visible focus state for keyboard navigation.

**Fix:** Add `.prose a:focus-visible` with an outline or ring style.

### 17. Active state overlap between Labels and Graph tabs — N/A

**File:** `frontend/src/components/layout/Header.tsx:120-139`

The Labels tab active check uses `startsWith('/labels/')` which also matches `/labels/graph`, causing both tabs to appear active.

**Status:** Labels and Graph are shown as a single segmented control, not separate tabs. The current behavior is intentional.

### 18. Nullable `account_name` in unique constraint — ALREADY FIXED

**File:** `backend/models/crosspost.py:26-33`

`account_name` is nullable but included in a `UniqueConstraint`. NULL values are not considered equal in SQL, so multiple rows with `(user_id, platform, NULL)` would be allowed.

**Fix:** Make `account_name` non-nullable with a default, or use a partial unique index.

### 19. Settings mismatch between `cli_entry()` and global `app` — FIXED

**File:** `backend/main.py:259-269`

`cli_entry()` creates its own `Settings()` instance but references the global `app` created at module load with a different `Settings()`. Environment variable changes between import and execution would cause inconsistency.

**Fix:** Changed `cli_entry()` to use `app.state.settings` instead of creating a new `Settings()` instance.

### 20. Architecture doc lists `atproto` as dependency — ALREADY FIXED

**File:** `docs/ARCHITECTURE.md:55`

The tech stack table lists `atproto` for cross-posting, but the code uses `httpx` directly against the AT Protocol HTTP API.

**Fix:** Replace `atproto` with `httpx` in the table.

## Documentation (5)

### 21. Review doc out of sync with current code — N/A

**File:** `docs/reviews/2026-02-17-codebase-review.md:107-122`

Lists `backend/models/sync.py` as missing `from __future__ import annotations`, but the import is present.

**Status:** Historical review document; reflects state at time of that review. No change needed.

### 22. Unreachable `break` in plan code snippet — N/A

**File:** `docs/plans/2026-02-18-multi-parent-labels-plan.md:739-744`

`break` after `raise HTTPException` is dead code.

**Status:** Plan document code snippet, not production code. No change needed.

### 23. Plan/test casing mismatch — ALREADY FIXED

**File:** `docs/plans/2026-02-18-structured-frontmatter-editor-design.md:209-214`

Plan asserts `data["author"] == "admin"` but test uses `"Admin"`.

### 24. Typos in initial prompt — ALREADY FIXED

**File:** `docs/initial_prompt.md:58`

"KeTeX" should be "KaTeX", "sings" should be "signs".

### 25. Missing item 9 in numbered list — ALREADY FIXED

**File:** `docs/history.md:23`

List jumps from item 8 to item 10.
