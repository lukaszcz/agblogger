# Security Remediation Report - AgBlogger

Date: 2026-02-20  
Reviewer: Codex

## Scope and Assumptions

- Reviewed and remediated backend security issues under the assumption that infrastructure controls may be absent or misconfigured.
- Authorization model now treats authenticated users and admins as different roles.
- Report covers application-layer hardening in this repository.

## Executive Summary

All previously documented findings were addressed in code and validated with tests:

- 2 Critical fixed
- 4 High fixed
- 2 Medium fixed
- 1 Low fixed

Validation status:

- `uv run pytest tests/test_api/test_security_regressions.py -q`: **9 passed**
- `just check`: **passed** (backend + frontend checks, backend `405` tests, frontend `114` tests)

## Findings and Remediation Status

### [C-001] Sync authorization boundary bypass

- Status: **Fixed**
- Change: Sync endpoints now require admin role (`require_admin`) instead of generic authenticated user.
- Files:
  - `backend/api/sync.py`

### [C-002] Stored XSS via rendered markdown/html

- Status: **Fixed**
- Change: Added allowlist HTML sanitizer in renderer; unsafe tags/attrs/schemes are stripped before persistence/serving.
- Files:
  - `backend/pandoc/renderer.py`

### [H-001] Arbitrary file read via page path traversal

- Status: **Fixed**
- Change: Page file paths are validated through safe path checks before read/update/delete operations.
- Files:
  - `backend/filesystem/content_manager.py`
  - `backend/services/admin_service.py`

### [H-002] Draft posts publicly readable by direct path

- Status: **Fixed**
- Change: Unauthenticated reads of draft posts now return `404`.
- Files:
  - `backend/api/posts.py`

### [H-003] Insecure production defaults / weak startup posture

- Status: **Fixed**
- Change:
  - Added runtime security validation to fail startup in production with default/weak secrets.
  - Removed insecure compose fallbacks and hardened `.env.example`.
  - Added trusted host and related hardening settings.
- Files:
  - `backend/config.py`
  - `backend/main.py`
  - `docker-compose.yml`
  - `.env.example`

### [H-004] Cross-user data exposure in crosspost history

- Status: **Fixed**
- Change:
  - Added `user_id` ownership to crosspost records.
  - Scoped history queries by `(post_path, user_id)`.
  - Added runtime schema-compatibility hook for existing DBs.
- Files:
  - `backend/models/crosspost.py`
  - `backend/models/user.py`
  - `backend/services/crosspost_service.py`
  - `backend/api/crosspost.py`
  - `backend/main.py`

### [M-001] Login CSRF/session confusion

- Status: **Fixed**
- Change: Enforced login `Origin`/`Referer` checks against trusted origins.
- Files:
  - `backend/api/auth.py`

### [M-002] X-Forwarded-For spoofing weakens rate limiting

- Status: **Fixed**
- Change: Forwarded IP headers are trusted only from configured proxy IPs.
- Files:
  - `backend/api/auth.py`
  - `backend/config.py`

### [L-001] Missing in-app hardening defaults (docs/hosts/headers)

- Status: **Fixed**
- Change:
  - Added Trusted Host enforcement.
  - Added default security headers middleware.
  - Disabled docs/openapi by default outside debug unless explicitly enabled.
- Files:
  - `backend/main.py`
  - `backend/config.py`

## Regression Tests Added

Added `tests/test_api/test_security_regressions.py` to cover:

1. Non-admin denied sync init.
2. Render preview sanitization (`<script>`, `javascript:`).
3. Draft post hidden from unauthenticated readers.
4. Crosspost history owner isolation.
5. Page traversal blocked.
6. Login origin validation.
7. Untrusted `X-Forwarded-For` cannot bypass rate limit.
8. Production hardening defaults (docs disabled, security headers, trusted host enforcement).
9. Production startup rejection for insecure default secrets.

## Architecture Documentation Sync

`docs/ARCHITECTURE.md` was updated to reflect:

- Admin-only sync boundaries.
- Trusted host/security header/docs exposure controls.
- Startup runtime security validation.
- Owner-scoped crosspost history model.
- Login origin enforcement and trusted proxy handling.

