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
├── cli/                Sync and deployment CLIs
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
│   ├── 2026-02-02-hello-world.md        Flat post (legacy)
│   └── 2026-02-20-my-post/              Post-per-directory (new posts)
│       ├── index.md                     Post content
│       ├── photo.png                    Co-located asset
│       └── diagram.svg                  Co-located asset
└── assets/                 Shared assets
```

Posts use YAML front matter:

```yaml
---
title: Post Title
created_at: 2026-02-02 22:21:29.975359+00
modified_at: 2026-02-02 22:21:35.000000+00
author: Admin
labels: ["#swe"]
---

Content here...
```

- **Title** is stored as a `title` field in YAML front matter. For backward compatibility, if `title` is absent, it is extracted from the first `# Heading` in the body, falling back to filename derivation. During sync, missing titles are backfilled from the first heading (or filename), and any matching leading heading is stripped from the body.
- **Labels** are referenced as `#label-id` strings.
- **Timestamps** use strict ISO output format; lax input is accepted via pendulum.
- **Post-per-directory**: New posts created via the web UI are stored as `posts/<date>-<slug>/index.md` with co-located assets. The slug is generated from the title via NFKD unicode normalization → ASCII → lowercase → hyphenated (max 80 chars). Existing flat posts (`posts/hello.md`) continue to work.
- **Directory rename on title change**: When a post's title changes, the directory is renamed to match the new slug. A symlink is created at the old path pointing to the new directory, preserving old URLs.
- **Directories** under `posts/` are for disk organization only — they have no effect on labels or metadata.

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
2. Configures docs/OpenAPI exposure based on environment (`DEBUG` or `EXPOSE_DOCS`).
3. Adds middleware:
   - `TrustedHostMiddleware` for host header allowlisting.
   - CORS middleware for browser origin control.
   - Cookie CSRF middleware for unsafe methods.
   - Security headers middleware (`nosniff`, frame deny, referrer policy, CSP).
4. Registers API routers under `/api/`.
5. Serves the React SPA static files from `frontend/dist/`.

On startup, the lifespan handler:

