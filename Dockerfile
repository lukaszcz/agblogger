# ── Stage 1: Build frontend ──────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production image ───────────────────────────────────────
FROM python:3.13-slim

# Install pandoc
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy backend code
COPY backend/ ./backend/
COPY cli/ ./cli/

# Copy Alembic config and migrations
COPY alembic.ini ./
COPY backend/migrations/ ./backend/migrations/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Content and database volumes
VOLUME /data/content
VOLUME /data/db

ENV CONTENT_DIR=/data/content
ENV DATABASE_URL=sqlite+aiosqlite:///data/db/agblogger.db
ENV FRONTEND_DIR=/app/frontend/dist

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
