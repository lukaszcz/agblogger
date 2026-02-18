# AgBlogger Architecture

AgBlogger is a self-hosted, markdown-first blogging platform. Markdown files with YAML front matter are the authoritative source of truth for all post content and metadata. The SQLite database is a regenerable cache for search and filtering. Configuration lives in TOML files. A bidirectional sync mechanism keeps a local directory and the server in lockstep.

## Directory Structure

```
agblogger/
├── backend/            Python FastAPI backend
│   ├── api/            Route handlers + dependency injection
│   ├── filesystem/     Markdown/TOML parsing, content management
│   ├── middleware/      SEO meta tag injection
│   ├── models/         SQLAlchemy ORM models
│   ├── pandoc/         Pandoc rendering
│   ├── services/       Business logic layer
│   ├── crosspost/      Cross-posting platform plugins
│   ├── config.py       Pydantic settings (from .env)
│   ├── database.py     Async SQLAlchemy engine
│   └── main.py         Application factory + lifespan
├── frontend/           React 19 + TypeScript SPA
│   └── src/
│       ├── api/        HTTP client (ky) + API functions
│       ├── stores/     Zustand state management
│       ├── pages/      Route-level page components
│       └── components/ Reusable UI components
├── cli/                Sync client CLI
├── tests/              pytest test suite
├── content/            Sample blog content
├── docs/               Project documentation
├── Dockerfile          Multi-stage Docker build
├── docker-compose.yml  Container orchestration
├── Caddyfile           Reverse proxy (HTTPS)
└── pyproject.toml      Python project config
```

## Tech Stack

### Backend

| Component | Technology |
|-----------|------------|
| Framework | FastAPI >=0.115 |
| ASGI server | uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | SQLite via aiosqlite |
| Migrations | Alembic |
| Markdown rendering | Pandoc (via pypandoc) |
| Front matter parsing | python-frontmatter + PyYAML |
| TOML | stdlib tomllib (read) + tomli-w (write) |
| Auth | python-jose (JWT) + bcrypt |
| Validation | Pydantic 2 + pydantic-settings |
| Date/time | pendulum |
| Sync merging | merge3 |
| HTTP client | httpx |
| Cross-posting | atproto, httpx (optional) |

### Frontend

| Component | Technology |
|-----------|------------|
| Framework | React 19 |
| Build tool | Vite 7 |
| Language | TypeScript 5.9 |
| Styling | TailwindCSS 4 |
| Routing | react-router-dom v7 |
| State management | Zustand 5 |
| HTTP client | ky |
| Markdown editor | Plain textarea + server-side Pandoc preview |
| Graph visualization | @xyflow/react + @dagrejs/dagre |
| Math rendering | KaTeX |

### Infrastructure

- Python 3.13+
- Node.js 22 (build stage)
- Pandoc binary
- uv (Python dependency management)
- Docker + Docker Compose
- Caddy (optional HTTPS reverse proxy)

## Core Concepts

### Markdown as Source of Truth

The filesystem is the canonical store for all content. The database is entirely regenerable from the files on disk — it is rebuilt on every server startup via `rebuild_cache()`.

Content lives in the `content/` directory:

```
content/
├── index.toml              Site configuration
├── labels.toml             Label DAG definitions
├── about.md                Top-level page
├── posts/
│   ├── 2026-02-02-hello-world.md
│   └── cooking/
│       └── best-pasta.md   Directory implies #cooking label
└── assets/                 Shared assets
```

Posts use YAML front matter:

```yaml
---
created_at: 2026-02-02 22:21:29.975359+00
modified_at: 2026-02-02 22:21:35.000000+00
author: Admin
labels: ["#swe"]
---
# Post Title

Content here...
```

- **Title** is extracted from the first `# Heading` in the body, falling back to filename derivation.
- **Labels** are referenced as `#label-id` strings.
- **Timestamps** use strict ISO output format; lax input is accepted via pendulum.
- **Directory-based implicit labels**: a post at `posts/cooking/recipe.md` automatically receives the `#cooking` label.

### Label DAG

Labels form a Directed Acyclic Graph where edges point from child to parent (subcategory to supercategory). Labels can have **multiple parents**. They are defined in `content/labels.toml`:

```toml
[labels.cs]
names = ["computer science"]

[labels.swe]
names = ["software engineering", "programming"]
parent = "#cs"

[labels.quantum]
names = ["quantum mechanics"]
parents = ["#math", "#physics"]
```

