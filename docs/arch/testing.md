# Testing

## Backend (pytest)

```
tests/
├── conftest.py                  Fixtures: tmp content dir, settings, DB engine/session
├── test_api/
│   └── test_api_integration.py  Full API tests via httpx AsyncClient + ASGITransport
├── test_services/
│   ├── test_config.py           Settings loading
│   ├── test_content_manager.py  ContentManager operations
│   ├── test_crosspost.py        Cross-posting platforms
│   ├── test_database.py         DB engine creation
│   ├── test_datetime_service.py Date/time parsing
│   ├── test_git_service.py      Git service operations
│   ├── test_git_merge_file.py   git merge-file wrapper tests
│   ├── test_frontmatter_merge.py  Semantic front matter merge tests
│   ├── test_hybrid_merge.py     Hybrid merge (front matter + body) tests
│   ├── test_sync_service.py     Sync plan computation
│   └── test_sync_merge_integration.py  Full sync merge API flow
├── test_sync/                   CLI sync client tests
├── test_labels/                 Label service tests
└── test_rendering/              Pandoc rendering tests
```

Configuration in `pyproject.toml`: `asyncio_mode = "auto"`, markers for `slow` and `integration`, coverage via `pytest-cov`.

## Frontend (Vitest)

Vitest with jsdom environment, `@testing-library/react`, and `@testing-library/user-event`.

## Mutation Testing

Mutation testing is implemented in three production phases with dedicated `just` targets.

### Backend targeted profile

- Runner: `cli/mutation_backend.py`, profile `backend`
- Goal: strict mutation gate for high-risk backend paths (auth, sync, front matter normalization, slugging, SSRF, rate limiting)
- Command: `just mutation-backend`
- Runtime mode: `mutate_only_covered_lines = false` (full-file mutation for stronger robustness at the cost of runtime)
- Quality enforcement:
  - minimum strict mutation score (`killed / (total - skipped - not_checked)`)
  - explicit budgets for `survived`, `timeout`, `suspicious`, `no tests`, `segfault`, and interrupted mutants
- Report: `reports/mutation/backend.json`
- Tunables:
  - `MUTATION_MAX_CHILDREN=<n>` to cap worker parallelism
  - `MUTATION_KEEP_ARTIFACTS=true` to persist mutmut workspaces in `reports/mutation/artifacts/`
  - when artifacts are persisted, clean them (`rm -rf reports/mutation/artifacts`) before running `just check` to avoid static-analysis noise from instrumented files

### Backend full profile

- Runner: `cli/mutation_backend.py`, profile `backend-full`
- Goal: broad backend + CLI mutation sweep across stable, high-signal suites
- Test selection: backend service/CLI/sync/labels/rendering suites (API-heavy suites are handled by the targeted backend profile and excluded here for mutmut stats stability)
- Uses the same full-file mutation mode (`mutate_only_covered_lines = false`)
- Excludes `tests/test_services/test_sync_merge_integration.py` from mutation runs due mutmut instrumentation instability in that flow
- Excludes `tests/test_rendering/test_renderer_no_dead_code.py` from mutation runs because mutmut-generated symbols intentionally violate that module’s dead-code/introspection assertions
- Excludes broad API integration/security modules from full-profile stats collection because mutmut stats-mode instrumentation causes repeated false failures in shared ASGI fixture flows
- Deselects introspection-sensitive coroutine-shape assertions (for example `TestIsSafeUrlAsync::test_is_safe_url_is_async`) that are invalidated by mutmut trampoline wrapping in `stats` mode
- Excludes mutation of `backend/main.py` to avoid mutmut stats-stage bootstrap instability in full-suite runs
- Command: `just mutation-backend-full`
- Report: `reports/mutation/backend-full.json`

### Frontend mutation profiles

- Engine: StrykerJS with Vitest runner
- Tooling is pinned in `frontend/package.json` devDependencies (`@stryker-mutator/*` v`9.3.0`) and run via local `stryker` binaries
- Targeted config: `frontend/stryker.mutation.config.mjs`
- Broad full-run config: `frontend/stryker.mutation-full.config.mjs`
- Commands:
  - `just mutation-frontend`
  - `just mutation-frontend-full`
- `just` targets auto-clean `.stryker-tmp/frontend*` sandboxes on exit (success or failure) to keep frontend static checks clean after mutation runs
- Reports:
  - `frontend/reports/mutation/frontend.html`
  - `frontend/reports/mutation/frontend.json`
  - `frontend/reports/mutation/frontend-full.html`
  - `frontend/reports/mutation/frontend-full.json`

### Composite mutation gates

- PR gate: `just mutation` (backend targeted + frontend targeted)
- Nightly gate: `just mutation-full` (backend targeted + backend full + frontend full)
