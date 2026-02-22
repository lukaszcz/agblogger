# Sync Simplification PR Review — 2026-02-22

Review of 10 commits implementing sync simplification: two-step protocol (status/commit), hybrid merge (semantic frontmatter + git merge-file body), CLI simplification (sync-only), merge3 dependency removal.

## Review Agents Used

- **code-reviewer**: General code quality and CLAUDE.md compliance
- **pr-test-analyzer**: Test coverage quality and completeness
- **silent-failure-hunter**: Error handling and silent failures
- **comment-analyzer**: Comment accuracy and documentation quality

---

## Critical Issues

### 1. UnicodeDecodeError catch silently enables binary file overwrite
**File**: `backend/api/sync.py:246-250`
**Source**: silent-failure-hunter

When reading the server's current file fails with `UnicodeDecodeError`, `server_content` is set to `None`. This causes the code to fall through and overwrite the server's binary file with the client's text content. No conflict is detected, no warning is emitted.

### 2. git merge-file exit codes >= 128 misinterpreted as conflicts
**File**: `backend/services/git_service.py:147-152`
**Source**: silent-failure-hunter, code-reviewer

`merge_file_content` only raises for negative return codes (signals). But `git merge-file` returns exit code 128+ for genuine errors (corrupt repo, permissions, etc.), which the current code misinterprets as "N conflict regions." Additionally, `CalledProcessError` from signal kills is unhandled in `_sync_commit_inner`.

### 3. CLI `_download_file` crashes entire sync on HTTP errors
**File**: `cli/sync_client.py:144-154`
**Source**: silent-failure-hunter, code-reviewer

`resp.raise_for_status()` raises `httpx.HTTPStatusError` on any non-2xx response with no error handling. This crashes the sync, leaves the local manifest unsaved, and the server state already committed. The old code had explicit error handling for this.

### 4. Field deletion silently dropped in front matter merge
**File**: `backend/services/sync_service.py:306-325`
**Source**: code-reviewer, silent-failure-hunter

When server wins on a conflict by deleting a field (`server_val is None`), the field is silently removed but client changes are discarded without conflict reporting. For fields like `title`, this could produce invalid posts.

### 5. No test coverage for front matter field deletion semantics
**File**: `backend/services/sync_service.py:306-325`
**Source**: pr-test-analyzer

No tests verify behavior when fields are present in base but removed by one or both sides. The `None` guards create implicit deletion behavior that is never tested.

---

## High Issues

### 6. CLI commit POST `raise_for_status` unhandled
**File**: `cli/sync_client.py:190-195`
**Source**: silent-failure-hunter

Server errors (413, 400, 500) on the commit POST produce raw tracebacks. Local state left inconsistent.

### 7. Git failures in `_get_base_content` silently degrade to baseless merges
**File**: `backend/api/sync.py:338-355`
**Source**: silent-failure-hunter

All `CalledProcessError` exceptions treated identically. Genuine git failures (corrupt repo) disguised as content conflicts, silently dropping all client changes. Logged at `warning` level instead of `error`.

### 8. Uploads with no filename silently skipped
**File**: `backend/api/sync.py:229-231`
**Source**: silent-failure-hunter

No logging or warning when a file upload has no filename.

### 9. OSError from file writes produces opaque 500 errors
**File**: `backend/api/sync.py:257-258,283,289-291`
**Source**: silent-failure-hunter

The old code had explicit `OSError` handling around merge file writes. This was removed in the refactor.

### 10. Malformed YAML in merge inputs crashes entire sync
**File**: `backend/services/sync_service.py:350-361`
**Source**: silent-failure-hunter

`frontmatter.loads()` can raise `yaml.YAMLError` on invalid front matter. Not caught, crashes entire sync.

### 11. No validation of metadata JSON structure
**File**: `backend/api/sync.py:206-212`
**Source**: code-reviewer, silent-failure-hunter

Metadata JSON parsed but contents not validated. Type annotation `list[str]` is static only. Malformed metadata produces confusing errors deep in the call stack.

### 12. Conflict files discard cleanly merged content
**File**: `backend/api/sync.py:271-280`
**Source**: code-reviewer, comment-analyzer

When body conflicts but labels merge cleanly, the entire merged result is discarded. Non-conflicting client changes (e.g., label additions) are lost.

---

## Medium Issues

### 13. `files_synced` count is misleading
**File**: `backend/api/sync.py:330`
**Source**: code-reviewer

Returns total number of files in content directory, not actual files changed.

### 14. Path traversal in delete loop silently skipped
**File**: `cli/sync_client.py:209-212`
**Source**: silent-failure-hunter

