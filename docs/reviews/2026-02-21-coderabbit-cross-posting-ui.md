# CodeRabbit Review: Cross-Posting UI Branch

**Date**: 2026-02-21
**Tool**: CodeRabbit CLI v0.3.5
**Scope**: All committed changes on `cross-posting-ui` vs `main`

## Findings

### 1. Missing character limit validation for custom_text (Bluesky)

**File**: `backend/crosspost/bluesky.py:68-70`
**Severity**: Potential issue

When `custom_text` is provided, `_build_post_text` returns it verbatim, bypassing the `BSKY_CHAR_LIMIT` (300) truncation logic. If custom text exceeds 300 characters, the Bluesky API will reject the post.

**Fix**: Validate `custom_text` length and raise `ValueError` when over limit.

### 2. Missing character limit validation for custom_text (Mastodon)

**File**: `backend/crosspost/mastodon.py:154-155`
**Severity**: Potential issue

Same issue as #1: `_build_status_text` returns `custom_text` verbatim without checking `MASTODON_CHAR_LIMIT` (500).

**Fix**: Validate `custom_text` length and raise `ValueError` when over limit.

### 3. Potential KeyError if token response is malformed (Mastodon)

**File**: `backend/crosspost/mastodon.py:124-126`
**Severity**: Potential issue

`exchange_mastodon_oauth_token` accesses `token_data["access_token"]` directly. If the Mastodon instance returns 200 but with malformed JSON missing the `access_token` key, this raises an unhandled `KeyError` instead of `MastodonOAuthTokenError`.

**Fix**: Use `token_data.get("access_token")` and raise `MastodonOAuthTokenError` if missing.

### 4. Potential re-render loop in SocialAccountsPanel

**File**: `frontend/src/components/crosspost/SocialAccountsPanel.tsx:46-48`
**Severity**: Suggestion

The `useEffect` depends on `[localBusy, onBusyChange]`. If the parent passes a non-memoized `onBusyChange` callback, the effect fires on every render.

**Fix**: Store `onBusyChange` in a ref, depend only on `localBusy`.

### 5. Effect may reset state on accounts array reference change

**File**: `frontend/src/components/crosspost/CrossPostDialog.tsx:67-79`
**Severity**: Suggestion

The reset effect depends on `accounts`, which could cause re-runs if the parent re-creates the array on each render, resetting user-edited text.

**Fix**: Derive a stable platform list via `useMemo` and use that in the dependency array instead of `accounts`.
