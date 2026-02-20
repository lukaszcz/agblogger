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
│       ├── hooks/      Custom React hooks (auto-save, KaTeX)
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
| Markdown rendering | Pandoc (via subprocess) |
| Front matter parsing | python-frontmatter + PyYAML |
| TOML | stdlib tomllib (read) + tomli-w (write) |
| Auth | python-jose (JWT) + bcrypt |
| Validation | Pydantic 2 + pydantic-settings |
| Date/time | pendulum |
| Sync merging | merge3 |
| Content versioning | git (CLI) |
| HTTP client | httpx |
| Cross-posting | httpx |

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
- git (content versioning for three-way merge)
- uv (Python dependency management)
- Docker + Docker Compose
- Caddy (optional HTTPS reverse proxy)

## Core Concepts

### Markdown as Source of Truth

The filesystem is the canonical store for all content. The database is entirely regenerable from the files on disk — it is rebuilt on every server startup via `rebuild_cache()`. Post CRUD endpoints also perform incremental cache maintenance for `posts_cache`, `posts_fts`, and `post_labels_cache` so search/filter data stays fresh between full rebuilds.

The `content/` directory is **not version-controlled** (it is in `.gitignore`). On first startup, `ensure_content_dir()` in `backend/main.py` creates a minimal scaffold (`index.toml`, `labels.toml`, `posts/`) if the directory doesn't exist.

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
3. Ensures the content directory exists (`ensure_content_dir()`), creating the default scaffold if needed.
4. Initializes the `ContentManager`.
5. Initializes the `GitService` (creates a git repo in the content directory if one doesn't exist).
6. Creates the admin user if it doesn't exist.
7. Rebuilds the full database cache from the filesystem.

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
| `auth` | `/api/auth` | Login, invite-based register, refresh/logout, invite management, PAT management, current user |
| `posts` | `/api/posts` | CRUD, search, listing with pagination/filtering, structured editor data |
| `labels` | `/api/labels` | Label CRUD (create, update, delete), listing, graph data, posts by label |
| `pages` | `/api/pages` | Site config, rendered page content |
| `sync` | `/api/sync` | Bidirectional sync protocol |
| `crosspost` | `/api/crosspost` | Social account management, cross-posting |
| `render` | `/api/render` | Server-side Pandoc preview for the editor |
| `health` | `/api/health` | Health check with DB verification |

### Database Models

The database serves as a **cache**, not the source of truth:

- **`PostCache`** — Cached post metadata: file path, title, author, timestamps (`DateTime(timezone=True)`, stored as UTC), draft status, content hash (SHA-256), rendered excerpt (Pandoc HTML), rendered HTML.
- **`PostsFTS`** — SQLite FTS5 virtual table for full-text search over title and content.
- **`LabelCache`** — Label with ID, display names (JSON array), and implicit flag.
- **`LabelParentCache`** — DAG edge table (label_id → parent_id).
- **`PostLabelCache`** — Many-to-many posts to labels with source tracking ("frontmatter" or "directory").
- **`User`** — Username, email, password hash, display name, admin flag.
- **`RefreshToken`** — Hashed refresh token with expiry.
- **`PersonalAccessToken`** — Hashed long-lived API tokens (PATs), with revocation and optional expiry.
- **`InviteCode`** — Single-use hashed invite codes for closed registration.
- **`SocialAccount`** — OAuth credentials per user/platform.
- **`CrossPost`** — Cross-posting history log.
- **`SyncManifest`** — File state at last sync: path, content hash, file size, mtime.

### Rendering Pipeline

Pandoc renders markdown to HTML at publish time (during cache rebuild), not per-request. The rendered HTML is stored in `PostCache.rendered_html`. A rendered excerpt is also generated from a markdown-preserving truncation (`generate_markdown_excerpt()`) and stored in `PostCache.rendered_excerpt` — used in timeline cards and search results. KaTeX math in excerpts is processed client-side by the `useRenderedHtml` hook.

```
pandoc -f gfm+tex_math_dollars+footnotes+raw_html -t html5
       --katex --highlight-style=pygments --wrap=none
```

Features: GitHub Flavored Markdown (tables, task lists, strikethrough), KaTeX math, syntax highlighting (140+ languages), and heading anchor injection.

Lua filter files exist in `backend/pandoc/filters/` as placeholders for future use (callouts, tabsets, video embeds, local link rewriting) but are not currently wired into the rendering pipeline.

## Authentication and Authorization

### Token and Session Flow

- **Web sessions**: Login issues `access_token` and `refresh_token` as `HttpOnly` cookies, plus a readable `csrf_token` cookie.
- **CSRF protection**: Unsafe API methods (`POST/PUT/PATCH/DELETE`) with cookie auth require `X-CSRF-Token` matching the `csrf_token` cookie.
- **Access tokens**: Short-lived (15 min), HS256 JWT containing `{sub: user_id, username, is_admin}`.
- **Refresh tokens**: Long-lived (7 days), cryptographically random 48-byte strings. Only SHA-256 hashes are stored in DB. Refresh rotates tokens and revokes the old one.
- **PATs (Personal Access Tokens)**: Long-lived random tokens (hashed in DB) for CLI/API automation via Bearer auth.
- **Passwords**: bcrypt hashed.
- **Logout**: `POST /api/auth/logout` revokes refresh token (if present) and clears auth cookies.

### Registration and Abuse Controls

- **Self-registration** is disabled by default (`AUTH_SELF_REGISTRATION=false`).
- **Invite-based registration** is enabled by default (`AUTH_INVITES_ENABLED=true`): admins generate single-use invite codes.
- **Rate limiting** is applied to failed auth attempts on login and refresh endpoints in a sliding window.

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
  │     (client manifest,                   │  Compare client manifest
  │      last_sync_commit) ─────────────►   │  vs server manifest
  │   ◄──────── (sync plan,                 │  vs current filesystem
  │              server_commit)              │
  │                                         │
  │  2. POST /api/sync/upload               │
  │     (changed + conflict files) ─────►   │  Write files to content/
  │                                         │
  │  3. GET /api/sync/download/{path}       │
  │   ◄──────────────── (file content)      │  Send files to client
  │                                         │
  │  4. POST /api/sync/commit               │
  │     (uploaded_files, deleted_files,     │  Merge conflicts, apply
  │      conflict_files,                    │  deletions, normalize front
  │      last_sync_commit) ─────────────►   │  matter, git commit, update
  │   ◄──────── (commit_hash,               │  manifest, rebuild cache
  │              merge_results)              │
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
| Deleted | Changed | Conflict (delete/modify) |
| Same | Deleted | Delete on client |

### Front Matter Normalization

During `sync_commit`, before scanning files and updating the manifest, the server applies `deleted_files` requested by the client and normalizes YAML front matter for uploaded `.md` files under `posts/`. The client sends `uploaded_files` in the commit request to identify which files were uploaded.

- **New posts** (not in old server manifest): missing fields are filled with defaults — `created_at` and `modified_at` set to now, `author` from site config `default_author`.
- **Edited posts** (in old server manifest): existing fields are preserved, except `modified_at` which is set to the current server time.
- **Unrecognized fields** in front matter are preserved in the file but generate warnings in the commit response.

Recognized front matter fields: `created_at`, `modified_at`, `author`, `labels`, `draft`.

### Git Content Versioning

The server's `content/` directory is a git repository. Every file-modifying operation (post create/update/delete, label create/update/delete, sync commit) creates a git commit via `GitService`. This provides:

- A complete history of all content changes
- The merge base for three-way conflict resolution during sync
- The `server_commit` hash returned in sync init, used by clients to track their last sync point

`GitService` (`backend/services/git_service.py`) wraps the git CLI via `subprocess.run`. It is synchronous (git operations are fast for small repos). The repo is initialized on application startup with `git init` if `.git/` doesn't exist.

### Three-Way Merge

When both client and server modify the same file, the sync protocol performs a three-way merge using `merge3`:

1. **Client uploads its version** of conflicting files during sync
2. **Server retrieves the merge base** from git history using the client's `last_sync_commit`
3. **`merge_file(base, server, client)`** performs the merge:
   - **Clean merge** (non-overlapping edits): merged result written to disk, `MergeResult.status = "merged"`
   - **Unresolved conflict** (overlapping edits): server version restored on disk, diff3 conflict markers returned to client in `MergeResult.content` with `status = "conflicted"`
   - **No base available** (first sync or invalid commit): falls back to keeping server version with `status = "conflicted"`
4. **Delete/modify conflicts**: the modified version is kept regardless of which side deleted

The client handles merge results:
- `"merged"` → downloads the merged file from the server
- `"conflicted"` → backs up local file as `.conflict-backup`, writes conflict markers as the main file for manual resolution

### CLI Sync Client (`cli/sync_client.py`)

A standalone Python script using httpx with subcommands: `init`, `status`, `push`, `pull`, `sync`. Stores config in `.agblogger-sync.json` (including `last_sync_commit`) and the local manifest in `.agblogger-manifest.json`. The client uploads conflict files to the server for three-way merge, sends `uploaded_files`, `deleted_files`, `conflict_files`, and `last_sync_commit` in the commit request, and saves the returned `commit_hash` for subsequent syncs.

CLI authentication supports either:
- Username/password login (obtaining a JWT access token), or
- A pre-created PAT via `--pat` (recommended for automation).

For transport security, the CLI requires `https://` for non-localhost servers by default. Plain `http://` is only allowed for localhost, or when explicitly opted in with `--allow-insecure-http`.

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

Uses `createBrowserRouter` (data router) with `RouterProvider` for full react-router v7 feature support including `useBlocker`.

| Route | Page | Description |
|-------|------|-------------|
| `/` | TimelinePage | Paginated post list with filter panel |
| `/post/*` | PostPage | Single post view (rendered HTML) |
| `/page/:pageId` | PageViewPage | Top-level page (About, etc.) |
| `/search` | SearchPage | Full-text search results |
| `/login` | LoginPage | Login form |
| `/labels` | LabelsPage | Label list/graph with segmented control toggle (auth: graph edge create/delete) |
| `/labels/:labelId` | LabelPostsPage | Posts filtered by label |
| `/labels/:labelId/settings` | LabelSettingsPage | Label names, parents, delete (auth required) |
| `/editor/*` | EditorPage | Structured metadata bar + split-pane markdown editor |

### Editor Auto-Save

The `useEditorAutoSave` hook (`hooks/useEditorAutoSave.ts`) provides crash recovery and unsaved-changes protection:

- **Dirty tracking**: Compares current form state (body, labels, isDraft, newPath) to the loaded/initial state
- **Debounced auto-save**: Writes draft to `localStorage` (key: `agblogger:draft:<filePath>`) 3 seconds after the last edit
- **Navigation blocking**: `useBlocker` shows a native `window.confirm` dialog for in-app SPA navigation; `beforeunload` covers tab close and page refresh
- **Draft recovery**: On editor mount, detects stale drafts and shows a banner with Restore/Discard options
- **Enabled gating**: The hook accepts an `enabled` parameter; for existing posts it activates only after loading completes, preventing false dirty state during data fetch

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
│   ├── test_git_service.py      Git service operations
│   ├── test_merge.py            Three-way merge logic
│   ├── test_sync_service.py     Sync plan computation
│   └── test_sync_merge_integration.py  Full merge API flow
├── test_sync/                   CLI sync client tests
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
| Git-backed content directory | Provides merge base for three-way sync; full change history at no extra cost |
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
