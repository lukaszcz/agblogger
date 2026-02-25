# PR Review: YouTube Iframe Embed Support

**Branch:** `embed-youtube-videos`
**Date:** 2026-02-25
**Review agents:** code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer

## Files Changed

- `backend/config.py` — CSP `frame-src` directive
- `backend/pandoc/renderer.py` — iframe sanitizer logic
- `docs/arch/security.md` — security architecture docs
- `docs/guidelines/security.md` — security guidelines docs
- `docs/plans/2026-02-25-youtube-embed-design.md` — design doc
- `docs/plans/2026-02-25-youtube-embed-plan.md` — implementation plan
- `frontend/src/index.css` — responsive iframe CSS
- `tests/test_rendering/test_sanitizer.py` — YouTube iframe + CSP tests

## Critical Issues (2)

### 1. CSP / Sanitizer regex mismatch on bare domains

**Files:** `backend/pandoc/renderer.py:32-35`, `backend/config.py:79`

The regex `_YOUTUBE_SRC_RE` uses `(?:www\.)?` making `www.` optional, allowing URLs like `https://youtube.com/embed/...` and `https://youtube-nocookie.com/embed/...`. But the CSP `frame-src` only lists `https://www.youtube.com` and `https://www.youtube-nocookie.com`. Per CSP spec, these are different hosts.

**Result:** A user writes `<iframe src="https://youtube.com/embed/dQw4w9WgXcQ">` -- the sanitizer accepts it, the browser blocks it via CSP, and the user sees a broken blank iframe with no explanation.

**Fix (recommended):** Tighten the regex to require `www.`, reducing CSP surface:

```python
r"^https://www\.(?:youtube\.com/(?:embed|shorts)/|youtube-nocookie\.com/embed/)"
```

This also means `test_youtube_without_www_allowed` should change to expect stripping.

### 2. `docs/guidelines/security.md` CSP code block is stale

**File:** `docs/guidelines/security.md:151-155`

The CSP code block in the security guidelines was not updated with the new `frame-src` directive (unlike `docs/arch/security.md` which was). Developers consulting the guidelines would see an incorrect CSP policy.

## Important Issues (4)

### 3. `handle_startendtag` doesn't handle self-closing iframes

**File:** `backend/pandoc/renderer.py:146-154`

XHTML-style `<iframe src="..." />` routes through `handle_startendtag`, which only checks `_ALLOWED_TAGS` (iframe is not in it). Valid YouTube iframes in self-closing form are silently stripped. Not a security issue (fails closed), but a functional gap.

**Fix:** Add iframe guard to `handle_startendtag`:

```python
if tag_name == "iframe":
    self._handle_iframe(attrs)
    return
```

### 4. No test for user-supplied sandbox override attempt

**Criticality:** 9/10

No test verifying that a user who supplies `sandbox="allow-top-navigation allow-forms"` cannot widen permissions. The implementation correctly ignores user attributes, but a regression test would guard against accidental refactoring.

**Suggested test:**

```python
def test_user_sandbox_attribute_cannot_override_forced(self) -> None:
    html = (
        '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"'
        ' sandbox="allow-top-navigation allow-forms"></iframe>'
    )
    result = _sanitize_html(html)
    assert "allow-top-navigation" not in result
    assert "allow-forms" not in result
    assert 'sandbox="allow-scripts allow-same-origin allow-popups"' in result
```

### 5. No test for multiple/mixed iframes in a single document

**Criticality:** 8/10

All tests exercise a single iframe. The `_open_tags` stack-based matching needs testing with mixed valid + invalid iframes to verify state machine correctness.

**Suggested tests:**

```python
def test_mixed_valid_and_invalid_iframes(self) -> None:
    html = (
        '<iframe src="https://evil.com/page"></iframe>'
        '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
    )
    result = _sanitize_html(html)
    assert result.count("<iframe") == 1
    assert result.count("</iframe>") == 1
    assert "evil.com" not in result
    assert "youtube.com" in result

def test_multiple_valid_iframes(self) -> None:
    html = (
        '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
        '<iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe>'
    )
    result = _sanitize_html(html)
    assert result.count("<iframe") == 2
    assert result.count("</iframe>") == 2
```

### 6. Silent stripping with no logging

**File:** `backend/pandoc/renderer.py:206-208`

When an iframe is stripped (e.g., wrong URL format like `/watch?v=` instead of `/embed/`), there's no `logger.debug()` call. Users get zero feedback. Consider adding a debug log for stripped iframes.

## Suggestions (5)

### 7. Test for `youtube-nocookie.com/shorts/` rejection

Regex intentionally disallows this path; add a test documenting the behavior.

### 8. Test for URL with fragment (`#t=30`) rejection

Regex doesn't match fragments; should be tested.

### 9. Test for video ID length boundary (10 or 12 chars)

Regex requires exactly 11 chars; boundary tests would be valuable.

### 10. `docs/arch/security.md:133` — "on all iframes" is ambiguous

Should say "on all allowed iframes" since non-YouTube iframes are stripped entirely.

### 11. Design doc sandbox "Blocked:" implies completeness

Change to "Key capabilities blocked:" since the list is not exhaustive.

## Strengths

- **Defense-in-depth:** Sanitizer regex + CSP `frame-src` + sandbox + forced security attributes
- **Forced-attribute approach:** `_handle_iframe` constructs output from scratch, ignoring all user-supplied attributes
- **HTML escaping of src:** `html.escape(src, quote=True)` prevents attribute breakout attacks
- **Strict regex with `fullmatch`:** Prevents partial-match bypasses, enforces exact 11-char video ID
- **Comprehensive test coverage:** 21 test cases covering happy paths and security abuse vectors (javascript:, data:, path traversal, subdomain attacks, HTTP downgrade)
- **Well-structured sandbox justification** in design doc explaining why each permission is needed

## Recommended Action

1. Fix critical #1 -- tighten regex to require `www.` (or widen CSP)
2. Fix critical #2 -- update `docs/guidelines/security.md` CSP code block
3. Address important #3 -- add iframe handling to `handle_startendtag`
4. Add tests for sandbox override, multiple iframes, and self-closing syntax
5. Consider adding `logger.debug()` for stripped iframes
6. Re-run `just check` after fixes
