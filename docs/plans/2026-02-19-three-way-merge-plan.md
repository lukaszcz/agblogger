# Three-Way Merge for Sync Conflicts

## Context

Sync conflicts (both sides modified the same file) are currently resolved by "keep remote" — the server always wins, local is backed up. This loses client changes silently. We want actual three-way merge using `merge3`, with diff3 conflict markers when automatic merge fails.

**Design decisions (user-approved):**
- Server's `content/` dir is a git repo; every file change creates a commit (git is independent of sync)
- Client stores the commit hash from its last sync — this is the merge base
- Merge happens **server-side** during `sync_commit`
- Clean merges → write merged result; unresolved → return diff3 markers to client
- Delete/modify conflicts → keep the modified version
- No base available → fall back to keep-remote

## Step 1: Create `backend/services/git_service.py`

New file with a `GitService` class wrapping git CLI via `subprocess.run`:

- `__init__(self, content_dir: Path)` — stores path
- `_run(self, *args, check, capture_output)` — runs `git <args>` in content_dir
- `init_repo(self)` — `git init` if `.git/` doesn't exist, configure user, initial commit
- `commit_all(self, message: str) -> str | None` — `git add -A`, check if anything staged, commit; return commit hash or None
- `head_commit(self) -> str` — `git rev-parse HEAD`
- `commit_exists(self, commit_hash: str) -> bool` — `git cat-file -t <hash>`
- `show_file_at_commit(self, commit_hash: str, file_path: str) -> str | None` — `git show <hash>:<path>`, None if not found

All methods synchronous (git is fast for small repos). No new dependencies — uses `subprocess` + git CLI.

Also add `git` to `Dockerfile` line 14: `pandoc curl` → `pandoc curl git`.

## Step 2: Wire GitService into App Startup and Dependencies

**`backend/main.py`** — in `lifespan()`, after creating ContentManager:
```python
from backend.services.git_service import GitService
git_service = GitService(content_dir=settings.content_dir)
git_service.init_repo()
app.state.git_service = git_service
```

**`backend/api/deps.py`** — new dependency:
```python
def get_git_service(request: Request) -> GitService:
    from backend.services.git_service import GitService
    gs: GitService = request.app.state.git_service
    return gs
```

**`backend/services/sync_service.py`** — in `scan_content_files()`, skip `.git` dir:
```python
dirs[:] = [d for d in dirs if not d.startswith(".")]
```
Same filter in `cli/sync_client.py` `scan_local_files()`.

**`tests/test_api/test_api_integration.py`** — in `client` fixture, after creating ContentManager:
```python
from backend.services.git_service import GitService
git_service = GitService(content_dir=app_settings.content_dir)
git_service.init_repo()
app.state.git_service = git_service
```

**`tests/conftest.py`** — add `git_service` fixture:
```python
@pytest.fixture
def git_service(tmp_content_dir: Path) -> GitService:
    gs = GitService(tmp_content_dir)
    gs.init_repo()
    return gs
```

## Step 3: Git Commits After File-Modifying Operations

Inject `git_service: Annotated[GitService, Depends(get_git_service)]` into these endpoints and call `git_service.commit_all(message)` after the file write:

- **`backend/api/posts.py`**: `create_post_endpoint`, `update_post_endpoint`, `delete_post_endpoint`
- **`backend/api/labels.py`**: `create_label_endpoint`, `update_label_endpoint`, `delete_label_endpoint`

This ensures HEAD always reflects the server's current state, which is critical for the merge — when the client uploads files during sync, HEAD still has the pre-upload version.

## Step 4: Modify Sync Protocol Schemas

**`backend/api/sync.py`** — schema changes:

`SyncInitRequest`: add `last_sync_commit: str | None = None`

`SyncPlanItem`: add `change_type: str = ""`

`SyncPlanResponse`: add `server_commit: str | None = None`

New `MergeResult` schema:
```python
class MergeResult(BaseModel):
    file_path: str
    status: str  # "merged" or "conflicted"
    content: str | None = None  # diff3 markers for "conflicted"
```

`SyncCommitRequest`: add `conflict_files: list[str] = Field(default_factory=list)`, `last_sync_commit: str | None = None`

`SyncCommitResponse`: add `commit_hash: str`, `merge_results: list[MergeResult] = Field(default_factory=list)`

## Step 5: Server-Side Merge Logic

**`backend/services/sync_service.py`** — new function:

