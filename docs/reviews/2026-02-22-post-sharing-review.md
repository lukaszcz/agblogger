# PR Review: Client-Side Post Sharing (8 commits)

**Date**: 2026-02-21
**Branch**: sharing-posts
**Scope**: 13 files changed, +1221 lines. Frontend-only feature adding share buttons (Bluesky, Mastodon, X, Facebook, LinkedIn, Reddit, Email, Copy Link, native share API) to the post page, available to all users including unauthenticated visitors.

## Critical Issues (1 found)

### 1. Mastodon instance URL not validated before interpolation — potential open redirect

**[code-reviewer]** `frontend/src/components/share/shareUtils.ts:22`

The `mastodonInstance` value is user-provided, stored in localStorage, and interpolated directly into a URL:

```typescript
return `https://${mastodonInstance}/share?text=${encodeURIComponent(text)}`
```

A user could enter `evil.com/phishing#` producing `https://evil.com/phishing#/share?text=...`. The backend Mastodon OAuth flow has `_normalize_instance_url()` for SSRF protection, but the client-side share has no equivalent validation.

**Fix**: Validate the instance string — reject values containing `/`, `?`, `#`, `@`, or whitespace. A hostname regex like `/^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$/` would suffice.

## Important Issues (5 found)

### 2. Duplicated `PLATFORMS` constant — CLAUDE.md violation

**[code-reviewer]** `ShareButton.tsx:22-29` and `ShareBar.tsx:22-29`

Identical `PLATFORMS` array defined in both files. CLAUDE.md says: "Avoid code duplication. Abstract common logic into parameterized functions."

**Fix**: Move to `shareUtils.ts`, export once, import in both components.

### 3. Clipboard copy failure provides zero user feedback

**[silent-failure-hunter]** `shareUtils.ts:46-53`, `ShareButton.tsx:91`, `ShareBar.tsx:61`

`copyToClipboard` returns `false` on failure, but callers do nothing with the failure case — no visual feedback, no error message. The user clicks "Copy link" and nothing visibly happens. Can fail due to `DOMException: Document is not focused`, `NotAllowedError`, or non-HTTPS contexts.

**Fix**: Add a failure state to callers (e.g., show "Copy failed" text briefly).

### 4. `localStorage` access unprotected — crashes in restrictive browsers

**[silent-failure-hunter]** `shareUtils.ts:55-61`, `MastodonSharePrompt.tsx:11`

`localStorage.getItem()`/`setItem()` can throw `SecurityError` in Safari private browsing (older versions), disabled storage, or sandboxed iframes. The `getMastodonInstance()` call during component initialization (`useState`) would crash the MastodonSharePrompt component.

**Fix**: Wrap localStorage access in try-catch. Return `null` on failure for `get`, silently handle `set`.

### 5. `<label>` not associated with `<input>` — accessibility issue

**[code-reviewer]** `MastodonSharePrompt.tsx:24-35`

The `<label>` is not programmatically associated with the text input (missing `htmlFor`/`id`). Other components in the codebase (e.g., `SocialAccountsPanel.tsx`) use `htmlFor` properly.

**Fix**: Add `htmlFor="mastodon-instance"` to `<label>` and `id="mastodon-instance"` to `<input>`.

### 6. `window.location.href` may include query params/fragments in shared URLs

**[code-reviewer]** `PostPage.tsx:138, 179`

If the URL has `?q=...` or `#section`, those get included in the share URL. Users expect clean canonical URLs.

**Fix**: Construct from route path: `` `${window.location.origin}/post/${filePath}` ``

## Suggestions (7 found)

### 7. Native share catch blocks are overly broad

**[silent-failure-hunter]** `ShareButton.tsx:55-59`, `ShareBar.tsx:71-75`

The catch blocks treat all errors as "user cancelled." They should differentiate `AbortError` (user cancel) from `NotAllowedError`/`TypeError` (actual failures). For `ShareButton`, falling back to the dropdown on non-cancel errors would improve UX.

### 8. `getShareUrl` unknown platform — no developer signal

**[silent-failure-hunter, test-analyzer]** `shareUtils.ts:35`

The `default` case returns `''` silently. If a developer adds a platform to `PLATFORMS` but forgets the switch case, nothing happens. Add `console.warn` in the default case.

### 9. ARCHITECTURE.md minor inaccuracies

**[comment-analyzer]**

- States "each platform button opens a pre-filled compose URL in a new tab" — Email uses `_self`, Copy Link doesn't open a URL
- Share text format documentation doesn't clearly describe the null-author variant

### 10. Inconsistent catch-block comments

**[comment-analyzer]** `ShareButton.tsx:58` says `// User cancelled`, `ShareBar.tsx:74` says `// User cancelled or share failed -- no action needed`. Both do the same thing but document it differently.

### 11. localStorage mock duplicated across 4 test files

**[test-analyzer]** All 4 share test files have identical 15-line localStorage mock boilerplate. Consider extracting to a shared test utility.

### 12. Missing test: MastodonSharePrompt Enter key submission

**[test-analyzer]** The `onKeyDown` handler for Enter is untested. If removed, keyboard submission breaks silently.

### 13. Missing tests: email share and copy link in ShareButton dropdown

**[test-analyzer]** Email click handler (`_self` target) and copy-with-feedback are tested in ShareBar but not ShareButton. Since they're independent implementations, both need coverage.

## Strengths

- **Well-structured architecture**: Clean separation between `shareUtils.ts` (logic), components (UI), and clear distinction from server-side cross-posting
- **Excellent test quality**: Tests use accessible queries (`getByLabelText`, `getByRole`), test both native-share and fallback paths, and cover the Mastodon two-path flow well
- **Good documentation**: ARCHITECTURE.md clearly explains the feature and its distinction from cross-posting
- **Proper patterns**: PascalCase components, camelCase utilities, Tailwind semantic tokens, testing-library conventions all followed