1. Creates the async SQLAlchemy engine and session factory.
2. Creates all database tables (including the FTS5 virtual table).
3. Validates production security settings (`validate_runtime_security()`), failing fast for insecure defaults.
4. Ensures the content directory exists (`ensure_content_dir()`), creating the default scaffold if needed.
5. Initializes the `ContentManager`.
6. Initializes the `GitService` (creates a git repo in the content directory if one doesn't exist).
7. Loads or creates the AT Protocol OAuth ES256 keypair (`content/.atproto-oauth-key.json`) and initializes OAuth state stores for Bluesky, Mastodon, X, and Facebook on `app.state`.
8. Creates the admin user if it doesn't exist.
9. Applies lightweight schema compatibility updates for `cross_posts.user_id` when needed.
10. Rebuilds the full database cache from the filesystem.

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
| `posts` | `/api/posts` | Search/list/read for all users; create/update/delete/upload/edit-data are admin-only |
| `labels` | `/api/labels` | Label CRUD (create, update, delete), listing, graph data, posts by label |
| `pages` | `/api/pages` | Site config, rendered page content |
| `sync` | `/api/sync` | Bidirectional sync protocol (admin-only) |
| `crosspost` | `/api/crosspost` | Social account management, cross-posting, Bluesky/Mastodon/X/Facebook OAuth flows |
| `render` | `/api/render` | Server-side Pandoc preview for the editor |
| `admin` | `/api/admin` | Site settings, page management, password change (admin-only) |
| `content` | `/api/content` | Public file serving for post assets and shared assets |
| `health` | `/api/health` | Health check with DB verification |

### Database Models

The database serves as a **cache**, not the source of truth:

- **`PostCache`** — Cached post metadata: file path, title, author, timestamps (`DateTime(timezone=True)`, stored as UTC), draft status, content hash (SHA-256), rendered excerpt (Pandoc HTML), rendered HTML.
- **`PostsFTS`** — SQLite FTS5 virtual table for full-text search over title and content.
- **`LabelCache`** — Label with ID, display names (JSON array), and implicit flag.
- **`LabelParentCache`** — DAG edge table (label_id → parent_id).
- **`PostLabelCache`** — Many-to-many association between posts and labels.
- **`User`** — Username, email, password hash, display name, admin flag.
- **`RefreshToken`** — Hashed refresh token with expiry.
- **`PersonalAccessToken`** — Hashed long-lived API tokens (PATs), with revocation and optional expiry.
- **`InviteCode`** — Single-use hashed invite codes for closed registration.
- **`SocialAccount`** — OAuth credentials per user/platform.
- **`CrossPost`** — Cross-posting history log scoped to the owning user (`user_id`).
- **`SyncManifest`** — File state at last sync: path, content hash, file size, mtime.

### Rendering Pipeline

Pandoc renders markdown to HTML at publish time (during cache rebuild), not per-request. The rendered HTML is stored in `PostCache.rendered_html`. A rendered excerpt is also generated from a markdown-preserving truncation (`generate_markdown_excerpt()`) and stored in `PostCache.rendered_excerpt`. Search results render excerpt HTML client-side (including KaTeX via `useRenderedHtml`), while timeline cards render excerpts as plain text extracted from sanitized HTML.

Pandoc output is sanitized through an allowlist HTML sanitizer before storage and before heading-anchor injection. Unsafe tags/attributes and unsafe URL schemes (for example `javascript:`) are stripped.

```
pandoc -f gfm+tex_math_dollars+footnotes+raw_html -t html5
       --katex --highlight-style=pygments --wrap=none
```

Features: GitHub Flavored Markdown (tables, task lists, strikethrough), KaTeX math, syntax highlighting (140+ languages), and heading anchor injection.

After rendering and sanitization, `rewrite_relative_urls()` rewrites relative `src` and `href` attributes in the HTML to absolute `/api/content/...` paths based on the post's file path. This allows co-located assets (e.g., `photo.png` next to `index.md`) to be referenced with simple relative paths in markdown and served correctly via the content API.

Lua filter files exist in `backend/pandoc/filters/` as placeholders for future use (callouts, tabsets, video embeds, local link rewriting) but are not currently wired into the rendering pipeline.

## Authentication and Authorization

### Token and Session Flow

- **Web sessions**: Login issues `access_token`, `refresh_token`, and `csrf_token` as `HttpOnly` cookies.
- **CSRF protection**: Unsafe API methods (`POST/PUT/PATCH/DELETE`) with cookie auth require `X-CSRF-Token` matching the `csrf_token` cookie. The token is mirrored in an `X-CSRF-Token` response header and persisted by the frontend client for subsequent unsafe requests.
- **Login origin enforcement**: Login requests with `Origin`/`Referer` must match the app origin or configured CORS origins.
- **Access tokens**: Short-lived (15 min), HS256 JWT containing `{sub: user_id, username, is_admin}`.
- **Refresh tokens**: Long-lived (7 days), cryptographically random 48-byte strings. Only SHA-256 hashes are stored in DB. Refresh rotates tokens and revokes the old one.
- **PATs (Personal Access Tokens)**: Long-lived random tokens (hashed in DB) for CLI/API automation via Bearer auth.
- **Passwords**: bcrypt hashed.
- **Logout**: `POST /api/auth/logout` revokes refresh token (if present) and clears auth cookies.
- **Trusted proxy handling**: `X-Forwarded-For` is only trusted when the direct peer IP is in `TRUSTED_PROXY_IPS`; otherwise the socket peer IP is used for rate-limit keys.

### Registration and Abuse Controls

- **Self-registration** is disabled by default (`AUTH_SELF_REGISTRATION=false`).
- **Invite-based registration** is enabled by default (`AUTH_INVITES_ENABLED=true`): admins generate single-use invite codes.
- **Rate limiting** is applied to failed auth attempts on login and refresh endpoints in a sliding window.

### Roles

| Role | Access |
|------|--------|
| Unauthenticated | Read published (non-draft) posts, labels, pages, search |
| Authenticated | Above + cross-post and user-scoped account actions |
| Admin | Above + post create/update/delete/upload/edit-data, sync, and admin panel operations |

Public reads require no authentication. The `get_current_user()` dependency returns `None` for unauthenticated requests.

**Draft visibility**: Draft posts and their co-located assets are visible only to their author for read endpoints. The post listing endpoint filters drafts by matching the authenticated user's display name (or username) against the post's author field. Direct access to draft post pages and content files enforces the same author-only restriction, including legacy flat draft markdown files under `posts/*.md`. Editing endpoints are admin-only regardless of draft author.

### Admin Bootstrap

On startup, `ensure_admin_user()` creates the admin user from `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables if no matching user exists.

## Bidirectional Sync

Hash-based, three-way sync inspired by Unison. Both client and server maintain a **sync manifest** mapping `file_path → (SHA-256 hash, mtime, size)`.
All `/api/sync/*` endpoints require an authenticated admin user.

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

Recognized front matter fields: `title`, `created_at`, `modified_at`, `author`, `labels`, `draft`.

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

### CLI Deployment Helper (`cli/deploy_production.py`)

An interactive deployment script (`agblogger-deploy`) that:

1. Validates Docker/Docker Compose availability.
2. Prompts for required production settings (`SECRET_KEY`, `ADMIN_*`, `TRUSTED_HOSTS`, optional `TRUSTED_PROXY_IPS`, `HOST_PORT`).
3. Optionally configures Caddy by asking for a public domain and optional ACME contact email.
4. Writes `.env.production` with hardened defaults (`DEBUG=false`, `EXPOSE_DOCS=false`, `AUTH_ENFORCE_LOGIN_ORIGIN=true`).
5. Uses checked-in `docker-compose.yml` as the default Caddy-based deployment and generates `Caddyfile.production` when Caddy is enabled.
6. For public Caddy exposure, generates `docker-compose.caddy-public.yml` and deploys with `-f docker-compose.yml -f docker-compose.caddy-public.yml`.
7. When Caddy is disabled, generates `docker-compose.nocaddy.yml` and deploys with `-f docker-compose.nocaddy.yml`.
8. Prints operational commands for start/stop/status and the correct login URL.

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

- **Bluesky** — AT Protocol OAuth (confidential client / BFF pattern). Uses DPoP-bound access tokens, PKCE, and Pushed Authorization Requests (PAR). Builds rich text facets for URLs and hashtags. 300-character limit.
- **Mastodon** — OAuth 2.0 with dynamic app registration and PKCE. Posts statuses via httpx. 500-character limit.
- **X (Twitter)** — OAuth 2.0 with PKCE. Posts text tweets via X API v2 (`POST /2/tweets`). 280-character limit. Token refresh on 401.
- **Facebook** — OAuth 2.0 for Facebook Pages. Posts to Pages via Graph API v22.0 (`POST /{page-id}/feed`). Page Access Tokens are non-expiring. Multi-page selection supported.

A platform registry maps names to poster classes. Each cross-post attempt is recorded in the `cross_posts` table with status, platform ID, timestamp, and error message. When tokens are refreshed during a cross-post (Bluesky or X), the updated credentials are re-encrypted and persisted.

Cross-posting supports an optional `custom_text` field: when provided via the API (`CrossPostRequest.custom_text`), platforms use it verbatim instead of auto-generating text from the post title, excerpt, and URL.

### Bluesky OAuth Flow

AgBlogger authenticates with Bluesky using AT Protocol OAuth with three mandatory extensions:

- **PKCE (S256)**: Prevents authorization code interception.
- **PAR**: Authorization parameters are pushed server-side, not exposed in the browser URL.
- **DPoP**: Every token request and API call includes an ES256-signed JWT proof binding the token to the client.

The flow:

1. User enters their Bluesky handle → `POST /api/crosspost/bluesky/authorize`
2. Backend resolves handle → DID → PDS → authorization server metadata
3. Backend sends a PAR request with PKCE challenge + client assertion (signed with the app's ES256 key)
4. Frontend redirects user to Bluesky's authorization page
5. Bluesky redirects back to `GET /api/crosspost/bluesky/callback`
6. Backend exchanges authorization code for DPoP-bound tokens, stores encrypted credentials in `SocialAccount`

**Client identity**: An ES256 keypair is generated on first startup and stored at `{content_dir}/.atproto-oauth-key.json`. The public key is served in the client metadata document at `GET /api/crosspost/bluesky/client-metadata.json`. The `BLUESKY_CLIENT_URL` setting provides the public base URL used to construct the `client_id`.

**OAuth state**: Pending authorization flows are stored in an in-memory `OAuthStateStore` (`backend/crosspost/bluesky_oauth_state.py`) with a 10-minute TTL, keyed by the `state` parameter.

**Token lifecycle**: Access tokens are short-lived and DPoP-bound. Refresh tokens last up to 3 months. On 401 responses during cross-posting, the `BlueskyCrossPoster` automatically refreshes tokens and retries. Updated tokens are persisted after each successful cross-post.

### Mastodon OAuth Flow

Mastodon uses standard OAuth 2.0 with dynamic client registration and PKCE:

1. User enters their Mastodon instance URL → `POST /api/crosspost/mastodon/authorize`
2. Backend validates and normalizes the instance URL (SSRF protection via `_normalize_instance_url()`)
3. Backend dynamically registers an app on the instance via `POST /api/v1/apps`, generating PKCE challenge
4. OAuth state (client credentials, PKCE verifier, instance URL) is stored in the in-memory `OAuthStateStore` with 10-minute TTL
5. Frontend redirects user to the instance's `/oauth/authorize` endpoint
6. Instance redirects back to `GET /api/crosspost/mastodon/callback`
7. Backend exchanges authorization code for access token, verifies credentials via `GET /api/v1/accounts/verify_credentials`, stores encrypted credentials in `SocialAccount`

### X OAuth Flow

X uses OAuth 2.0 with PKCE:

1. User clicks "Connect X" on the admin page → `POST /api/crosspost/x/authorize`
2. Backend builds the authorization URL with PKCE challenge using `X_CLIENT_ID` and `X_CLIENT_SECRET` settings
3. OAuth state (PKCE verifier, client credentials) is stored in the in-memory `OAuthStateStore` with 10-minute TTL
4. Frontend redirects user to X's authorization page
5. X redirects back to `GET /api/crosspost/x/callback`
6. Backend exchanges authorization code for access and refresh tokens, fetches user profile via `GET /2/users/me`, stores encrypted credentials in `SocialAccount`

**Token lifecycle**: Access tokens are short-lived. Refresh tokens are used to obtain new access tokens. On 401 responses during cross-posting, `XCrossPoster` automatically refreshes tokens and retries. Updated tokens are persisted after refresh.

### Facebook OAuth Flow

Facebook uses OAuth 2.0 for Pages:

1. User clicks "Connect Facebook" on the admin page → `POST /api/crosspost/facebook/authorize`
2. Backend builds the authorization URL using `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` settings, requesting `pages_manage_posts` and `pages_read_engagement` scopes
3. OAuth state is stored in the in-memory `OAuthStateStore` with 10-minute TTL
4. Frontend redirects user to Facebook's authorization page
5. Facebook redirects back to `GET /api/crosspost/facebook/callback`
6. Backend exchanges the authorization code for a short-lived user token, then exchanges it for a long-lived token
7. Backend fetches managed Pages via `GET /me/accounts`, presenting a page selection step if multiple pages are available
8. Page Access Tokens (non-expiring for long-lived user tokens) and selected page info are stored encrypted in `SocialAccount`

### Cross-Posting UI

The frontend cross-posting interface spans three pages:

**Admin page** (`SocialAccountsPanel`): A "Social Accounts" section lists connected accounts as cards with platform icon, handle, and disconnect button. Connect buttons open inline forms for entering a Bluesky handle, Mastodon instance URL, or initiating X/Facebook OAuth flows.

**Post page** (`CrossPostSection`, `CrossPostHistory`): An admin-only section below post content shows cross-post history (platform icon, timestamp, status badge) and a "Share" button (visible only when accounts are connected). The Share button opens the `CrossPostDialog`.

**Editor page**: When social accounts are connected, platform checkboxes appear in the metadata bar ("Share after saving"). On save with platforms selected, the `CrossPostDialog` opens pre-populated — a two-step flow ensuring the user reviews text before posting.

**Cross-post dialog** (`CrossPostDialog`): A modal with a single editable textarea (auto-generated from post title + URL), per-platform character counters (300 for Bluesky, 280 for X, 500 for Mastodon; Facebook has no limit), platform checkboxes, and a results view showing per-platform success/failure after posting.

### Post Sharing (Client-Side)

Separate from the admin-only cross-posting system, post sharing is a client-side feature available to all users (including unauthenticated visitors). It requires no backend changes — share links are constructed entirely in the browser.

**Components** live in `frontend/src/components/share/`:

```
frontend/src/components/share/
├── shareUtils.ts           Share URL generation, native share API, clipboard, Mastodon instance helpers
├── ShareButton.tsx         Compact header share button with dropdown popover
├── ShareBar.tsx            Bottom-of-post horizontal row of platform icon buttons
└── MastodonSharePrompt.tsx Inline form for Mastodon instance URL input
```

**Placement on PostPage**: `ShareButton` appears inline in the post header metadata row (date, author, labels). `ShareBar` appears as a horizontal icon row below the post content, above the admin-only cross-post section.

**Share mechanism**: On browsers that support the Web Share API (`navigator.share`), `ShareButton` invokes the native OS share sheet directly — clicking the button invokes the OS share sheet without showing platform options. On browsers without Web Share API support, it opens a dropdown popover listing platform buttons. `ShareBar` always shows individual platform buttons and additionally shows the native share button alongside them when the API is available.

**Supported platforms**: Bluesky, Mastodon, X, Facebook, LinkedIn, Reddit, Email, and Copy Link. Platform buttons open a pre-filled compose URL in a new tab (e.g., `https://bsky.app/intent/compose?text=...`). Email uses a `mailto:` link in the current window. Copy Link writes the post URL to the clipboard.

**Share text format**: When an author is present: `"\u201c{title}\u201d by {author} {url}"`. When the author is null: `"\u201c{title}\u201d {url}"`. Both formats use curly (typographic) quotes around the title.

**Mastodon instance handling**: Mastodon requires a per-instance share URL (`https://{instance}/share?text=...`). When a user clicks the Mastodon share button for the first time, `MastodonSharePrompt` asks for their instance URL (e.g., `mastodon.social`). The instance is saved to `localStorage` (key: `agblogger:mastodon-instance`) and reused on subsequent shares.

**Platform icons**: The existing `PlatformIcon` component (`frontend/src/components/crosspost/PlatformIcon.tsx`) was extended with SVG icons for X, Facebook, LinkedIn, and Reddit to support the additional share platforms.

**Distinction from cross-posting**: Sharing opens external compose pages for the reader to post from their own accounts. Cross-posting publishes server-side from the admin's connected OAuth accounts. The two features are independent and appear in separate sections on the post page.

## Frontend Architecture

### Routing

Uses `createBrowserRouter` (data router) with `RouterProvider` for full react-router v7 feature support including `useBlocker`.

| Route | Page | Description |
|-------|------|-------------|
| `/` | TimelinePage | Paginated post list with filter panel, post upload (file/folder) |
| `/post/*` | PostPage | Single post view (rendered HTML) |
| `/page/:pageId` | PageViewPage | Top-level page (About, etc.) |
| `/search` | SearchPage | Full-text search results |
| `/login` | LoginPage | Login form |
| `/labels` | LabelsPage | Label list/graph with segmented control toggle (auth: graph edge create/delete) |
| `/labels/:labelId` | LabelPostsPage | Posts filtered by label |
| `/labels/:labelId/settings` | LabelSettingsPage | Label names, parents, delete (auth required) |
| `/editor/*` | EditorPage | Structured metadata bar + split-pane markdown editor |
| `/admin` | AdminPage | Admin panel: site settings, pages, password (admin required) |

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

`docker-compose.yml` is Caddy-first: AgBlogger is internal-only (`expose: 8000`), Caddy publishes `127.0.0.1:80:80` and `127.0.0.1:443:443`, and Caddy forwards to `agblogger:8000`.

For public Caddy deployment, the script generates `docker-compose.caddy-public.yml` that overrides Caddy ports to `80:80` and `443:443`.

For deployments without Caddy, the deploy script generates `docker-compose.nocaddy.yml` that publishes AgBlogger directly on `${HOST_BIND_IP:-127.0.0.1}:${HOST_PORT:-8000}:8000`.

Recommended deployment path is the interactive helper:

```bash
uv run agblogger-deploy
```

### Production HTTPS

When enabled in the deploy helper, Caddy is configured as a reverse proxy in front of AgBlogger with automatic Let's Encrypt TLS, static asset caching with `Cache-Control: immutable`, and gzip/zstd compression.

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
Frontend sends structured data: { title, body, labels, is_draft }
    → POST /api/posts
        → Require admin
        → Backend generates directory path: posts/<date>-<slug>/index.md
        → Backend sets author from authenticated user
        → Backend sets created_at and modified_at to now
        → Constructs PostData from structured fields
        → serialize_post() assembles YAML front matter + body
        → write to content/ directory (creates directory)
        → render HTML via Pandoc, rewrite relative URLs, store in PostCache
```

### Updating a Post (Editor)

```
Frontend sends structured data: { title, body, labels, is_draft }
    → PUT /api/posts/{path}
        → Require admin
        → Backend uses title from request body
        → Backend preserves original author and created_at from filesystem
        → Backend sets modified_at to now
        → Constructs PostData from structured fields
        → serialize_post() assembles YAML front matter + body
        → write to content/ directory
        → If title slug changed: rename directory, create symlink at old path
        → render HTML via Pandoc, rewrite relative URLs, update PostCache
        → Returns new file_path (may differ from request path after rename)
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
GET /api/posts/{path}/edit (admin required)
    → ContentManager.read_post()
        → parse .md file from filesystem
        → return structured JSON: title, body, labels, is_draft, timestamps, author
```

### Reading a Post

```
GET /api/posts/{path}
    → PostService.get_post()
        → query PostCache (pre-rendered HTML)
        → return cached metadata + HTML
```

### Uploading a Post (File or Folder)

```
User selects a .md file or a folder (with index.md + assets) on the Timeline page
    → POST /api/posts/upload (multipart form data)
        → Require admin
        → Find the markdown file (index.md preferred, else single .md file)
        → Parse frontmatter via parse_post() (same as sync/cache rebuild)
        → Normalize: title from frontmatter → first heading → ?title param → 422
        → Set created_at, modified_at, author, labels, is_draft with defaults
        → Generate post directory via generate_post_path()
        → Write all files (normalized markdown + assets)
        → Create PostCache, render HTML, update FTS index
        → Git commit
        → Return PostDetail → frontend navigates to new post
    → If 422 with "no_title": frontend shows title prompt, retries with ?title=
```

### Uploading Assets (Editor)

```
Frontend sends multipart file upload
    → POST /api/posts/{path}/assets
        → Require admin
        → Verify post exists in DB cache
        → Write files to post's directory (10 MB limit per file)
        → Git commit
        → Return list of uploaded filenames
        → Frontend inserts markdown at cursor: ![name](name) for images, [name](name) for others
```

### Serving Content Files

```
GET /api/content/{file_path}
    → Validate path (no traversal, allowed prefixes: posts/, assets/)
    → Verify resolved path stays within content directory
    → For draft content files (directory assets and flat draft markdown): require draft author authentication
    → Return FileResponse with guessed content type
```

### Deleting a Post

```
DELETE /api/posts/{path}?delete_assets=true|false
    → Require admin
    → If delete_assets=true and post is index.md:
        → Remove symlinks pointing to directory
        → Remove entire directory (post + all assets)
    → If delete_assets=false (default):
        → Remove only the .md file
    → Clean up DB cache, FTS index, label associations
    → Git commit
```

### Searching

```
GET /api/posts/search?q=...
    → PostService.search_posts()
        → FTS5 MATCH query on posts_fts
        → join with PostCache for metadata
        → return ranked results with snippets
```
