# Input Validation & User-Friendliness Review

Date: 2026-02-26

## Critical: Silent Fallbacks (user gets wrong results with no explanation)

1. **Sort/order/label_mode query params silently fall back to defaults** — `backend/api/posts.py:126-131`, `backend/services/post_service.py:125-142`. If a user passes `?sort=invalid`, it silently becomes `?sort=created_at`. They should get a 400 error instead.

2. **Invalid date filters silently ignored** — `backend/services/post_service.py:68-82`. If `from_date` or `to_date` can't be parsed, the filter is dropped with only a log warning. The user sees unfiltered results with no explanation.

3. **Preview rendering failures are silent** — `frontend/src/pages/EditorPage.tsx:128`. If Pandoc preview fails, the user gets no indication. The preview area simply doesn't update.

## High: Generic / Unhelpful Error Messages

4. **Global ValueError handler returns "Invalid value"** — `backend/main.py:417-423`. Business logic errors (duplicate checks, cycle detection) all collapse into this one message. The specific reason from `str(exc)` should be forwarded.

5. **No custom RequestValidationError handler** — Pydantic's default format (`"ensure this value has at least 1 character"`) is passed through raw. A custom handler could produce messages like "Title is required".

6. **422 errors not mapped to fields** — `frontend/src/pages/EditorPage.tsx:161-185`. Validation errors are joined into a single banner string. The user sees `"title: ensure this value has at least 1 character, body: ..."` but can't tell which field to fix at a glance.

7. **LabelInput shows "Invalid label" for all 422 errors** — `frontend/src/components/editor/LabelInput.tsx:78-84`. Doesn't extract or show the backend's detail message.

8. **Page ID validation error is vague** — `backend/api/admin.py:156,178`. Returns "Invalid page ID" without explaining the required format.

## Medium: Missing Client-Side Validation

9. **No frontend format validation for:**
   - Post title length (backend limit: 500 chars) — no counter or limit shown
   - Post body length (backend limit: 500K chars) — no counter shown
   - Page ID format (must be `^[a-z0-9][a-z0-9_-]*$`) — no constraint shown
   - Timezone input (must be valid IANA timezone) — only placeholder text
   - Bluesky handle format — only empty check
   - Password requirements on admin change — inconsistency across endpoints

10. **File upload restrictions not shown upfront** — 10 MB limit only appears after a 413 error. Should be visible near the upload button.

11. **No required field indicators on most forms** — Only admin site title has `*`. Other required fields (post title, label display names, login fields) have no visual indicator.

## Medium: Inconsistencies

12. **Password min_length mismatch** — `LoginRequest.password` min_length=1 vs `RegisterRequest.password` min_length=12. Login allows any length (correct), but admin password change requires min 8. Three different minimums across the app.

13. **Missing max_length on crosspost schemas** — `platform` and `post_path` have `min_length=1` but no upper bound.

14. **Error clearing is inconsistent** — Some forms clear errors when the user starts typing, others only on resubmission, and some persist across page navigations.

## Low: Polish Items

15. **Disabled button states use only opacity** — `disabled:opacity-50` is subtle.

16. **Success messages can scroll off-screen** — No toast system; all feedback is inline banners.

17. **No character counters** on long-text fields (only cross-post dialog has them).

18. **No `created_at <= modified_at` validation** in frontmatter parsing.

## What's Working Well

- Cross-post character limits with real-time counter and disabled submit
- Mastodon hostname validation with inline error
- File upload size enforcement (10 MB) and path traversal checks
- Label cycle prevention in both frontend and backend
- All submit buttons disabled during async operations
- Auth 401 consistently prompts re-login across all pages
- Sync endpoint has good validation messages
