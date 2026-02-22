# Authentication and Authorization

## Token and Session Flow

- **Web sessions**: Login issues `access_token`, `refresh_token`, and `csrf_token` as `HttpOnly` cookies.
- **CSRF protection**: Unsafe API methods (`POST/PUT/PATCH/DELETE`) with cookie auth require `X-CSRF-Token` matching the `csrf_token` cookie. The token is mirrored in an `X-CSRF-Token` response header and persisted by the frontend client for subsequent unsafe requests.
- **Login origin enforcement**: Login requests with `Origin`/`Referer` must match the app origin or configured CORS origins.
- **Access tokens**: Short-lived (15 min), HS256 JWT containing `{sub: user_id, username, is_admin}`.
- **Refresh tokens**: Long-lived (7 days), cryptographically random 48-byte strings. Only SHA-256 hashes are stored in DB. Refresh rotates tokens and revokes the old one.
- **PATs (Personal Access Tokens)**: Long-lived random tokens (hashed in DB) for CLI/API automation via Bearer auth.
- **Passwords**: bcrypt hashed.
- **Logout**: `POST /api/auth/logout` revokes refresh token (if present) and clears auth cookies.
- **Trusted proxy handling**: `X-Forwarded-For` is only trusted when the direct peer IP is in `TRUSTED_PROXY_IPS`; otherwise the socket peer IP is used for rate-limit keys.

## Registration and Abuse Controls

- **Self-registration** is disabled by default (`AUTH_SELF_REGISTRATION=false`).
- **Invite-based registration** is enabled by default (`AUTH_INVITES_ENABLED=true`): admins generate single-use invite codes.
- **Rate limiting** is applied to failed auth attempts on login and refresh endpoints in a sliding window.

## Roles

| Role | Access |
|------|--------|
| Unauthenticated | Read published (non-draft) posts, labels, pages, search |
| Authenticated | Above + cross-post and user-scoped account actions |
| Admin | Above + post create/update/delete/upload/edit-data, sync, and admin panel operations |

Public reads require no authentication. The `get_current_user()` dependency returns `None` for unauthenticated requests.

**Draft visibility**: Draft posts and their co-located assets are visible only to their author for read endpoints. The post listing endpoint filters drafts by matching the authenticated user's display name (or username) against the post's author field. Direct access to draft post pages and content files enforces the same author-only restriction, including legacy flat draft markdown files under `posts/*.md`. Editing endpoints are admin-only regardless of draft author.

## Admin Bootstrap

On startup, `ensure_admin_user()` creates the admin user from `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables if no matching user exists.
