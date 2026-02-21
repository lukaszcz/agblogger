# Bluesky AT Protocol OAuth Design

## Problem

The current Bluesky cross-posting implementation stores the user's username and password (encrypted at rest). This is a security concern: the password grants full account access, may be reused elsewhere, and is recoverable if the encryption key is compromised. AT Protocol now supports OAuth, which provides scoped, revocable tokens.

## Solution

Replace Bluesky's username+password authentication with AT Protocol OAuth using the confidential client (Backend For Frontend) pattern. AgBlogger acts as a server-side OAuth client with its own ES256 keypair for identity.

## OAuth Flow

```
1. User clicks "Connect Bluesky" → enters their Bluesky handle
2. POST /api/crosspost/bluesky/authorize { handle: "user.bsky.social" }
   → Backend resolves handle to DID
   → Backend discovers authorization server via PDS metadata
   → Backend generates PKCE verifier + challenge (S256)
   → Backend generates DPoP proof (ES256 JWT)
   → Backend sends PAR request with client assertion
   → Backend stores auth state (PKCE verifier, DPoP key, auth server URL) in session
   → Returns { authorization_url: "https://bsky.social/oauth/authorize?request_uri=..." }
3. Frontend redirects user to authorization_url
4. User approves on Bluesky's auth page
5. Bluesky redirects to GET /api/crosspost/bluesky/callback?code=...&state=...&iss=...
   → Backend retrieves stored auth state by state parameter
   → Backend exchanges code for tokens (access_token + refresh_token)
     with PKCE verifier + client assertion + DPoP proof
   → Tokens + DPoP private key + metadata stored encrypted in SocialAccount
   → Redirects user back to app UI
```

## AT Protocol OAuth Requirements

### Mandatory Extensions

All three are required by the AT Protocol OAuth spec:

- **PKCE (S256)**: Generate 48 random bytes as verifier, SHA-256 hash as challenge
- **PAR**: Push all auth params to the PAR endpoint, receive request_uri
- **DPoP**: Every token request and API call includes an ES256-signed JWT proof binding the token to the client

### Confidential Client Identity

AgBlogger is a confidential client (server-side web service):

- An ES256 keypair is generated on first startup, stored at `{content_dir}/.atproto-oauth-key.json`
- The public key is served in the client metadata document
- The private key signs client assertion JWTs for token requests
- Client authenticates via `private_key_jwt` method

### Client Metadata

Served at `GET /api/crosspost/bluesky/client-metadata.json`:

```json
{
  "client_id": "https://example.com/api/crosspost/bluesky/client-metadata.json",
  "client_name": "AgBlogger",
  "client_uri": "https://example.com",
  "grant_types": ["authorization_code", "refresh_token"],
  "scope": "atproto transition:generic",
  "response_types": ["code"],
  "redirect_uris": ["https://example.com/api/crosspost/bluesky/callback"],
  "dpop_bound_access_tokens": true,
  "application_type": "web",
  "token_endpoint_auth_method": "private_key_jwt",
  "token_endpoint_auth_signing_alg": "ES256",
  "jwks": { "keys": [{ ... ES256 public key ... }] }
}
```

The `client_id` URL is constructed from a new `BLUESKY_CLIENT_URL` setting (the public base URL of the AgBlogger instance, e.g. `https://myblog.example.com`).

### Authorization Server Discovery

1. Resolve handle to DID (via DNS TXT `_atproto.handle` or HTTP `/.well-known/atproto-did`)
2. Resolve DID to DID document (via `plc.directory` for did:plc, or HTTP for did:web)
3. Extract PDS URL from DID document `#atproto_pds` service endpoint
4. Fetch `{pds}/.well-known/oauth-protected-resource` to find authorization server
5. Fetch `{authserver}/.well-known/oauth-authorization-server` for endpoints

### DPoP Proof Structure

```json
{
  "typ": "dpop+jwt",
  "alg": "ES256",
  "jwk": { "...public key..." }
}
{
  "jti": "<unique-id>",
  "htm": "POST",
  "htu": "https://bsky.social/oauth/token",
  "iat": 1708000000,
  "nonce": "<server-provided>"
}
```

For resource server (PDS) requests, add `ath` (base64url SHA-256 of access token).

### Token Lifecycle

- Access tokens: short-lived, DPoP-bound
- Refresh tokens: up to 3 months for confidential clients
- On expiry: automatic refresh using stored refresh_token + DPoP key
- Nonce rotation: server may return new DPoP nonce in response headers

## Components

### New File: `backend/crosspost/atproto_oauth.py`

OAuth helper module with pure functions:

- `generate_dpop_key()` → ES256 JWK keypair
- `create_dpop_proof(method, url, key, nonce, ath?)` → signed DPoP JWT
- `create_client_assertion(client_id, aud, key)` → signed client assertion JWT
- `create_pkce_challenge()` → (verifier, challenge)
- `resolve_handle_to_did(handle)` → DID string
- `resolve_did_to_doc(did)` → DID document
- `discover_auth_server(pds_url)` → auth server metadata
- `send_par_request(...)` → (request_uri, state)
- `exchange_code_for_tokens(...)` → token response
- `refresh_tokens(...)` → new token response
- `make_dpop_request(method, url, access_token, dpop_key, nonce)` → httpx response with DPoP

All HTTP calls include SSRF protection (reject private/loopback IPs).

### New File: `backend/crosspost/bluesky_oauth_state.py`

Temporary in-memory store for pending OAuth flows:

- Maps `state` → `{pkce_verifier, dpop_key, auth_server_url, dpop_nonce, user_id, created_at}`
- Entries expire after 10 minutes
- Cleared on successful callback

### Modified: `backend/crosspost/bluesky.py`

`BlueskyCrossPoster` rewritten:

- `authenticate()` accepts credentials dict with `access_token`, `refresh_token`, `dpop_key`, `dpop_nonce`, `pds_url`, `did`
- `post()` creates a DPoP proof per request, uses `Authorization: DPoP <access_token>`
- Handles token refresh automatically when access token is expired (401 response)
- Returns updated credentials (new tokens/nonce) via a new mechanism so they can be persisted

### Modified: `backend/api/crosspost.py`

New endpoints:

- `GET /api/crosspost/bluesky/client-metadata.json` — public, serves client metadata
- `POST /api/crosspost/bluesky/authorize` — auth required, takes `{handle}`, returns `{authorization_url}`
- `GET /api/crosspost/bluesky/callback` — handles OAuth callback, stores tokens, redirects to UI

The existing `POST /api/crosspost/accounts` endpoint remains for Mastodon (which uses direct token input). For Bluesky, account creation happens in the callback.

### Modified: `backend/config.py`

New setting:

- `bluesky_client_url: str = ""` — Public base URL for OAuth client_id (e.g. `https://myblog.example.com`). Required for Bluesky cross-posting.

### Modified: `backend/services/crosspost_service.py`

- `crosspost()` updated: after a successful Bluesky post, if tokens were refreshed during the request, update the stored encrypted credentials with the new tokens
- Bluesky credential decryption now expects the OAuth token format

### Modified: `backend/schemas/crosspost.py`

New schemas:

- `BlueskyAuthorizeRequest` — `{ handle: str }`
- `BlueskyAuthorizeResponse` — `{ authorization_url: str }`

### Modified: `backend/main.py`

On startup:

- Generate ES256 keypair if not present at `{content_dir}/.atproto-oauth-key.json`
- Store keypair in `app.state.atproto_oauth_key`

### ES256 Key Storage

The keypair is stored as a JWK JSON file at `{content_dir}/.atproto-oauth-key.json`. This file is:

- Created on first startup if it doesn't exist
- Read-only after creation
- Excluded from sync (not under `posts/` or `assets/`)
- Contains both private and public key material

## Dependencies

New Python dependency: `authlib` — provides JWT encoding/decoding, PKCE utilities, and JWK support. Already well-maintained and widely used.

No need for a separate `jwcrypto` dependency — `authlib` covers all cryptographic needs (ES256 signing, JWK generation, JWT creation).

## Migration

Existing Bluesky `SocialAccount` entries (with username+password credentials) will fail to authenticate after this change. Users will need to reconnect their Bluesky account using the new OAuth flow. The old `createSession` code path is removed entirely.

## Testing

- Unit tests for DPoP proof generation, PKCE, client assertion creation
- Unit tests for handle/DID resolution with mocked HTTP responses
- Unit tests for PAR, token exchange, token refresh with mocked responses
- Integration tests for the authorize/callback flow with mocked Bluesky endpoints
- Existing cross-post formatting tests (`_build_post_text`, `_find_facets`) remain unchanged

## Security Properties

- No passwords stored — only scoped, revocable OAuth tokens
- DPoP binding — stolen tokens are useless without the corresponding DPoP private key
- Confidential client — Bluesky's auth server verifies AgBlogger's identity
- PKCE — prevents authorization code interception
- PAR — authorization parameters are not exposed in browser URL
- SSRF protection — all external HTTP calls validate against private/loopback IPs
- Encrypted at rest — tokens encrypted with Fernet (same as existing credential storage)
