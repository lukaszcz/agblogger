# CodeRabbit Review: Bluesky OAuth (Last 10 Commits)

**Date**: 2026-02-21
**Tool**: CodeRabbit CLI v0.3.5
**Scope**: Last 10 commits (`f75c130..e5da59b`) - Bluesky AT Protocol OAuth implementation

## Commits Reviewed

- `e5da59b` update AGENTS.md
- `59e2c0f` docs: add security threat model report
- `0c13636` fix: critical DPoP key mismatch and security hardening
- `1432028` fix: resolve static analysis issues and update architecture docs for Bluesky OAuth
- `c6bbfe8` feat: persist refreshed Bluesky OAuth tokens after cross-posting
- `2952638` feat: add Bluesky OAuth API endpoints (client-metadata, authorize, callback)
- `e58d486` feat: rewrite BlueskyCrossPoster to use AT Protocol OAuth + DPoP
- `ff056a0` feat: add OAuth state store and bluesky_client_url setting
- `f6acd6b` feat: add AT Protocol discovery, PAR, and token exchange
- `fe42fc7` feat: add AT Protocol OAuth crypto helpers (DPoP, PKCE, client assertion)

## Findings

### 1. Overly broad exception handling may delete accounts incorrectly

**File**: `backend/api/crosspost.py:336-343`
**Severity**: Potential Issue

The `except ValueError` block assumes any `ValueError` from `create_social_account` indicates a duplicate account. If `create_social_account` raises `ValueError` for other validation failures (e.g., invalid credentials format), this logic would incorrectly delete the user's existing Bluesky account.

**Fix**: Check the exception message for "already exists" before deleting accounts, or use a more specific exception type.

### 2. Race condition in keypair creation

**File**: `backend/crosspost/atproto_oauth.py:71-81`
**Severity**: Potential Issue (low risk - single startup)

If multiple processes call `load_or_create_keypair` concurrently when the file doesn't exist, both may pass the `path.exists()` check and attempt to create/write the file. This could result in a corrupted file or one process overwriting the other's key.

**Fix**: Use atomic file creation with exclusive mode or a file lock. Write to a temp file then atomically rename.

### 3. Blocking DNS resolution in async context

**File**: `backend/crosspost/atproto_oauth.py:155-168`
**Severity**: Potential Issue

`socket.getaddrinfo` is a synchronous blocking call. When called from async functions like `_resolve_handle_http` or `discover_auth_server`, this can block the entire event loop, degrading performance under load.

**Fix**: Wrap `socket.getaddrinfo` in `asyncio.get_running_loop().run_in_executor()` and make `_is_safe_url` async.

### 4. Missing JSON decode error handling for DPoP nonce

**File**: `backend/crosspost/atproto_oauth.py:322-328`
**Severity**: Potential Issue

If the 400 response body is not valid JSON, `resp.json()` will raise an exception. This could mask the actual error or cause unexpected failures during DPoP nonce rotation handling.

**Fix**: Wrap `resp.json()` in try/except for `JSONDecodeError`.

## Positive Observations

- The OAuth implementation correctly uses all three AT Protocol required extensions (PKCE, PAR, DPoP)
- Token refresh and persistence logic is solid
- Security hardening (SSRF protection via `_is_safe_url`, private IP checks) is well implemented