No user notification when server-provided delete path fails traversal check.

### 15. Git commit failure demoted to warning
**File**: `backend/api/sync.py:302-317`
**Source**: silent-failure-hunter

A git commit failure affects integrity of future syncs but is returned with status "ok".

### 16. Failed downloads not tracked in sync summary
**File**: `cli/sync_client.py:204-206`
**Source**: silent-failure-hunter

Download failures not counted; sync summary overstates success.

### 17. Test dummy never raises on HTTP errors
**File**: `tests/test_sync/test_sync_client.py:25-27`
**Source**: silent-failure-hunter

`_DummyResponse.raise_for_status()` always returns None, no error path test coverage.

---

## Comment/Documentation Issues

### 18. `merge_post_file` docstring inaccurate about modified_at stripping
**File**: `backend/services/sync_service.py:348`
**Source**: comment-analyzer

Says "modified_at is stripped before merge" but the function doesn't strip anything; `merge_frontmatter()` excludes the key during iteration.

### 19. "Server version is already on disk; no write needed" comment misleading
**File**: `backend/api/sync.py:280`
**Source**: comment-analyzer

Implies server version is the desired final state, but merged content (with non-conflicting client changes) is actually discarded.

### 20. "Binary file -- read raw bytes for hash comparison" comment inaccurate
**File**: `backend/api/sync.py:249-250`
**Source**: comment-analyzer

No hash comparison happens. `server_content` is just set to `None`.

### 21. git merge-file exit code comment slightly inaccurate
**File**: `backend/services/git_service.py:147`
**Source**: comment-analyzer

Says "exit 1-127 = number of conflict regions" but 127 actually means "127 or more."

### 22. `compute_sync_plan` docstring has stale "push scenario" framing
**File**: `backend/services/sync_service.py:103-112`
**Source**: comment-analyzer

References "push" concept that was removed in sync simplification.

### 23. `SyncPlanItem` docstring says "conflict" but class is generic
**File**: `backend/api/sync.py:71-76`
**Source**: comment-analyzer

Class docstring says "describing a conflict" but the class has generic fields.

### 24. No comment explaining baseless merge design decision
**File**: `backend/services/sync_service.py:353-359`
**Source**: comment-analyzer

When `base is None`, body is reported as conflicted with no explanation why.

### 25. `merge_frontmatter` docstring omits silent resolution of unrecognized fields
**File**: `backend/services/sync_service.py:260-266`
**Source**: comment-analyzer

Docstring doesn't mention that unrecognized field conflicts are NOT reported.

### 26. ARCHITECTURE.md imprecise about modified_at handling
**File**: `docs/ARCHITECTURE.md:360-361`
**Source**: comment-analyzer

"Stripped from both sides" implies explicit removal; actually just excluded from iteration.

---

## Test Coverage Gaps

### 27. No test for invalid metadata JSON returning 400
**Source**: pr-test-analyzer

### 28. No test for file upload size limit (413 response)
**Source**: pr-test-analyzer

### 29. No test for binary file upload through sync commit
**Source**: pr-test-analyzer

### 30. No test for `_get_base_content` fallback when commit doesn't exist
**Source**: pr-test-analyzer

### 31. No test for non-post .md file conflict handling (last-writer-wins)
**Source**: pr-test-analyzer

### 32. No test for CLI path traversal rejection in downloads
**Source**: pr-test-analyzer

### 33. No test for commit-response `to_download` entries
**Source**: pr-test-analyzer

### 34. No test for `merge_frontmatter` with labels as non-list types
**Source**: pr-test-analyzer

### 35. CLI tests don't verify multipart request payload contents
**Source**: pr-test-analyzer

### 36. `test_draft_conflict` name is misleading (not actually a conflict)
**Source**: pr-test-analyzer

---

## Positive Observations

- Well-structured test decomposition: breaking `test_merge.py` into three files mirrors implementation architecture
- Strong integration test coverage for core merge flow
- Security regression tests maintained (path traversal, auth requirements)
- Clean `merge3` dependency removal
- Good coverage of `compute_sync_plan` function
- Labels merge tested end-to-end
- `TestRemovedMethods` explicitly verifies old API surface was removed
- Code follows CLAUDE.md conventions (type annotations, naming, async patterns)
- `merge_frontmatter()` docstring clearly documents merge rules
- `show_file_at_commit()` docstring explains dual return semantics well
- Sync commit endpoint docstring documents multipart form data contract
- `_sync_lock` comment explains *why* the lock exists
- ARCHITECTURE.md protocol diagram accurately reflects new two-step protocol
