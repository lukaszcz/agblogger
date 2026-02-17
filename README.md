# AgBlogger

A markdown-first blogging platform where markdown files with YAML front matter are the source of truth. A lightweight SQLite database serves as a cache for search/filtering and stores authentication data. Configuration lives in TOML files. A bidirectional sync engine keeps a local directory and the server in lockstep.

## Features

- **Markdown-first** — Pandoc rendering with KaTeX math, syntax highlighting, and custom Lua filters (callouts, tabsets, video embeds)
- **Label DAG** — Hierarchical labels forming a directed acyclic graph with interactive visualization
- **Bidirectional sync** — SHA-256 hash-based sync with three-way merge and conflict resolution
- **Cross-posting** — Publish to Bluesky, Mastodon, X (Twitter), LinkedIn, and Facebook
- **Full-text search** — SQLite FTS5 index over post content and metadata
- **JWT authentication** — Access and refresh tokens with role-based authorization

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.0, SQLite (WAL mode), Pandoc |
| Frontend | React 19, TypeScript, Vite, TailwindCSS 4, Zustand, React Flow |
| Infrastructure | Docker, Caddy, uv |

## Prerequisites

- Python 3.13+
- Node.js 20+
- [Pandoc](https://pandoc.org/installing.html)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker & Docker Compose (for containerized deployment)

## Quick Start

```bash
# Install backend dependencies
uv sync

# Install frontend dependencies and build
cd frontend && npm install && npm run build && cd ..

# Copy and edit environment config
cp .env.example .env

# Run database migrations and start the server
source .venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The app is available at http://localhost:8000. API docs are at http://localhost:8000/docs.

Default credentials: `admin` / `admin` (change via `.env`).

### Frontend Development

For hot-reload during frontend work, run the Vite dev server in a separate terminal:

```bash
cd frontend
npm run dev
```

This starts http://localhost:5173 and proxies API calls to the backend.

## Testing

### Backend

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

93 backend tests cover API integration, services, sync, rendering, labels, and datetime handling.

### Frontend

```bash
cd frontend
npm test
```

### Type Checking & Linting

```bash
# Python
mypy backend/
ruff check backend/

# TypeScript
cd frontend
npm run typecheck
npm run lint
```

## Deployment

### Docker (recommended)

```bash
# Build and start
docker-compose up -d
```

The multi-stage Dockerfile builds the frontend with Node.js, then packages everything into a Python slim image with Pandoc. The container runs as a non-root user and exposes port 8000.

Volumes:
- `/data/content` — blog content (markdown, TOML, assets)
- `/data/db` — SQLite database

### With HTTPS via Caddy

Update the domain in `Caddyfile`, then:

```bash
docker-compose up -d
```

Caddy automatically obtains Let's Encrypt certificates and reverse-proxies to the backend.

### Environment Variables

Key variables (see `.env.example` for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/db/agblogger.db` | Database connection string |
| `CONTENT_DIR` | `./content` | Blog content directory |
| `ADMIN_USERNAME` | `admin` | Bootstrap admin username |
| `ADMIN_PASSWORD` | `admin` | Bootstrap admin password |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

Cross-posting credentials (Bluesky, Mastodon, X, LinkedIn, Facebook) are configured through additional environment variables documented in `.env.example`.

### Backup

```bash
# Content (the source of truth)
rsync -av /data/content/ /backups/content/

# Database (cache + auth data)
cp /data/db/agblogger.db /backups/agblogger.db
```

## Project Structure

```
backend/          Python FastAPI application (API, services, models, sync engine)
frontend/         React + TypeScript SPA (Vite, TailwindCSS)
cli/              Sync client CLI (typer)
tests/            pytest test suite
content/          Sample blog content (markdown, TOML, assets)
docs/             Design documentation
```

## Content Authoring

Posts are markdown files with YAML front matter in the `content/posts/` directory:

```markdown
---
title: My Post
date: 2026-02-17
labels: [programming, python]
status: published
---

Post content here with **markdown**, $\LaTeX$ math, and ```code blocks```.
```

Site configuration lives in `content/index.toml` and labels are defined in `content/labels.toml`.
