# PR Review: Input Validation Improvements (d47bac9..HEAD)

**Date:** 2026-02-26
**Scope:** 21 files, 726 additions, 122 deletions across 3 commits (feaaba6, 32bf8b5, 678be74)
**Review agents:** code-reviewer, pr-test-analyzer, silent-failure-hunter, comment-analyzer, code-simplifier

## Critical Issues (2)

### 1. ~~[Security] Global ValueError handler leaks internal error details to clients~~ RESOLVED

Resolved in c87ca26: Introduced `InternalServerError` exception class. Internal errors (decryption, config, pandoc) now raise `InternalServerError` instead of `ValueError`. Global handler returns generic "Internal server error" (500).

### 2. ~~[Architecture] HTTPException imported into service layer~~ RESOLVED

Resolved in c87ca26: `post_service.py` no longer imports `HTTPException`. Raises `ValueError` from the service; caught in `api/posts.py` to raise `HTTPException(400)`.

## Important Issues (7)

### 3. ~~[Error Handling] AdminPage PagePreview silently swallows preview errors~~ RESOLVED

Added `previewError` state to `PagePreview` component, matching the pattern already used in `EditorPage`. Shows "Preview unavailable" on failure.

### 4. ~~[Error Handling] `raise ValueError from None` discards traceback context~~ RESOLVED

Added `logger.warning()` with `exc_info=True` before the re-raise in both `from_date` and `to_date` parsing blocks, preserving the original parse error in server logs.

### 5. ~~[Error Handling] fetchSocialAccounts silently swallowed in EditorPage~~ RESOLVED

Replaced `.catch(() => {})` with `.catch((err) => { console.warn('Failed to load social accounts', err) })`.

### 6. ~~[Docs] Typo "Bussiness" in 2 files~~ RESOLVED

Fixed to "Business" in `CLAUDE.md` and `docs/guidelines/security.md`.

### 7. ~~[Docs] Stale exception handler count in security docs~~ RESOLVED

Resolved in c87ca26: Updated `docs/guidelines/security.md` and `docs/arch/security.md` with the full handler table.

### 8. ~~[Error Handling] RequestValidationError handler has no logging~~ RESOLVED

Added `logger.warning()` call to the `RequestValidationError` handler in `main.py`.

### 9. ~~[Robustness] Service layer sort fallback weakened~~ RESOLVED

Added explicit `_ALLOWED_SORT_COLUMNS` validation in `list_posts`. Invalid sort columns now raise `ValueError` instead of silently falling back.

## Suggestions (7)

### 10. ~~[Dedup] Extract shared parseErrorDetail utility on frontend~~ RESOLVED

Extracted to `frontend/src/api/parseError.ts`. Replaced duplicated error-parsing logic in `LabelInput.tsx`, `EditorPage.tsx`, and `AdminPage.tsx`.

### 11. ~~[Dedup] Extract page ID error message constant~~ RESOLVED

Extracted `_PAGE_ID_ERROR` constant in `backend/api/admin.py`, used by both PUT and DELETE handlers.

### 12. ~~[Simplify] `str(exc) if str(exc)` calls str() twice~~ RESOLVED

Changed to `str(exc) or "Invalid value"`.

### 13. ~~[Tests] Missing tests for DELETE endpoint page ID validation~~ RESOLVED

Added `test_invalid_page_id_delete_explains_format` to `TestPageIdErrorMessage`.

### 14. ~~[Tests] Missing to_date service-level unit test~~ RESOLVED

Resolved in c87ca26: Added `test_invalid_to_date_raises_value_error`.

### 15. ~~[Tests] Missing CrossPostRequest.post_path max_length test~~ RESOLVED

Added `test_post_path_max_length_rejected` and `test_post_path_valid_length_accepted` to `TestCrosspostSchemaLimits`.

### 16. ~~[Docs] Review document doesn't indicate which items are resolved~~ RESOLVED

This document now marks all resolved items.

## Strengths

- Excellent use of `Literal` types for query parameters, moving validation to the API boundary
- Descriptive page ID validation messages communicate exact constraints
- Title character counter with `maxLength` gives users both enforcement and awareness
- Error-clearing-on-type across Login and Admin pages improves UX
- `previewError` state in EditorPage replaces a silent failure
- Well-structured test file (`test_input_validation.py`) with clear class-per-behavior organization
- Both positive and negative test cases for sort/order/labelMode
- Frontend error parsing handles multiple backend response formats (string detail, array detail)
