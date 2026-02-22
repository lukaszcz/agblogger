# Security Review Report — AgBlogger Full Codebase

**Scope:** Entire codebase
**Date:** 2026-02-22
**Branch:** `main`

---

## No High-Confidence Vulnerabilities Found

A comprehensive security review of the entire AgBlogger codebase was conducted, covering:

- All backend API endpoints and input validation
- Authentication and authorization flows (JWT, refresh tokens, CSRF)
- File operations and path traversal protections
- Subprocess calls for command injection
- HTML sanitization and XSS vectors
- Cryptographic implementations
- YAML/TOML deserialization
- OAuth/cross-posting flows (Mastodon, Bluesky)
- Frontend `dangerouslySetInnerHTML` usage

Three candidate findings were identified and subjected to independent false-positive validation. All three scored **below the confidence threshold of 8/10** and are excluded from the final report:

| # | Category | Location | Confidence | Reason for Exclusion |
|---|----------|----------|------------|----------------------|
| 1 | SSRF (DNS rebinding) | `backend/crosspost/mastodon.py` | 5/10 | HTTPS-only constraint blocks most internal targets; blind SSRF with fixed POST body; requires authentication |
| 2 | Data Exposure (dotfiles via sync) | `backend/api/sync.py` | 2/10 | Admin-only endpoint; admins are system owners; dotfiles excluded from sync manifests; secrets on disk behind auth is excluded per criteria |
| 3 | Login CSRF | `backend/main.py` | 2/10 | Mitigated by SameSite=Strict cookies, origin enforcement, JSON body + CORS; login CSRF is a low-impact web vulnerability excluded per criteria |

---

## Positive Security Observations

The codebase demonstrates strong security practices:

- **Path traversal:** Consistently prevented via `resolve()` + `is_relative_to()` across content serving, sync, and upload endpoints
- **SQL injection:** Parameterized queries used throughout, including FTS5 with proper escaping
- **Command injection:** Subprocess calls use list-based arguments; commit hashes validated with regex
- **HTML sanitization:** Strict allowlist-based sanitizer with URL scheme validation, applied before storage
- **Authentication:** bcrypt with timing-attack resistant dummy hashing, hashed refresh token storage, token rotation
- **CSRF:** Double-submit cookie pattern with `secrets.compare_digest`
- **Cookie security:** `HttpOnly`, `SameSite=Strict`, `Secure` in production
- **Credentials at rest:** Encrypted via Fernet
- **YAML/TOML:** Uses `yaml.safe_load` (via frontmatter) and `tomllib` (safe by design)
- **Production guards:** Fail-fast validation for `SECRET_KEY`, `ADMIN_PASSWORD`, `TRUSTED_HOSTS`