Single parent uses `parent = "#id"`, multiple parents use `parents = ["#id1", "#id2"]`. The TOML parser accepts both forms; the writer intelligently chooses singular vs plural.

**Cycle enforcement** operates at two levels:
- **Cache rebuild / sync** (batch): DFS with back-edge detection in O(V+E). Cycles in `labels.toml` are automatically broken by dropping edges, with warnings returned in the sync response and logged at startup.
- **API (single-edge additions)**: Recursive CTE checks if the proposed parent is already a descendant of the label, returning 409 on cycle.

Descendant queries use recursive CTEs in SQLite, enabling a "show me all posts in #cs including subcategories" pattern. The graph is visualized and editable in the frontend using React Flow with Dagre auto-layout.

### TOML Configuration

`content/index.toml` defines site-level settings (title, timezone, default author, page navigation). `content/labels.toml` defines the label hierarchy. Both are read at startup and on cache rebuild.

## Backend Architecture

### Application Lifecycle (`backend/main.py`)

The `create_app()` factory:

1. Creates a FastAPI app with a lifespan context manager.
2. Adds GZip and CORS middleware.
3. Registers API routers under `/api/`.
4. Serves the React SPA static files from `frontend/dist/`.

On startup, the lifespan handler:

1. Creates the async SQLAlchemy engine and session factory.
2. Creates all database tables (including the FTS5 virtual table).
3. Initializes the `ContentManager`.
4. Creates the admin user if it doesn't exist.
5. Rebuilds the full database cache from the filesystem.

### Layered Architecture

```
┌─────────────────────────────────────┐
│  API Layer (backend/api/)           │  Route handlers, request/response
├─────────────────────────────────────┤
│  Dependencies (backend/api/deps.py)  │  Auth, DB session, settings injection
├─────────────────────────────────────┤
│  Services (backend/services/)       │  Business logic
├─────────────────────────────────────┤
│  Models (backend/models/)           │  SQLAlchemy ORM
├─────────────────────────────────────┤
│  Filesystem (backend/filesystem/)   │  Markdown/TOML parsing, content I/O
├─────────────────────────────────────┤
│  Pandoc (backend/pandoc/)           │  HTML rendering
└─────────────────────────────────────┘
```

### API Routes

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth` | `/api/auth` | Login, register, refresh tokens, current user |
| `posts` | `/api/posts` | CRUD, search, listing with pagination/filtering, structured editor data |
| `labels` | `/api/labels` | Label CRUD (create, update, delete), listing, graph data, posts by label |
| `pages` | `/api/pages` | Site config, rendered page content |
| `sync` | `/api/sync` | Bidirectional sync protocol |
| `crosspost` | `/api/crosspost` | Social account management, cross-posting |
| `render` | `/api/render` | Server-side Pandoc preview for the editor |
| `health` | `/api/health` | Health check with DB verification |

### Database Models

The database serves as a **cache**, not the source of truth:

- **`PostCache`** — Cached post metadata: file path, title, author, timestamps, draft status, content hash (SHA-256), excerpt, rendered HTML.
- **`PostsFTS`** — SQLite FTS5 virtual table for full-text search over title, excerpt, and content.
- **`LabelCache`** — Label with ID, display names (JSON array), and implicit flag.
- **`LabelParentCache`** — DAG edge table (label_id → parent_id).
- **`PostLabelCache`** — Many-to-many posts to labels with source tracking ("frontmatter" or "directory").
- **`User`** — Username, email, password hash, display name, admin flag.
- **`RefreshToken`** — Hashed refresh token with expiry.
- **`SocialAccount`** — OAuth credentials per user/platform.
- **`CrossPost`** — Cross-posting history log.
- **`SyncManifest`** — File state at last sync: path, content hash, file size, mtime.

### Rendering Pipeline

Pandoc renders markdown to HTML at publish time (during cache rebuild), not per-request. The rendered HTML is stored in `PostCache.rendered_html`.

```
pandoc -f gfm+tex_math_dollars+footnotes+raw_html -t html5
       --katex --highlight-style=pygments --wrap=none
