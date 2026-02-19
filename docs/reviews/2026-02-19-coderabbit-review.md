# Review: CodeRabbit AI Code Review

**Date:** 2026-02-19
**Method:** CodeRabbit CLI (`coderabbit review --plain -t committed`)
**Scope:** Full codebase review triggered by UI improvement commit

## Findings

### 1. H1 regex won't match multi-line content

**Files:** `PostPage.tsx:159`, `PageViewPage.tsx:51`
**Severity:** Bug

The regex `/<h1[^>]*>.*?<\/h1>\s*/i` uses `.` which doesn't match newlines in JavaScript. If an H1 tag contains newlines, the strip fails.

**Fix:** Use `[\s\S]*?` instead of `.*?`.

### 2. EditorPage user dependency causes re-fetch

**File:** `EditorPage.tsx:40-65`
**Severity:** Bug

The `useEffect` depends on `user`, so auth refresh re-runs the effect and overwrites unsaved edits for existing posts.

**Fix:** Split into two effects — one for loading existing posts (depends on `filePath`, `isNew`), one for new post defaults (depends on `isNew`, `user`).

### 3. Naive datetime in sync_service

**File:** `backend/services/sync_service.py:280-281`
**Severity:** Bug

`datetime(year, month, day)` creates a naive datetime. Downstream `format_datetime` may expect timezone-aware values.

**Fix:** Add `tzinfo=timezone.utc`.

### 4. DB committed before filesystem write in labels API

**Files:** `backend/api/labels.py` — create (76-93), update (125-141), delete (158-177)
**Severity:** Bug

If `write_labels_config` fails after `session.commit()`, the DB has the change but `labels.toml` doesn't. Next cache rebuild from disk loses the change.

**Fix:** Write filesystem first, then commit. Rollback on filesystem failure.

### 5. Cycle detection deletes edges before checking

**File:** `backend/services/label_service.py:162-175`
**Severity:** Bug

`update_label` deletes existing parent edges before checking new parents for cycles. A `ValueError` from cycle detection leaves the label without edges unless the caller rolls back.

**Fix:** Check cycles before deleting edges.

### 6. Request body lost on retry after token refresh

**File:** `frontend/src/api/client.ts:36-51`
**Severity:** Bug

After a 401 refresh, `request.body` may be consumed (`bodyUsed`). The retry sends an empty body for POST/PUT/PATCH requests.

**Fix:** Use ky's `options` parameter to retry with original request options.

### 7. JWT sub claim accepts int type

**File:** `backend/api/deps.py:57-58`
**Severity:** Minor

`isinstance(user_id, (str, int))` accepts integers, but JWT `sub` is always a string per RFC 7519.

**Fix:** Check `isinstance(user_id, str)` only.

### 8. Conflicting min_length and default_factory on label names

**File:** `backend/schemas/label.py:51-52`
**Severity:** Minor

`names: list[str] = Field(default_factory=list, min_length=1)` — the empty list default fails min_length validation when names is omitted.

**Fix:** Remove `default_factory=list` to make names required.

### 9. CORS origins not configurable for production

**File:** `backend/main.py:111-118`
**Severity:** Minor

Production CORS is hardcoded to empty list. If frontend and API are on different origins, requests are blocked.

**Fix:** Add `cors_origins` setting loaded from environment.

### 10. Platform index fallback masks mismatch

**File:** `backend/api/crosspost.py:123-134`
**Severity:** Minor

Silent empty-string fallback for platform index masks a results/platforms length mismatch.

**Fix:** Assert 1:1 correspondence or include platform in result objects.

### 11. Dagre version claim is incorrect

**File:** `docs/reviews/2026-02-18-coderabbit-full-codebase.md:257-261`
**Severity:** Documentation

Item 42 claims `@dagrejs/dagre@2.0.4` may not exist — it does (npm latest).

**Fix:** Remove or correct the item.

### 12. Unreachable break in plan doc

**File:** `docs/plans/2026-02-18-multi-parent-labels-plan.md:740-743`
**Severity:** Documentation

`break` after `raise HTTPException` is unreachable.

**Fix:** Remove the dead `break`.

### 13. README triple backticks inside fenced block

**File:** `README.md:183`
**Severity:** Documentation

Triple backticks inside a fenced code block may cause rendering issues.

### 14. Missing @pytest.mark.asyncio on async tests

**File:** `tests/test_labels/test_label_dag.py:92-136`
**Severity:** False positive

The project uses `asyncio_mode = "auto"` in pyproject.toml, which applies the marker automatically.

### 15. Caddyfile path matching scope

**File:** `Caddyfile:27-29`
**Severity:** Needs verification

Caddy wildcard behavior may differ from intent. Needs manual verification of intended caching scope.