```python
def merge_file(base: str | None, server: str, client: str, file_path: str) -> tuple[str, bool]:
```
- If `base is None` → return `(server, True)` (no base = can't merge)
- Use `Merge3(base_lines, server_lines, client_lines)`
- Check `any(kind == "conflict" for kind, *_ in m.merge_groups())` for conflict detection
- Generate output with `m.merge_lines(name_a="SERVER", name_b="CLIENT", name_base="BASE", base_marker="|||||||")`
- Return `(merged_content, has_conflicts)`

**`backend/api/sync.py`** — modify `sync_init`:
- Inject `git_service`, include `server_commit=git_service.head_commit()` and `change_type=c.change_type` in response

**`backend/api/sync.py`** — modify `sync_commit` (the core change):

After applying deletions, before front matter normalization:

```
pre_upload_head = git_service.head_commit()
can_merge = last_sync_commit is not None and git_service.commit_exists(last_sync_commit)

for each conflict_path in body.conflict_files:
    client_content = read from disk (uploaded by client)
    server_content = git_service.show_file_at_commit(pre_upload_head, path)
    base_content = git_service.show_file_at_commit(last_sync_commit, path) if can_merge

    # Delete/modify: if server_content is None → keep client (on disk). If client file doesn't exist → restore server version.
    # Normal conflict: merge_file(base, server, client)
    #   Clean → write merged to disk
    #   Unresolved → restore server version to disk, return conflict-marker text in MergeResult
```

After all merges: normalize front matter (including cleanly merged posts), then `git_service.commit_all("Sync commit by {username}")`, scan files, update manifest, rebuild cache.

Response includes `commit_hash` and `merge_results`.

## Step 6: Update CLI Client

**`cli/sync_client.py`** changes:

1. `scan_local_files()`: add `dirs[:] = [d for d in dirs if not d.startswith(".")]`

2. `status()`: send `last_sync_commit` from config in init request

3. `sync()` — major rewrite of conflict handling:
   - Upload `to_upload` files (existing)
   - Upload conflict files too (client's version for server-side merge)
   - Download `to_download` files, delete `to_delete_local` files
   - Call commit with `conflict_files`, `last_sync_commit`
   - Handle `merge_results`:
     - `"merged"` → download merged file from server
     - `"conflicted"` → back up local as `.conflict-backup`, write conflict-marker content as main file, warn user
   - Save `commit_hash` to config

4. `push()` / `pull()`: also save `commit_hash` from commit response

## Step 7: Tests

**New: `tests/test_services/test_git_service.py`**
- `TestGitServiceInit`: init creates repo, idempotent, commits existing files
- `TestGitServiceCommit`: returns hash, returns None when clean, stages new/deleted files
- `TestGitServiceShow`: show at commit, show nonexistent, show at old commit, commit_exists

**New: `tests/test_services/test_merge.py`**
- Clean merge (different sections modified)
- Conflict (same line modified → diff3 markers with `<<<<<<< SERVER`, `||||||| BASE`, `=======`, `>>>>>>> CLIENT`)
- No base → returns server content + has_conflicts=True
- Identical changes → clean merge
- One side unchanged → clean merge

**New: `tests/test_services/test_sync_merge_integration.py`**
- Full API flow: create post, sync (get commit hash), both sides edit, upload + commit → verify merge results
- Conflict returns diff3 markers in response
- No base / invalid commit hash → graceful fallback
- Delete/modify conflict keeps modified version
- Cleanly merged posts get front matter normalized

**Modified: `tests/test_sync/test_sync_client.py`**
- Client uploads conflict files
- Client sends last_sync_commit
- Client saves commit_hash
- Client handles merged/conflicted results

## Step 8: Update `docs/ARCHITECTURE.md`

- Tech stack: add `git (CLI)` for content versioning
- Sync protocol diagram: add `last_sync_commit`, `merge_results`, `commit_hash`
- New subsection "Three-Way Merge" documenting the merge flow
- New subsection "Git Content Versioning" documenting that all file changes create commits
- Key Design Decisions: add git-backed content directory rationale
- Infrastructure: note git requirement in Docker

## File Summary

| File | Action |
|------|--------|
| `backend/services/git_service.py` | **NEW** |
| `backend/services/sync_service.py` | Add `merge_file()`, filter `.git` in scan |
| `backend/api/sync.py` | Schema changes, merge in `sync_commit`, `server_commit` in `sync_init` |
| `backend/api/posts.py` | Git commit after create/update/delete |
| `backend/api/labels.py` | Git commit after create/update/delete |
| `backend/api/deps.py` | Add `get_git_service` |
| `backend/main.py` | Init git repo on startup |
| `cli/sync_client.py` | Upload conflicts, handle merge results, persist commit hash |
| `Dockerfile` | Add `git` to apt-get |
| `tests/test_services/test_git_service.py` | **NEW** |
| `tests/test_services/test_merge.py` | **NEW** |
| `tests/test_services/test_sync_merge_integration.py` | **NEW** |
| `tests/test_sync/test_sync_client.py` | Add merge tests |
| `tests/conftest.py` | Add `git_service` fixture |
| `tests/test_api/test_api_integration.py` | Add git_service to client fixture |
| `docs/ARCHITECTURE.md` | Document git versioning + merge |

## Verification

1. `uv run pytest tests/test_services/test_git_service.py -v` — git service works
2. `uv run pytest tests/test_services/test_merge.py -v` — merge logic works
3. `uv run pytest tests/test_services/test_sync_merge_integration.py -v` — full API flow
4. `uv run pytest tests/ -v` — all existing tests still pass
5. `just check` — no type/lint/format errors