```

Features: GitHub Flavored Markdown (tables, task lists, strikethrough), KaTeX math, syntax highlighting (140+ languages), and heading anchor injection.

Lua filter files exist in `backend/pandoc/filters/` as placeholders for future use (callouts, tabsets, video embeds, local link rewriting) but are not currently wired into the rendering pipeline.

## Authentication and Authorization

### JWT Flow

- **Access tokens**: Short-lived (15 min), HS256 JWT containing `{sub: user_id, username, is_admin}`.
- **Refresh tokens**: Long-lived (7 days), cryptographically random 48-byte strings. Only the SHA-256 hash is stored in the database. Old tokens are revoked on refresh (rotation).
- **Passwords**: bcrypt hashed.

### Roles

| Role | Access |
|------|--------|
| Unauthenticated | Read published posts, labels, pages, search |
| Authenticated | Above + create/edit/delete posts, sync, cross-post |
| Admin | Above + admin-only operations |

Public reads require no authentication. The `get_current_user()` dependency returns `None` for unauthenticated requests.

### Admin Bootstrap

On startup, `ensure_admin_user()` creates the admin user from `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables if no matching user exists.

## Bidirectional Sync

Hash-based, three-way sync inspired by Unison. Both client and server maintain a **sync manifest** mapping `file_path → (SHA-256 hash, mtime, size)`.

### Sync Protocol

```
Client                                   Server
  │                                         │
  │  1. POST /api/sync/init                 │
  │     (client manifest) ──────────────►   │  Compare client manifest
  │                                         │  vs server manifest
  │   ◄──────────────── (sync plan)         │  vs current filesystem
  │                                         │
  │  2. POST /api/sync/upload               │
  │     (changed files) ────────────────►   │  Write files to content/
  │                                         │
  │  3. GET /api/sync/download/{path}       │
  │   ◄──────────────── (file content)      │  Send files to client
  │                                         │
  │  4. POST /api/sync/commit               │
  │     (finalize) ─────────────────────►   │  Update manifest,
  │                                         │  rebuild cache
```

### Three-Way Conflict Detection

| Client vs Manifest | Server vs Manifest | Action |
|---|---|---|
| Same | Same | No change |
| Changed | Same | Upload to server |
| Same | Changed | Download to client |
| Changed | Changed (different) | Conflict |
| New | Not present | Upload |
| Not present | New | Download |
| Deleted | Same | Delete on server |
| Same | Deleted | Delete on client |

### CLI Sync Client (`cli/sync_client.py`)

A standalone Python script using httpx with subcommands: `init`, `status`, `push`, `pull`, `sync`. Stores config in `.agblogger-sync.json` and the local manifest in `.agblogger-manifest.json`. Conflicts default to "keep remote" with local backups saved as `.conflict-backup`.

## Cross-Posting

### Plugin Architecture

A `CrossPoster` protocol defines the interface:

```python
class CrossPoster(Protocol):
    platform: str
    async def authenticate(self, credentials: dict[str, str]) -> bool: ...
    async def post(self, content: CrossPostContent) -> CrossPostResult: ...
    async def validate_credentials(self) -> bool: ...
```

### Platforms

- **Bluesky** — AT Protocol HTTP API. Builds rich text facets for URLs and hashtags. 300-character limit.
- **Mastodon** — HTTP API via httpx.

A platform registry maps names to poster classes. Each cross-post attempt is recorded in the `cross_posts` table with status, platform ID, timestamp, and error message.

## Frontend Architecture

### Routing

| Route | Page | Description |
|-------|------|-------------|
| `/` | TimelinePage | Paginated post list with filter panel |
| `/post/*` | PostPage | Single post view (rendered HTML) |
| `/page/:pageId` | PageViewPage | Top-level page (About, etc.) |
| `/search` | SearchPage | Full-text search results |
| `/login` | LoginPage | Login form |
| `/labels` | LabelListPage | Label list with post counts |
| `/labels/graph` | LabelGraphPage | Interactive DAG visualization (auth: edge create/delete) |
| `/labels/:labelId` | LabelPostsPage | Posts filtered by label |
| `/labels/:labelId/settings` | LabelSettingsPage | Label names, parents, delete (auth required) |
| `/editor/*` | EditorPage | Structured metadata bar + split-pane markdown editor |

### State Management

Two Zustand stores:

- **`authStore`** — User state, login/logout, token persistence in localStorage.
- **`siteStore`** — Site configuration fetched on app load.

The `ky` HTTP client injects `Authorization: Bearer <token>` from localStorage and clears tokens on 401 responses.

