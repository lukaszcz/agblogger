# ── Quality checks ──────────────────────────────────────────────────

# Run all type checking, linting, format checks, and tests
check: check-backend check-frontend
    @echo "\n✓ All checks passed"

# Backend: mypy, ruff check, ruff format --check, pytest
check-backend:
    @echo "── Backend: type checking ──"
    uv run mypy backend/ cli/
    @echo "\n── Backend: linting ──"
    uv run ruff check backend/ cli/ tests/
    @echo "\n── Backend: format check ──"
    uv run ruff format --check backend/ cli/ tests/
    @echo "\n── Backend: tests ──"
    uv run pytest tests/ -v

# Frontend: tsc, eslint, vitest
check-frontend:
    @echo "── Frontend: type checking ──"
    cd frontend && npm run typecheck
    @echo "\n── Frontend: linting ──"
    cd frontend && npm run lint
    @echo "\n── Frontend: tests ──"
    cd frontend && npm test

# ── Development server ──────────────────────────────────────────────

backend_port := "8000"
frontend_port := "5173"
localdir := justfile_directory() / ".local"
pidfile := localdir / "dev.pid"

# Start backend and frontend in the background (override ports: just start backend_port=9000 frontend_port=9173)
start:
    #!/usr/bin/env bash
    mkdir -p "{{localdir}}"
    if [ -f "{{pidfile}}" ] && kill -0 "$(cat "{{pidfile}}")" 2>/dev/null; then
        echo "Dev server is already running (PID $(cat "{{pidfile}}"))"
        exit 1
    fi
    (
        trap 'kill 0' EXIT
        uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port {{backend_port}} &
        cd frontend && npm run dev -- --port {{frontend_port}} &
        wait
    ) &
    echo "$!" > "{{pidfile}}"
    echo "Dev server started (PID $!) — backend :{{backend_port}}, frontend :{{frontend_port}}"

# Stop the running dev server
stop:
    #!/usr/bin/env bash
    if [ ! -f "{{pidfile}}" ]; then
        echo "No dev server pidfile found"
        exit 1
    fi
    pid=$(cat "{{pidfile}}")
    if kill -0 "$pid" 2>/dev/null; then
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null
        echo "Dev server stopped (PID $pid)"
    else
        echo "Dev server was not running (stale pidfile)"
    fi
    rm -f "{{pidfile}}"
