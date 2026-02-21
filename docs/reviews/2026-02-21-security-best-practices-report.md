# Security Best Practices Report - AgBlogger

Date: 2026-02-21
Reviewer: Codex (using `security-best-practices` skill)

## Executive Summary

I reviewed backend and frontend security controls using FastAPI and React security guidance, plus automated scans.

Automated checks:
- `just check-semgrep`: passed (no findings)
- `uv run pip-audit`: no known vulnerabilities
- `npm audit --omit=dev`: no known vulnerabilities

Manual review found **4 actionable findings**:
- 2 High
- 1 Medium
- 1 Low

I also found 1 authorization design risk to confirm with product requirements.

## High Severity Findings

### SBP-001: Draft confidentiality bypass for flat-file drafts in content API
- Severity: High
- Location: `backend/api/content.py:73`, `backend/api/content.py:123`
- Impact: Unauthenticated or non-author users can read draft markdown files stored directly under `posts/` (legacy flat-file drafts), bypassing draft privacy guarantees.
- Evidence:
```python
# backend/api/content.py
if len(parts) < 3:
    # File directly under posts/, e.g. "posts/hello.md" — not a directory post
    return
...
await _check_draft_access(file_path, session, user)
```
- Why this is vulnerable: draft enforcement only applies to paths like `posts/<dir>/<file>`. Flat files like `posts/admin-draft.md` skip checks entirely.
- Fix:
1. Add a draft lookup path for flat files (exact `PostCache.file_path == file_path`) in `_check_draft_access`.
2. Apply the same author-only rule used in `backend/api/posts.py:371`.
- Mitigation: Block direct serving of `.md` under `posts/` unless explicitly public.

### SBP-002: Crosspost endpoint can exfiltrate drafts by path
- Severity: High
- Location: `backend/services/crosspost_service.py:102`, `backend/api/crosspost.py:99`
- Impact: Any authenticated user can attempt to cross-post any readable post path (including another author's draft), leaking draft excerpt/title to external platforms.
- Evidence:
```python
# backend/services/crosspost_service.py
post_data = content_manager.read_post(post_path)
...
excerpt = content_manager.get_plain_excerpt(post_data)
```
```python
# backend/api/crosspost.py
user: Annotated[User, Depends(require_auth)]
```
- Why this is vulnerable: no authorization check ties `post_path` visibility to requesting user; it reads from filesystem directly.
- Fix:
1. Resolve post via cached post metadata and enforce draft/author visibility before crossposting.
2. Return `404` for unauthorized draft access to avoid existence leaks.
3. Add regression tests for crossposting someone else’s draft.
- Mitigation: Temporarily restrict crosspost to admin only until ownership checks are implemented.

## Medium Severity Findings

### SBP-003: SSRF risk via unvalidated Mastodon `instance_url`
- Severity: Medium
- Location: `backend/schemas/crosspost.py:13`, `backend/crosspost/mastodon.py:59`, `backend/crosspost/mastodon.py:69`
- Impact: Authenticated users can force server-side HTTP requests to arbitrary hosts (including internal network endpoints), enabling SSRF and internal service probing.
- Evidence:
```python
# backend/schemas/crosspost.py
credentials: dict[str, str]
```
```python
# backend/crosspost/mastodon.py
instance_url = credentials.get("instance_url", "").rstrip("/")
resp = await client.get(f"{instance_url}/api/v1/accounts/verify_credentials", ...)
```
- Fix:
1. Validate `instance_url` against `https` scheme and DNS-resolved public IP ranges only.
2. Reject localhost, RFC1918, link-local, and metadata endpoints.
3. Consider an allowlist mode if deployments expect known instances only.
- Mitigation: Outbound egress filtering at network layer.

## Low Severity Findings

### SBP-004: Registration password policy is weak (minimum length 6)
- Severity: Low
- Location: `backend/schemas/auth.py:26`
- Impact: Allows weak passwords that increase account compromise risk under credential stuffing or password reuse.
- Evidence:
```python
password: str = Field(min_length=6, max_length=200)
```
- Fix:
1. Raise minimum to at least 12 for human-chosen passwords.
2. Optionally enforce breached-password checks and basic complexity guidance.
- Mitigation: Keep strict rate limiting and invite-only registration enabled.

## Authorization Design Risk (Confirm Intent)

### ADR-001: Any authenticated user can update/delete any post
- Severity: Risk acceptance decision needed
- Location: `backend/api/posts.py:472`, `backend/api/posts.py:611`, `docs/ARCHITECTURE.md:278`
- Observation: Update/delete routes require authentication but do not enforce author ownership.
- Evidence:
```python
# backend/api/posts.py
user: Annotated[User, Depends(require_auth)]
```
The documented role model currently states authenticated users can create/edit/delete posts globally.
- Risk: If multi-author isolation is expected, one compromised non-admin account can deface or delete all content.
- Recommendation: Confirm intended model. If per-author ownership is desired, enforce `post.author == current_user` (with optional admin override).

## Suggested Next Steps

1. Fix SBP-001 and SBP-002 first; they are direct confidentiality issues.
2. Add regression tests for both bypasses in `tests/test_api/test_security_regressions.py`.
3. Implement SSRF controls for Mastodon `instance_url` and add unit tests for blocked internal targets.
4. Decide on ADR-001 authorization model and align API behavior + architecture docs.