### SEO

`SEOMiddleware` intercepts HTML responses for `/post/*` routes and injects Open Graph and Twitter Card meta tags by looking up post metadata from the database cache.

## Testing

### Backend (pytest)

```
tests/
├── conftest.py                  Fixtures: tmp content dir, settings, DB engine/session
├── test_api/
│   └── test_api_integration.py  Full API tests via httpx AsyncClient + ASGITransport
├── test_services/
│   ├── test_config.py           Settings loading
│   ├── test_content_manager.py  ContentManager operations
│   ├── test_crosspost.py        Cross-posting platforms
│   ├── test_database.py         DB engine creation
│   ├── test_datetime_service.py Date/time parsing
│   └── test_sync_service.py     Sync plan computation
├── test_labels/                 Label service tests
└── test_rendering/              Pandoc rendering tests
```

Configuration in `pyproject.toml`: `asyncio_mode = "auto"`, markers for `slow` and `integration`, coverage via `pytest-cov`.

### Frontend (Vitest)

Vitest with jsdom environment, `@testing-library/react`, and `@testing-library/user-event`.

## Build and Deployment

### Local Development

```bash
# Backend
uv sync
source .venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (hot reload, proxies /api to :8000)
cd frontend && npm run dev
```

### Docker

Multi-stage build:

1. **Stage 1** (Node 22 Alpine): `npm ci && npm run build` to produce `frontend/dist/`.
2. **Stage 2** (Python 3.13 slim): Installs Pandoc, copies uv from astral-sh image, installs Python dependencies, copies backend + CLI + frontend dist, runs as non-root `agblogger` user on port 8000.

Volumes: `/data/content` (blog content) and `/data/db` (SQLite database).

Health check: `curl -f http://localhost:8000/api/health`.

### Production HTTPS

The `Caddyfile` configures automatic Let's Encrypt TLS, reverse proxy to the backend, static asset caching with `Cache-Control: immutable`, and gzip/zstd compression.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Filesystem as source of truth | Backup by copying files; database is fully regenerable at startup |
| Async throughout | Non-blocking I/O for file serving and database queries |
| SQLite FTS5 for search | Zero-config full-text search with good performance |
| Recursive CTEs for label DAG | SQLite supports them natively; efficient hierarchy traversal |
| Pandoc rendering at publish time | ~100ms overhead on write is acceptable; no per-request cost |
| JWT with refresh token rotation | Prevents stolen refresh token reuse |
| SHA-256 based sync | Clock-skew immune, deterministic conflict detection |
| Single Docker container | Simplest deployment for a self-hosted blog |

## Data Flow

### Creating a Post (Editor)

```
Frontend sends structured data: { file_path, body, labels, is_draft }
    → POST /api/posts
        → Backend sets author from authenticated user
        → Backend sets created_at and modified_at to now
        → Constructs PostData from structured fields
        → serialize_post() assembles YAML front matter + body
        → write to content/ directory
        → render HTML via Pandoc, store in PostCache
```

### Updating a Post (Editor)

```
Frontend sends structured data: { body, labels, is_draft }
    → PUT /api/posts/{path}
        → Backend preserves original author and created_at from filesystem
        → Backend sets modified_at to now
        → Constructs PostData from structured fields
        → serialize_post() assembles YAML front matter + body
        → write to content/ directory
        → render HTML via Pandoc, update PostCache
```

### Publishing a Post (Filesystem)

```
Write .md file → ContentManager.write_post()
    → serialize YAML front matter + body
    → write to content/ directory
    → rebuild_cache()
        → parse all .md files
        → render HTML via Pandoc
        → populate PostCache + PostsFTS
        → parse labels.toml
        → populate LabelCache + PostLabelCache
```

### Editing a Post (Loading)

```
GET /api/posts/{path}/edit (auth required)
    → ContentManager.read_post()
        → parse .md file from filesystem
        → return structured JSON: body, labels, is_draft, timestamps, author
```

### Reading a Post

```
GET /api/posts/{path}
    → PostService.get_post()
        → query PostCache (pre-rendered HTML)
        → return cached metadata + HTML
```

### Searching

```
GET /api/posts/search?q=...
    → PostService.search_posts()
        → FTS5 MATCH query on posts_fts
        → join with PostCache for metadata
        → return ranked results with snippets
```
