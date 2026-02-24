# ── Bootstrap ───────────────────────────────────────────────────────

# Set up a fresh worktree: deps, env file, and local db directory
setup:
    @echo "── Backend: sync dependencies ──"
    uv sync --extra dev
    @echo "\n── Frontend: install dependencies ──"
    cd frontend && npm install
    @echo "\n── Environment: ensure .env exists ──"
    if [ -f .env ]; then echo ".env already exists (leaving as-is)"; else cp .env.example .env && echo "Created .env from .env.example"; fi
    @echo "\n── Database: ensure local dir exists ──"
    mkdir -p data/db
    @echo "\n✓ Fresh worktree setup complete"

# ── Quality checks ──────────────────────────────────────────────────

mutation_max_children := env("MUTATION_MAX_CHILDREN", "")
mutation_keep_artifacts := env("MUTATION_KEEP_ARTIFACTS", "false")
mutmut_version := "3.4.0"

# Run all static analysis checks (no tests)
check-static: check-backend-static check-frontend-static check-vulture check-semgrep check-trivy
    @echo "\n✓ Static checks passed"

# Run all test suites (pass coverage=true for coverage reports)
test coverage="false":
    just test-backend "{{ coverage }}"
    just test-frontend "{{ coverage }}"
    @echo "\n✓ Tests passed"

# Run full quality gate (static checks first, then tests with coverage enforcement)
check: check-static (test "true")
    @echo "\n✓ All checks passed"

# Run full frontend vulnerability audit (including dev dependencies)
check-audit-full:
    @echo "\n── Frontend: full vulnerability audit (including dev dependencies) ──"
    cd frontend && npm audit --audit-level=high

# Run extra checks not covered by `check`
check-extra: check-audit-full check-codeql
    @echo "\n✓ Extra checks passed"

# ── Mutation testing ────────────────────────────────────────────────

# Targeted backend mutation gate for critical code paths
mutation-backend:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "\n── Backend mutation testing (targeted gate) ──"
    args=()
    if [ "{{ mutation_keep_artifacts }}" = "true" ]; then args+=(--keep-artifacts); fi
    if [ -n "{{ mutation_max_children }}" ]; then args+=(--max-children "{{ mutation_max_children }}"); fi
    if [ "${#args[@]}" -eq 0 ]; then
        uv run --extra dev --with "mutmut=={{ mutmut_version }}" python -m cli.mutation_backend backend
    else
        uv run --extra dev --with "mutmut=={{ mutmut_version }}" python -m cli.mutation_backend backend "${args[@]}"
    fi

# Full backend+cli mutation sweep (nightly/full run)
mutation-backend-full:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "\n── Backend mutation testing (full backend+cli sweep) ──"
    args=()
    if [ "{{ mutation_keep_artifacts }}" = "true" ]; then args+=(--keep-artifacts); fi
    if [ -n "{{ mutation_max_children }}" ]; then args+=(--max-children "{{ mutation_max_children }}"); fi
    if [ "${#args[@]}" -eq 0 ]; then
        uv run --extra dev --with "mutmut=={{ mutmut_version }}" python -m cli.mutation_backend backend-full
    else
        uv run --extra dev --with "mutmut=={{ mutmut_version }}" python -m cli.mutation_backend backend-full "${args[@]}"
    fi

# Targeted frontend mutation gate on high-impact flows
mutation-frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "\n── Frontend mutation testing (targeted gate) ──"
    trap 'rm -rf frontend/.stryker-tmp/frontend' EXIT
    cd frontend && npm run mutation

# Full frontend mutation sweep (nightly/full run)
mutation-frontend-full:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "\n── Frontend mutation testing (full sweep) ──"
    trap 'rm -rf frontend/.stryker-tmp/frontend-full' EXIT
    cd frontend && npm run mutation:full

# Recommended PR mutation gate
mutation: mutation-backend mutation-frontend
    @echo "\n✓ Mutation gate passed"

# Comprehensive nightly mutation gate
mutation-full: mutation-backend mutation-backend-full mutation-frontend-full
    @echo "\n✓ Full mutation gate passed"

# Backend static checks: mypy, pyright, deptry, import-linter, ruff, pip-audit
check-backend-static:
    @echo "── Backend: type checking ──"
    uv run mypy backend/ cli/ tests/
    @echo "\n── Backend: pyright type checking ──"
    uv run basedpyright backend/ cli/
    @echo "\n── Backend: dependency hygiene ──"
    uv run deptry .
    @echo "\n── Backend: import contracts ──"
    uv run lint-imports
    @echo "\n── Backend: linting ──"
    uv run ruff check backend/ cli/ tests/
    @echo "\n── Backend: format check ──"
    uv run ruff format --check backend/ cli/ tests/
    @echo "\n── Backend: vulnerability audit ──"
    uv run pip-audit --progress-spinner off

