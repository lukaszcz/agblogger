# Static Analysis Run By `just check-static`

`just check-static` runs these targets:

- `check-backend-static`
- `check-frontend-static`
- `check-semgrep`
- `check-vulture`
- `check-trivy`

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

## Trivy Security Scan (`check-trivy`)

- `trivy config --exit-code 1 --severity MEDIUM,HIGH,CRITICAL docker-compose.yml`
  - Purpose: detect medium/high/critical IaC misconfigurations in Compose.
  - Scope: `docker-compose.yml`.
- `trivy config --exit-code 1 --severity MEDIUM,HIGH,CRITICAL Dockerfile`
  - Purpose: detect medium/high/critical container build misconfigurations.
  - Scope: `Dockerfile`.
- `trivy fs --scanners secret --detection-priority precise --exit-code 1 --severity MEDIUM,HIGH,CRITICAL backend`
  - Purpose: detect medium/high/critical secrets with lower false-positive bias.
  - Scope: backend source directory.
- `trivy fs --scanners secret --detection-priority precise --exit-code 1 --severity MEDIUM,HIGH,CRITICAL cli`
  - Purpose: detect medium/high/critical secrets with lower false-positive bias.
  - Scope: CLI source directory.
- `trivy fs --scanners secret --detection-priority precise --exit-code 1 --severity MEDIUM,HIGH,CRITICAL frontend/src`
  - Purpose: detect medium/high/critical secrets with lower false-positive bias.
  - Scope: frontend source directory.

## Related Test Gates

Tests are intentionally split out from static analysis:

- `just test` runs both test suites (`test-backend`, `test-frontend`)
  - Optional coverage: `just test coverage=true`
- `just test-backend` supports optional coverage: `just test-backend coverage=true`
- `just test-frontend` supports optional coverage: `just test-frontend coverage=true`
- `just check` runs `just check-static` first, then `just test`

This keeps static analysis and runtime verification available separately while preserving a single full gate.

## Extra Security Gates

These are intentionally separate from `just check` and `just check-static`:

- `just check-audit-full`
  - Runs `npm audit --audit-level=high` in `frontend/`.
  - Includes development dependencies (unlike `npm run audit`, which uses `--omit=dev`).
- `just check-codeql`
  - Rebuilds CodeQL databases and runs CodeQL analysis for Python and JavaScript.
- `just check-extra`
  - Runs only extra checks not covered by `just check`: `check-audit-full` + `check-codeql`.
