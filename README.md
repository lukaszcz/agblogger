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

### Standalone Executable

Build a single-file executable that runs without a Python installation:

```bash
just build-cli
```

This produces `dist/cli/agblogger-sync` (or `agblogger-sync.exe` on Windows). The binary bundles the Python interpreter and all dependencies. Distribute it to users as-is:

```bash
./agblogger-sync --dir ./my-blog --server https://your-server.com init
```

The build targets the current platform — cross-compile by running `just build-cli` on each target OS.

## Deployment

### 1. Run the interactive deploy script

```bash
uv run agblogger-deploy
```

The script asks for all required production settings:

- `SECRET_KEY` (or auto-generate)
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- public hostnames/IPs for your blog (`TRUSTED_HOSTS`)
- `TRUSTED_PROXY_IPS` (optional)
- host port mapping (`HOST_PORT`, only used when Caddy is disabled)
- whether to set up HTTPS with Caddy (recommended)

Caddy is a web server and reverse proxy. It sits in front of AgBlogger, handles HTTPS certificates automatically, and forwards traffic to the app container.

If you enable Caddy, the script also generates:

- `Caddyfile.production`
- `docker-compose.caddy-public.yml` (only when you choose public Internet exposure)

If you disable Caddy, the script generates:

- `docker-compose.nocaddy.yml`

### 2. Manage the deployed server

After deployment, use the exact commands printed by the script.

```bash
docker compose --env-file .env.production up -d   # start (Caddy, localhost-only)
docker compose --env-file .env.production down    # stop (Caddy, localhost-only)
docker compose --env-file .env.production ps      # status (Caddy, localhost-only)
```

With Caddy and public Internet exposure enabled, commands include the generated public override:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.caddy-public.yml up -d
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.caddy-public.yml down
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.caddy-public.yml ps
```

With Caddy disabled, commands use the generated no-Caddy compose file:

```bash
docker compose --env-file .env.production -f docker-compose.nocaddy.yml up -d
docker compose --env-file .env.production -f docker-compose.nocaddy.yml down
docker compose --env-file .env.production -f docker-compose.nocaddy.yml ps
```

### 3. Admin user creation

On first startup the server automatically creates an admin account using `ADMIN_USERNAME` and `ADMIN_PASSWORD` from the environment. The password is bcrypt-hashed before storage — the plaintext value is never persisted.

The admin user is only created if no user with that username already exists. To reset the admin password, delete the database volume and restart:

```bash
docker compose --env-file .env.production down -v   # removes the db volume
docker compose --env-file .env.production up -d     # recreates admin from .env.production
```

### 4. Log in

Visit `https://<your-domain>/login` when Caddy is enabled, or `http://<your-server>:<host-port>/login` when Caddy is disabled. Sign in with the admin credentials from `.env.production`.

Self-registration is disabled by default. To add more users, create invite codes from the admin account — other users can then register at `/login` with an invite code.

### 5. HTTPS behavior

If Caddy is enabled, users access the app at `https://<your-domain>/login`.
If Caddy is not enabled, users access the app directly via `http://<your-server>:<host-port>/login`.

### Data volumes

| Volume | Path in container | Purpose |
|--------|-------------------|---------|
| `./content` | `/data/content` | Blog content — markdown, TOML, assets (bind mount) |
| `agblogger-db` | `/data/db` | SQLite database (named volume) |

The `content/` directory is the source of truth. Back it up to preserve your blog. The database is fully regenerable from content files on startup (auth data like user accounts is the exception).

### Environment variables

Key deployment variables used by `.env.production`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | generated by script | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Bootstrap admin username |
| `ADMIN_PASSWORD` | prompt input | Bootstrap admin password (hashed on storage) |
| `TRUSTED_HOSTS` | prompt input | Allowed Host headers in production |
| `TRUSTED_PROXY_IPS` | `[]` | Trusted proxy source IPs |
| `HOST_PORT` | `8000` | Host port mapped to container port 8000 in no-Caddy mode |
| `HOST_BIND_IP` | script-selected | Bind IP for no-Caddy mode |

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
cli/              Sync and deployment CLIs
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
