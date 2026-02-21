# Static Analysis Run By `just check-static`

`just check-static` runs these targets:

- `check-backend-static`
- `check-frontend-static`
- `check-semgrep`
- `check-vulture`

All checks are fail-fast and CI-blocking.

## Backend (`check-backend-static`)

- `mypy backend/ cli/ tests/`
  - Purpose: strict Python type checking.
  - Scope: backend, CLI, tests.
- `basedpyright backend/ cli/`
  - Purpose: second Python type-checker pass to catch issues mypy may miss.
  - Scope: backend, CLI runtime code.
- `deptry .`
  - Purpose: dependency declaration hygiene (missing/unused/misplaced deps).
  - Scope: Python project dependency graph.
- `lint-imports`
  - Purpose: architecture import-boundary enforcement.
  - Scope: Python module dependency contracts.
- `ruff check backend/ cli/ tests/`
  - Purpose: linting (correctness, style, security ruleset, simplifications).
  - Scope: backend, CLI, tests.
- `ruff format --check backend/ cli/ tests/`
  - Purpose: format compliance gate.
  - Scope: backend, CLI, tests.
- `pip-audit --progress-spinner off`
  - Purpose: known-vulnerability scan of Python dependencies.
  - Scope: installed dependency set.

## Frontend (`check-frontend-static`)

- `npm run typecheck` (`tsc -b --noEmit`)
  - Purpose: TypeScript type checking.
  - Scope: frontend source.
- `npm run lint` (`eslint .`)
  - Purpose: linting for TS/React correctness and code quality.
  - Scope: frontend source.
- `npm run lint:deps` (`dependency-cruiser --config .dependency-cruiser.cjs src`)
  - Purpose: dependency graph and module-boundary checks.
  - Scope: `frontend/src`.
- `npm run lint:unused` (`knip ...`)
  - Purpose: unused/unlisted/unresolved dependency checks.
  - Scope: frontend project + dependency declarations.
- `npm run audit` (`npm audit --audit-level=high --omit=dev`)
  - Purpose: known-vulnerability scan of production npm dependencies.
  - Scope: frontend production dependency tree.

## Runtime Security Static Analysis (`check-semgrep`)

- `semgrep scan` with:
  - `p/ci`
  - `p/security-audit`
  - `p/secrets`
  - `p/python`
  - `p/typescript`
  - `p/dockerfile`
  - `p/docker-compose`
  - `p/supply-chain`
  - `p/trailofbits`
  - `.semgrep.yml` (local project rules)
- Purpose: SAST and security-pattern detection.
- Scope: `backend/`, `cli/`, `frontend/src/`, `Dockerfile`, `docker-compose.yml` (tests excluded).

## Dead-Code Analysis (`check-vulture`)

- `vulture backend cli --exclude "backend/migrations" --min-confidence 80`
- Purpose: detect likely dead/unused Python code in runtime modules.
- Scope: backend and CLI runtime code.

## Related Test Gates

Tests are intentionally split out from static analysis:

- `just test` runs both test suites (`test-backend`, `test-frontend`)
- `just check` runs `just check-static` first, then `just test`

This keeps static analysis and runtime verification available separately while preserving a single full gate.
