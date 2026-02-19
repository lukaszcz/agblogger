# AgBlogger

A markdown-first blogging platform where markdown files with YAML front matter are the source of truth. A lightweight SQLite database serves as a cache for search/filtering and stores authentication data. Configuration lives in TOML files. A bidirectional sync engine keeps a local directory and the server in lockstep.

## Features

- **Markdown-first** — Pandoc rendering with KaTeX math, syntax highlighting, and custom Lua filters (callouts, tabsets, video embeds)
- **Label DAG** — Hierarchical labels forming a directed acyclic graph with interactive visualization
- **Bidirectional sync** — SHA-256 hash-based sync with three-way merge and conflict resolution
- **Cross-posting** — Publish to Bluesky, Mastodon, X (Twitter), LinkedIn, and Facebook
- **Full-text search** — SQLite FTS5 index over post content and metadata
- **Hardened authentication** — HttpOnly cookie sessions for web, invite-based registration, PATs for CLI/API

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
- [just](https://just.systems/) (command runner)
- Docker & Docker Compose (for containerized deployment)

## Quick Start

```bash
# Install backend dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy and edit environment config
cp .env.example .env

# Start both backend and frontend dev servers in the background
just start

# Or with custom ports (useful when running multiple worktrees)
just start backend_port=9000 frontend_port=9173

# Stop the dev server
just stop
```

This starts the backend at http://localhost:8000 and the frontend at http://localhost:5173 (proxying API calls to the backend). API docs are at http://localhost:8000/docs.

Default credentials: `admin` / `admin` (change via `.env`).
Self-registration is disabled by default; create invite codes from the admin account.

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

### Type Checking, Linting & Formatting

```bash
# Run all checks (backend + frontend)
just check

# Backend only (mypy, ruff check, ruff format --check)
just check-backend

# Frontend only (tsc, eslint)
just check-frontend
```

## Sync Client

The CLI sync client keeps a local content directory in sync with the server using SHA-256 hash-based three-way merge.

```bash
# Initialize a local directory for syncing
python cli/sync_client.py --dir ./my-blog --server https://your-server.com init

# Preview what would change
python cli/sync_client.py --dir ./my-blog status

# Push local changes to server
python cli/sync_client.py --dir ./my-blog push

# Pull server changes to local
python cli/sync_client.py --dir ./my-blog pull

# Full bidirectional sync
python cli/sync_client.py --dir ./my-blog sync
```

Authentication supports either username/password login or a personal access token (`--pat`). Conflicts are resolved by keeping the server version; the local copy is saved as a `.conflict-backup` file.

## Deployment

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with production values:

```
SECRET_KEY=<long-random-string>
ADMIN_USERNAME=<your-admin-username>
ADMIN_PASSWORD=<a-strong-password>
DEBUG=false
```

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 2. Build and start the container

```bash
docker compose up -d --build
```

The multi-stage Dockerfile builds the frontend with Node.js, then packages everything into a Python slim image with Pandoc. The container runs as a non-root user and exposes port 8000.

### 3. Admin user creation

On first startup the server automatically creates an admin account using `ADMIN_USERNAME` and `ADMIN_PASSWORD` from the environment. The password is bcrypt-hashed before storage — the plaintext value is never persisted.

The admin user is only created if no user with that username already exists. To reset the admin password, delete the database volume and restart:

```bash
docker compose down -v   # removes the db volume
docker compose up -d     # recreates admin from .env
```

### 4. Log in

Visit `http://<your-server>:8000/login` and sign in with the admin credentials from `.env`.

Self-registration is disabled by default. To add more users, create invite codes from the admin account — other users can then register at `/login` with an invite code.

### 5. Add HTTPS with Caddy (recommended)

Edit `Caddyfile` and replace `myblog.example.com` with your domain, then add a Caddy service to `docker-compose.yml`:

```yaml
services:
  agblogger:
    # ... existing config ...

  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
    depends_on:
      - agblogger

volumes:
  agblogger-db:
  caddy-data:
```

Caddy automatically obtains Let's Encrypt certificates and reverse-proxies to the backend.

### Data volumes

| Volume | Path in container | Purpose |
|--------|-------------------|---------|
| `./content` | `/data/content` | Blog content — markdown, TOML, assets (bind mount) |
| `agblogger-db` | `/data/db` | SQLite database (named volume) |

The `content/` directory is the source of truth. Back it up to preserve your blog. The database is fully regenerable from content files on startup (auth data like user accounts is the exception).

### Environment variables

Key variables (see `.env.example` for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Bootstrap admin username |
| `ADMIN_PASSWORD` | `admin` | Bootstrap admin password (hashed on storage) |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/db/agblogger.db` | Database connection string |
| `CONTENT_DIR` | `./content` | Blog content directory |
| `AUTH_SELF_REGISTRATION` | `false` | Enable/disable open registration |
| `AUTH_INVITES_ENABLED` | `true` | Allow invite-code registration |
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
created_at: 2026-02-02 22:21:29.975359+00
modified_at: 2026-02-02 22:21:35.000000+00
author: Admin
labels: ["#swe"]
---
# Hello World

Post content here with **markdown**, $\LaTeX$ math, and `code blocks`.
```

Site configuration lives in `content/index.toml` and labels are defined in `content/labels.toml`.
