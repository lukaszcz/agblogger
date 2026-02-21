# X and Facebook Cross-Posting Review (14 commits)

**Branch:** `instagram-x-facebook-linkedin-integration`
**Commits:** 98543e9..e6fb652
**Date:** 2026-02-21

## Critical Issues

### 1. Facebook page picker is non-functional
**`SocialAccountsPanel.tsx`** - `facebookPages` state is initialized as `[]` and never populated. When the Facebook OAuth callback returns multiple pages, the page picker renders empty. There is no endpoint to fetch the page list from the stored state token. This makes multi-page Facebook connections completely broken.

### 2. OAuth callbacks don't handle provider error/denial
**`crosspost.py` (x_callback, facebook_callback)** - Both `code` and `state` are required query params. When a user denies authorization, the provider redirects with `error` and `error_description` instead of `code`, resulting in an incomprehensible 422 validation error. Make `code` optional and handle the `error` query param explicitly.

### 3. Silent fallback to `"unknown"` username for X
**`x.py:86-89`** - `user_data.get("data", {}).get("username", "unknown")` silently creates an account with `@unknown` if the user profile response is malformed. All generated tweet URLs will be wrong. Should raise an error instead.

### 4. Facebook access token sent in request body, may leak into logs
**`facebook.py:125-132`** - The `page_access_token` is in the JSON body. On failure, `resp.text` (which may echo the token) is stored in the `CrossPost.error` field in the database. Violates the project security guideline: "Never log or persist plaintext credentials/tokens." Use `Authorization: Bearer` header instead.

## High Issues

### 5. X token refresh uses inconsistent auth method
**`x.py:139-155`** - `_try_refresh_token()` sends `client_id`/`client_secret` as form data, but `exchange_x_oauth_token()` uses HTTP Basic Auth for the same endpoint. X API docs specify Basic Auth for confidential clients. This inconsistency may cause silent refresh failures in production.

### 6. Facebook callback missing `if not replaced` guard on DuplicateAccountError
**`crosspost.py:810-821, 884-892`** - The Facebook single-page and `select_page` paths don't have the `if not replaced` guard that the X callback correctly implements. If the duplicate is a different account name, the retry `create_social_account` will raise an unhandled `DuplicateAccountError` causing a 500.

### 7. `FacebookCrossPoster.authenticate()` doesn't validate token
**`facebook.py:104-117`** - Unlike X (calls `/2/users/me`) and Mastodon (calls `/api/v1/accounts/verify_credentials`), Facebook just checks if strings are non-empty. Expired/revoked tokens are accepted as valid.

### 8. Silent fallback to short-lived Facebook token
**`facebook.py:70-74`** - If long-lived token exchange returns 200 but with malformed JSON (no `access_token` key), `ll_data.get("access_token", short_token)` silently falls back to the short-lived token that expires in ~1 hour.

## Medium Issues

### 9. `validate_credentials()` catches all errors silently
**`x.py:235-249`, `facebook.py:167-180`** - Both return `False` on any `httpx.HTTPError` with zero logging. Network timeouts, DNS failures, and SSL errors are indistinguishable from invalid credentials.

### 10. Token exchange errors lack response body details
**`x.py:73-89`, `facebook.py:54,72,82`** - Error messages include only HTTP status codes, discarding the detailed error information from the response body that would help debug OAuth issues.

### 11. Frontend error handlers discard platform-specific error details
**`SocialAccountsPanel.tsx:137-176`** - All catch blocks show generic "Failed to start authorization" messages. Backend configuration errors (e.g., missing `X_CLIENT_ID`) are invisible to the user.

### 12. `_try_refresh_token` KeyError catch too broad
**`x.py:161-166`** - Catches `KeyError` alongside `httpx.HTTPError` with the same log message, masking potential programming errors. Use `.get()` with explicit validation instead.

### 13. Facebook page dict structure not validated
**`crosspost.py:790-795, 874`** - Accesses `page["access_token"]` and `page["id"]` without checking keys exist. If Facebook API omits these fields (insufficient permissions), unhandled `KeyError` causes 500.

## CodeRabbit Findings

### CR-1. X tweet text truncation edge case
**`x.py:39-42`** - When `available` space is very small (1-3 chars), `rsplit(" ", maxsplit=1)[0]` could produce awkward single-character excerpts.

### CR-2. Facebook pages state never populated (same as #1)
### CR-3. Missing API endpoint to fetch Facebook pages (same as #1)

## Test Coverage Gaps

### Critical gaps (no tests at all):
- `exchange_x_oauth_token()` - security-sensitive token exchange function
- `exchange_facebook_oauth_token()` - complex three-step flow
- X callback happy path (valid state + account creation)
- Facebook callback happy path (single-page auto-select, multi-page redirect)

### Important gaps:
- Frontend `SocialAccountsPanel` tests don't mock `authorizeX`, `authorizeFacebook`, `selectFacebookPage`
- `CrossPostDialog` tests don't include X (280 char) or Facebook (no limit) accounts
- `XCrossPoster.post()` error paths (rate limit, network error, failed refresh)
- `FacebookCrossPoster.post()` error paths
- `validate_credentials()` for both platforms

## Positive Observations

- Text formatting tests are thorough for both platforms (7 tests total)
- API auth guard tests cover all new endpoints
- Platform registry correctly updated
- X token refresh test is well-designed (401-refresh-retry cycle)
- PKCE correctly implemented for X
- OAuth state store uses TTL with cleanup
- Existing patterns (Bluesky/Mastodon) are followed consistently
- Configuration tests verify new settings defaults
- ARCHITECTURE.md kept in sync
