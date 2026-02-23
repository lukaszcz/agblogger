# CodeRabbit Review — AgBlogger Full Codebase

**Scope:** All changes on `main` (full codebase)
**Date:** 2026-02-23
**Tool:** CodeRabbit CLI v0.3.5

---

## Critical (Bugs / Security)

### 1. Temp directory inside content_dir risks git staging

**File:** `backend/services/git_service.py:131`

`TemporaryDirectory(dir=self.content_dir)` places merge scratch files inside the git-tracked directory. A concurrent `git add -A` from `commit_all`/`try_commit` could stage them.

**Fix:** Use the system temp dir instead:

```python
# Before
with tempfile.TemporaryDirectory(dir=self.content_dir) as td:
# After
with tempfile.TemporaryDirectory() as td:
```

### 2. subprocess.run decodes output with system locale, not UTF-8

**File:** `backend/services/git_service.py:140-146`

The temp files are written as UTF-8, but `subprocess.run(..., text=True)` without an explicit encoding uses the process locale. On non-UTF-8 systems, `result.stdout` will corrupt the merged content.

**Fix:** Add `encoding="utf-8"` to the `subprocess.run` call.

### 3. Merge failure appends to uploaded_paths without writing file

**File:** `backend/api/sync.py:288-296`

When `merge_post_file` raises `CalledProcessError`/`OSError`, the `continue` skips writing content to disk, but `uploaded_paths.append(target_path)` still marks the path as uploaded. This causes `normalize_post_frontmatter` to run on files that weren't modified.

**Fix:** Move `uploaded_paths.append(target_path)` out of the except block into the successful merge path.

### 4. Missing validation for Mastodon account identity fields

**File:** `backend/api/crosspost.py:531-541`

`mastodon_access_token` is validated, but `acct` and `hostname` fall through with empty-string defaults. If the Mastodon instance returns a valid token but omits user identity fields, `account_name` becomes `"@@"`.

**Fix:** Validate both `acct` and `hostname` are non-empty before constructing `account_name`, raising `HTTP_502_BAD_GATEWAY` otherwise.

### 5. Rename rollback is best-effort — double-failure leaves inconsistent state

**File:** `backend/api/posts.py:616-650`

If `shutil.move` succeeds but `os.symlink` fails, the rollback move may also fail. The directory then exists at the new path, there's no symlink at the old path, but the DB references the old path. The next cache rebuild would not find the post.

**Recommendation:** Document as a known limitation; the dual logging is appropriate.

---

## Suggestions (Improvements)

### 6. Sync client total count includes skipped local deletes

**File:** `cli/sync_client.py:250-251`

`len(to_delete_local)` includes files skipped due to path traversal or non-existence. The reported total is slightly inflated.

**Fix:** Track actual deletes with a counter incremented only on successful deletion.

### 7. FilterPanel ignores clicks during closing animation

**File:** `frontend/src/components/filters/FilterPanel.tsx:40-46`

When `panelState` is `'closing'`, `togglePanel` does nothing. The user must wait for the animation to finish before re-opening.

**Fix:** Treat `'closing'` like `'closed'` in `togglePanel`.

### 8. Mutation test env var collision risk

**File:** `tests/conftest.py:71-89`

`MUTANT_UNDER_TEST` is a generic name that could collide with other tools. The `object()` placeholder for `atproto_oauth_key` will raise `AttributeError` if any mutation reaches OAuth code.

**Fix:** Rename to `AGBLOGGER_MUTANT_UNDER_TEST`; consider using a minimal real keypair.

### 9. Test never asserts navigation after upload

**File:** `frontend/src/pages/__tests__/TimelinePage.test.tsx:253-274`

The test "successful upload navigates to post" sets up `mockNavigate` but only asserts `mockUploadPost` was called. Navigation is never verified.

**Fix:** Add `expect(mockNavigate).toHaveBeenCalledWith('/posts/3')` assertion.

### 10. Misleading test descriptions: "throws SecurityError"

**File:** `frontend/src/components/share/__tests__/testUtils.test.ts:54-68`

Tests claim "throws SecurityError" but assertions only check for the string `'Access denied'`. Either rename tests or tighten assertions to verify the error type.

### 11. Test has no assertion after Close button click

**File:** `frontend/src/components/filters/__tests__/FilterPanel.test.tsx:201-215`

The test "closes panel via Close button" clicks Close but never verifies the outcome.

**Fix:** Assert panel transitions to `'closing'` state after the click.

### 12. Typo in testing docs

**File:** `docs/arch/testing.md:162`

"due mutmut" should be "due to mutmut".

---

## Documentation Issues

### 13. GPL licensing for embedded Pandoc documentation

**File:** `docs/pandoc/23-authors.md`

Verbatim excerpts from the Pandoc manual (GPL v2+) are embedded. Verify license compatibility. Stale copyright year (2024).

### 14. Broken cross-reference in Pandoc docs

**File:** `docs/pandoc/18-reproducible-builds.md:9`

Link `11.1-epub-metadata.html#epub-metadata` is an HTML-relative reference from upstream Pandoc and won't resolve in local Markdown context.

### 15. Orphaned heading sections in Pandoc docs

**File:** `docs/pandoc/08-pandocs-markdown.md:189-193`

Sections 8.5.2, 8.7.7, 8.7.9, 8.12.3, and 8.12.5 have no body content, creating empty TOC nodes.

### 16. Inconsistent request-header example

**File:** `docs/pandoc/05-defaults-files.md:138`

CLI column shows `--request-header foo:bar` while defaults column shows `["User-Agent", "Mozilla/5.0"]`.

### 17. Incorrect branch name in security review

**File:** `docs/reviews/2026-02-22-security-review.md:5`

Lists branch as `main` but the review was for `vscode-changes`.

### 18. Contradictory first-sync semantics

**File:** `docs/plans/2026-02-22-sync-simplification-design.md:42`

States "Client uploads overwrite server files" then immediately says conflicts use server-wins semantics.
