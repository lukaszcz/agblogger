# Backend Architecture

## Application Lifecycle (`backend/main.py`)

The `create_app()` factory:

1. Creates a FastAPI app with a lifespan context manager.
2. Configures docs/OpenAPI exposure based on environment (`DEBUG` or `EXPOSE_DOCS`).
3. Adds middleware (all defined inline in `main.py`):
   - `GZipMiddleware` for response compression (minimum 500 bytes).
   - `TrustedHostMiddleware` for host header allowlisting.
   - CORS middleware for browser origin control.
   - Cookie CSRF middleware for unsafe methods.
   - Security headers middleware (`nosniff`, frame deny, referrer policy, CSP).
4. Registers API routers under `/api/`.
5. Serves the React SPA static files from `frontend/dist/`.

On startup, the lifespan handler:

1. Validates production security settings (`validate_runtime_security()`), failing fast for insecure defaults.
2. Creates the async SQLAlchemy engine and session factory.
3. Drops all regenerable cache tables (`post_labels_cache`, `label_parents_cache`, `posts_fts`, `posts_cache`, `labels_cache`, `sync_manifest`) so `create_all` always matches the current schema.
4. Creates all database tables via `Base.metadata.create_all()`.
5. Applies lightweight schema compatibility updates for `cross_posts.user_id` when needed.
6. Creates the FTS5 virtual table (`posts_fts`).
7. Ensures required scaffold entries in the content directory via `ensure_content_dir()`: creates `content/`, `content/posts/`, `content/index.toml`, and `content/labels.toml` when any of them are missing (without overwriting existing files).
8. Initializes the `ContentManager`.
9. Initializes the `GitService` (creates a git repo in the content directory if one doesn't exist).
10. Loads or creates the AT Protocol OAuth ES256 keypair (`content/.atproto-oauth-key.json`) and initializes OAuth state stores for Bluesky, Mastodon, X, and Facebook on `app.state`.
11. Creates the admin user if it doesn't exist.
12. Starts the pandoc server (`PandocServer`) and initializes the renderer.
13. Rebuilds the full database cache from the filesystem.

## Layered Architecture

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

## API Routes

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

## Database Models

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

## Rendering Pipeline

Markdown is rendered to HTML via a long-lived `pandoc server` process managed by `PandocServer` in `backend/pandoc/server.py`. The server binds to `127.0.0.1` on an internal port and accepts JSON POST requests. `render_markdown()` in `renderer.py` sends async HTTP requests via `httpx` with a 10-second per-request timeout. If the server crashes, it is automatically restarted on the next render attempt.

Rendering happens at publish time (during cache rebuild and post create/update), not per-request. The rendered HTML is stored in `PostCache.rendered_html`. A rendered excerpt is also generated from a markdown-preserving truncation (`generate_markdown_excerpt()`) and stored in `PostCache.rendered_excerpt`. Search results render excerpt HTML client-side (including KaTeX via `useRenderedHtml`), while timeline cards render excerpts as plain text extracted from sanitized HTML.

Pandoc output is sanitized through an allowlist HTML sanitizer before storage and before heading-anchor injection. Unsafe tags/attributes and unsafe URL schemes (for example `javascript:`) are stripped.

Pandoc conversion settings: GFM with `tex_math_dollars`, `footnotes`, and `raw_html` extensions, output as `html5` with KaTeX math rendering and Pygments syntax highlighting.

Features: GitHub Flavored Markdown (tables, task lists, strikethrough), KaTeX math, syntax highlighting (140+ languages), and heading anchor injection.

After rendering and sanitization, `rewrite_relative_urls()` rewrites relative `src` and `href` attributes in the HTML to absolute `/api/content/...` paths based on the post's file path. This allows co-located assets (e.g., `photo.png` next to `index.md`) to be referenced with simple relative paths in markdown and served correctly via the content API.

Lua filter files exist in `backend/pandoc/filters/` as placeholders for future use (callouts, tabsets, video embeds, local link rewriting) but are not currently wired into the rendering pipeline.
