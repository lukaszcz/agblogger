# PR Review: Input Validation Improvements (d47bac9..HEAD)

**Date:** 2026-02-26
**Scope:** 21 files, 726 additions, 122 deletions across 3 commits (feaaba6, 32bf8b5, 678be74)
**Review agents:** code-reviewer, pr-test-analyzer, silent-failure-hunter, comment-analyzer, code-simplifier

## Critical Issues (2)

### 1. [Security] Global ValueError handler leaks internal error details to clients

`backend/main.py:433-437`

The handler now forwards `str(exc)` verbatim. Since `ValueError` is used throughout the codebase for both business-logic and internal errors, this exposes internal details like:

- `"Path traversal detected: {rel_path}"` (filesystem/content_manager.py)
- `"Failed to decrypt credential data"` (services/crypto_service.py)
- `"Insecure production configuration: {joined}"` (config.py)
- Pandoc server connection details (pandoc/server.py)

This violates the security guideline: "Never expose internal server error details to clients."

**Fix:** Introduce a `BusinessValidationError(ValueError)` subclass for intentionally user-facing errors. Keep the global `ValueError` handler returning generic messages. Or handle specific `ValueError`s at the route level.

### 2. [Architecture] HTTPException imported into service layer

`backend/services/post_service.py:10`

This is the only service file that imports `HTTPException`. The codebase pattern is: services raise domain exceptions, API layer translates to HTTP responses. This couples the service layer to FastAPI, breaking it for non-HTTP callers (CLI, sync).

**Fix:** Raise `ValueError` from the service and catch it in `backend/api/posts.py` to raise `HTTPException(400, ...)`.

## Important Issues (7)

### 3. [Error Handling] AdminPage PagePreview silently swallows preview errors

`frontend/src/pages/AdminPage.tsx:53-55`

The same silent preview failure that was fixed in `EditorPage` (with `previewError` state) was left unchanged here with `// Silently ignore preview failures`.

### 4. [Error Handling] `raise HTTPException from None` discards traceback context

`backend/services/post_service.py:74-78, 85-89`

The original `ValueError` from `parse_datetime` is completely discarded. The server should log the original error before re-raising.

### 5. [Error Handling] fetchSocialAccounts silently swallowed in EditorPage

`frontend/src/pages/EditorPage.tsx:109-111`

`.catch(() => {})` with no logging or error state. Pre-existing but in a modified file.

### 6. [Docs] Typo "Bussiness" in 2 files

`AGENTS.md:87`, `docs/guidelines/security.md:9` -- should be "Business".

### 7. [Docs] Stale exception handler count in security docs

`docs/guidelines/security.md:90` and `docs/arch/security.md:176` -- say "Five handlers" but there are now 11. The table also claims all handlers return "only generic messages," which is no longer true after the `ValueError` and `RequestValidationError` changes.

### 8. [Error Handling] RequestValidationError handler has no logging

`backend/main.py:367-376`

Unlike every other exception handler in the file, this one has zero logging. Also, it strips `loc` to just the last element, losing context for nested fields.

### 9. [Robustness] Service layer sort fallback weakened

`backend/services/post_service.py:131`

The explicit allowlist was removed but the function signature still accepts `str`. Non-API callers get a silent fallback to `created_at` via `getattr(PostCache, sort, PostCache.created_at)`.

## Suggestions (7)

### 10. [Dedup] Extract shared parseErrorDetail utility on frontend

Three components (`LabelInput.tsx`, `EditorPage.tsx`, `AdminPage.tsx`) duplicate ~45 lines of error-response parsing logic. Extract to `frontend/src/api/parseError.ts`.

### 11. [Dedup] Extract page ID error message constant

`backend/api/admin.py:159-160, 185-186` -- identical 3-line error string repeated. Extract to a module constant.

### 12. [Simplify] `str(exc) if str(exc)` calls str() twice

`backend/main.py:433` -- use `str(exc) or "Invalid value"` instead.

### 13. [Tests] Missing tests for DELETE endpoint page ID validation

Only PUT is tested in `TestPageIdErrorMessage`. The DELETE endpoint has the same validation but no test.

### 14. [Tests] Missing to_date service-level unit test

`test_error_handling.py` -- `from_date` has a service-level test but the old `to_date` test was removed.

### 15. [Tests] Missing CrossPostRequest.post_path max_length test

Only `platform` max_length is tested. `post_path` max_length=500 is untested.

### 16. [Docs] Review document doesn't indicate which items are resolved

`docs/reviews/2026-02-26-input-validation-review.md` -- items fixed in the same commit still appear as open findings.

## Strengths

- Excellent use of `Literal` types for query parameters, moving validation to the API boundary
- Descriptive page ID validation messages communicate exact constraints
- Title character counter with `maxLength` gives users both enforcement and awareness
- Error-clearing-on-type across Login and Admin pages improves UX
- `previewError` state in EditorPage replaces a silent failure
- Well-structured test file (`test_input_validation.py`) with clear class-per-behavior organization
- Both positive and negative test cases for sort/order/labelMode
- Frontend error parsing handles multiple backend response formats (string detail, array detail)
