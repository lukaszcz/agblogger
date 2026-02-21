# ── Quality checks ──────────────────────────────────────────────────

# Run all type checking, linting, format checks, and tests
check: check-backend check-frontend check-semgrep check-vulture
    @echo "\n✓ All checks passed"

# Backend: mypy, ruff check, ruff format --check, pytest
check-backend:
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
    @echo "\n── Backend: tests ──"
    uv run pytest tests/ -v

# Frontend: tsc, eslint, vitest
check-frontend:
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
    @echo "\n── Frontend: tests ──"
    cd frontend && npm test

# Runtime security-focused static analysis (Semgrep)
check-semgrep:
    @echo "── Runtime static security analysis (Semgrep) ──"
    uv run semgrep scan \
        --config p/ci \
        --config p/security-audit \
        --config p/secrets \
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

# Dead-code analysis (Vulture), scoped to runtime Python code only.
check-vulture:
    @echo "── Runtime dead-code analysis (Vulture) ──"
    uv run vulture backend cli --exclude "backend/migrations" --min-confidence 80

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

# ── Development server ──────────────────────────────────────────────

backend_port := "8000"
frontend_port := "5173"
localdir := justfile_directory() / ".local"
pidfile := localdir / "dev.pid"

# Start backend and frontend in the background (override ports: just start backend_port=9000 frontend_port=9173)
start:
    #!/usr/bin/env bash
    mkdir -p "{{ localdir }}"
    if [ -f "{{ pidfile }}" ] && kill -0 "$(cat "{{ pidfile }}")" 2>/dev/null; then
        echo "Dev server is already running (PID $(cat "{{ pidfile }}"))"
        exit 1
    fi
    (
        trap 'kill 0' EXIT
        uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port {{ backend_port }} &
        cd frontend && npm run dev -- --port {{ frontend_port }} &
        wait
    ) &
    echo "$!" > "{{ pidfile }}"
    echo "Dev server started (PID $!) — backend :{{ backend_port }}, frontend :{{ frontend_port }}"

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
    rm -f "{{ pidfile }}"

# Start backend and frontend in the foreground (Ctrl-C to stop). Do not use unless you're human.
syncrun:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port {{ backend_port }} &
    cd frontend && npm run dev -- --port {{ frontend_port }} &
    wait