# Backend tests (pass coverage=true for coverage report)
test-backend coverage="false":
    @echo "\n── Backend: tests ──"
    if [ "{{ coverage }}" = "true" ] || [ "{{ coverage }}" = "coverage=true" ]; then \
        uv run pytest tests/ -v --cov=backend --cov=cli --cov-report=term-missing; \
    elif [ "{{ coverage }}" = "false" ] || [ "{{ coverage }}" = "coverage=false" ]; then \
        uv run pytest tests/ -v; \
    else \
        echo "Invalid coverage option '{{ coverage }}' (use coverage=true|false)" >&2; \
        exit 1; \
    fi

# Backend full gate (static + tests)
check-backend: check-backend-static test-backend

# Frontend static checks: tsc, eslint, dependency-cruiser, knip, npm audit
check-frontend-static:
    @echo "── Frontend: type checking ──"
    cd frontend && npm run typecheck
    @echo "\n── Frontend: linting ──"
    cd frontend && npm run lint
    @echo "\n── Frontend: dependency graph checks ──"
    cd frontend && npm run lint:deps
    @echo "\n── Frontend: dependency hygiene ──"
    cd frontend && npm run lint:unused
    @echo "\n── Frontend: vulnerability audit ──"
    cd frontend && npm run audit

# Frontend tests (pass coverage=true for coverage report)
test-frontend coverage="false":
    @echo "\n── Frontend: tests ──"
    if [ "{{ coverage }}" = "true" ] || [ "{{ coverage }}" = "coverage=true" ]; then \
        cd frontend && npm run test:coverage; \
    elif [ "{{ coverage }}" = "false" ] || [ "{{ coverage }}" = "coverage=false" ]; then \
        cd frontend && npm test; \
    else \
        echo "Invalid coverage option '{{ coverage }}' (use coverage=true|false)" >&2; \
        exit 1; \
    fi

# Frontend full gate (static + tests)
check-frontend: check-frontend-static test-frontend

# Dead-code analysis (Vulture), scoped to runtime Python code only.
check-vulture:
    @echo "── Runtime dead-code analysis (Vulture) ──"
    uv run vulture backend cli --exclude "backend/migrations" --min-confidence 80

# Runtime security-focused static analysis (Semgrep)
check-semgrep:
    @echo "── Runtime static security analysis (Semgrep) ──"
    uv run semgrep scan \
        --config p/ci \
        --config p/security-audit \
        --config p/secrets \
        --config p/owasp-top-ten \
        --config p/python \
        --config p/typescript \
        --config p/dockerfile \
        --config p/docker-compose \
        --config p/supply-chain \
        --config p/trailofbits \
        --config .semgrep.yml \
        --exclude-rule typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml \
        --error \
        --quiet \
        backend/ cli/ frontend/src/ Dockerfile docker-compose.yml \
        --exclude tests \
        --exclude "frontend/src/**/__tests__" \
        --exclude "frontend/src/**/*.test.ts" \
        --exclude "frontend/src/**/*.test.tsx"

# Trivy security scans.
check-trivy:
    @echo "\n── Security scan (Trivy: all scanners/configured severities) ──"
    trivy fs \
        --scanners vuln,misconfig,secret,license \
        --exit-code 1 \
        .

# ── CodeQL ────────────────────────────────────────────────────────

# Create CodeQL databases for Python and JavaScript/TypeScript
setup-codeql:
    mkdir -p codeql-db
    @echo "── CodeQL: creating Python database ──"
    codeql database create codeql-db/python --language=python --source-root=. --overwrite
    @echo "\n── CodeQL: creating JavaScript database ──"
    codeql database create codeql-db/javascript --language=javascript --source-root=. --overwrite --command="cd frontend && npm run build"
    @echo "\n✓ CodeQL databases created in codeql-db/"

# Analyze CodeQL databases (security + quality suite)
codeql:
    @echo "── CodeQL: analyzing Python database ──"
    codeql database analyze codeql-db/python \
        codeql/python-queries:codeql-suites/python-security-and-quality.qls \
        --format=sarifv2.1.0 --output=codeql-db/python-results.sarif
    @echo "\n── CodeQL: analyzing JavaScript database ──"
    codeql database analyze codeql-db/javascript \
        codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls \
        --format=sarifv2.1.0 --output=codeql-db/javascript-results.sarif
    @echo "\n✓ CodeQL analysis complete — results in codeql-db/*.sarif"

# Rebuild CodeQL databases and analyze
check-codeql: setup-codeql codeql

# ── Build ─────────────────────────────────────────────────────────

# Create a full production build (frontend + backend dependency sync)
build:
    @echo "── Frontend: install dependencies ──"
    cd frontend && npm ci
    @echo "\n── Frontend: build ──"
    cd frontend && npm run build
    @echo "\n── Backend: sync dependencies ──"
    uv sync
    @echo "\n✓ Production build complete (frontend/dist/)"

# Build standalone CLI executable for the current platform
build-cli:
    uv run pyinstaller \
        --onefile \
        --name agblogger-sync \
        --strip \
        --distpath dist/cli \
        --workpath build/cli \
        --specpath build/cli \
        --clean \
        --noconfirm \
        --exclude-module tkinter \
        --exclude-module test \
        --exclude-module unittest \
        --exclude-module pydoc \
        --exclude-module multiprocessing \
        --exclude-module sqlite3 \
        cli/sync_client.py

