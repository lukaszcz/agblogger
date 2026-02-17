# ── Quality checks ──────────────────────────────────────────────────

# Run all type checking, linting, and format checks
check: check-backend check-frontend
    @echo "\n✓ All checks passed"

# Backend: mypy, ruff check, ruff format --check
check-backend:
    @echo "── Backend: type checking ──"
    uv run mypy backend/ cli/
    @echo "\n── Backend: linting ──"
    uv run ruff check backend/ cli/ tests/
    @echo "\n── Backend: format check ──"
    uv run ruff format --check backend/ cli/ tests/

# Frontend: tsc, eslint
check-frontend:
    @echo "── Frontend: type checking ──"
    cd frontend && npm run typecheck
    @echo "\n── Frontend: linting ──"
    cd frontend && npm run lint

# ── Development server ──────────────────────────────────────────────

# Start backend (port 8000) and frontend (port 5173) concurrently
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
    cd frontend && npm run dev &
    wait