# ── Deployment ──────────────────────────────────────────────

deploy:
    uv run agblogger-deploy

# ── Development server ──────────────────────────────────────────────

backend_port := "8000"
frontend_port := "5173"
localdir := justfile_directory() / ".local"
pidfile := localdir / "dev.pid"

# Start backend and frontend in the background (override ports: just start backend_port=9000 frontend_port=9173)
start:
    #!/usr/bin/env bash
    set -euo pipefail
    is_port_in_use() {
        lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
    }

    validate_port() {
        local port="$1"
        if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
            echo "Invalid TCP port: $port (must be 1-65535)" >&2
            exit 1
        fi
    }

    find_free_port() {
        local candidate="$1"
        local blocked="${2:-}"
        while [ "$candidate" -le 65535 ]; do
            if [ -n "$blocked" ] && [ "$candidate" = "$blocked" ]; then
                candidate=$((candidate + 1))
                continue
            fi
            if ! is_port_in_use "$candidate"; then
                echo "$candidate"
                return 0
            fi
            candidate=$((candidate + 1))
        done
        echo "no free TCP port found in range" >&2
        exit 1
    }

    requested_backend_port="{{ backend_port }}"
    requested_frontend_port="{{ frontend_port }}"
    validate_port "$requested_backend_port"
    validate_port "$requested_frontend_port"
    selected_backend_port="$(find_free_port "$requested_backend_port")"
    selected_frontend_port="$(find_free_port "$requested_frontend_port" "$selected_backend_port")"

    mkdir -p "{{ localdir }}"
    if [ -f "{{ pidfile }}" ] && kill -0 "$(cat "{{ pidfile }}")" 2>/dev/null; then
        echo "Dev server is already running (PID $(cat "{{ pidfile }}"))"
        exit 1
    fi
    if [ "$selected_backend_port" != "$requested_backend_port" ]; then
        echo "Backend port :$requested_backend_port unavailable, using :$selected_backend_port"
    fi
    if [ "$selected_frontend_port" != "$requested_frontend_port" ]; then
        echo "Frontend port :$requested_frontend_port unavailable, using :$selected_frontend_port"
    fi
    (
        trap 'kill 0' EXIT
        uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port "$selected_backend_port" &
        cd frontend && AGBLOGGER_BACKEND_PORT="$selected_backend_port" npm run dev -- --port "$selected_frontend_port" &
        wait
    ) &
    echo "$!" > "{{ pidfile }}"
    echo "$selected_backend_port" > "{{ localdir }}/backend.port"
    echo "$selected_frontend_port" > "{{ localdir }}/frontend.port"
    echo "Dev server started (PID $!) — backend :$selected_backend_port, frontend :$selected_frontend_port"

# Stop the running dev server
stop:
    #!/usr/bin/env bash
    if [ ! -f "{{ pidfile }}" ]; then
        echo "No dev server pidfile found"
        exit 1
    fi
    pid=$(cat "{{ pidfile }}")
    if kill -0 "$pid" 2>/dev/null; then
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null
        echo "Dev server stopped (PID $pid)"
    else
        echo "Dev server was not running (stale pidfile)"
    fi
    rm -f "{{ pidfile }}" "{{ localdir }}/backend.port" "{{ localdir }}/frontend.port"

# Check if the dev server is healthy (backend API responds, frontend serves pages)
health:
    #!/usr/bin/env bash
    set -euo pipefail
    # Read actual ports from state files written by `start`, fall back to defaults
    if [ -f "{{ localdir }}/backend.port" ]; then
        bp=$(cat "{{ localdir }}/backend.port")
    else
        bp="{{ backend_port }}"
    fi
    if [ -f "{{ localdir }}/frontend.port" ]; then
        fp=$(cat "{{ localdir }}/frontend.port")
    else
        fp="{{ frontend_port }}"
    fi
    ok=true
    printf "Backend  (:%s): " "$bp"
    if curl -sf "http://localhost:$bp/api/health" >/dev/null 2>&1; then
        echo "✓ healthy"
    else
        echo "✗ unreachable"
        ok=false
    fi
    printf "Frontend (:%s): " "$fp"
    if curl -sf "http://localhost:$fp/" >/dev/null 2>&1; then
        echo "✓ healthy"
    else
        echo "✗ unreachable"
        ok=false
    fi
    if [ "$ok" = false ]; then
        echo "Run 'just start' to start the dev server."
        exit 1
    fi

# Start backend and frontend in the foreground (Ctrl-C to stop). Do not use unless you're human.
syncrun:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port {{ backend_port }} &
    cd frontend && npm run dev -- --port {{ frontend_port }} &
    wait

# ── Developer commands (do not use unless you're human) ──────────────────────────────────────────

cloc:
    @echo "********************************************************************************"
    @echo "                              Source LOC count"
    @echo "********************************************************************************"
    @echo
    cloc --exclude-dir=__tests__ backend/ frontend/src/ cli/
    @echo
    @echo
    @echo "********************************************************************************"
    @echo "                              Tests LOC count"
    @echo "********************************************************************************"
    @echo
    cloc tests/ $(find frontend/src -type d -name __tests__)
