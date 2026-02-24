# CodeRabbit Review 2026-02-24

Full codebase review via CodeRabbit CLI v0.3.5.

## Critical / Bugs

1. **`tests/test_services/test_error_handling.py:134`** — Missing `@pytest.mark.asyncio` on `test_get_page_propagates_render_error`. Without auto mode, this async test won't execute.
2. **`backend/crosspost/atproto_oauth.py:104-110`** — `path.unlink()` can raise `FileNotFoundError` in a race condition between `path.exists()` and `path.unlink()`. Should use `missing_ok=True`.
3. **`frontend/src/pages/__tests__/TimelinePage.test.tsx:87-94`** — `simulateFileUpload` has a silent null-dereference risk and `Object.defineProperty` without `configurable: true` prevents redefinition.

## Potential Issues (Tests)

4. **`frontend/src/pages/__tests__/EditorPage.test.tsx:509-517`** — `getByText(/Modified/)` runs outside `waitFor`, risking flaky assertion.
5. **`frontend/src/pages/__tests__/EditorPage.test.tsx:543-563`** — `mockApi.post` not reset between tests; preview tests may see stale call history.
6. **`frontend/src/components/editor/__tests__/LabelInput.test.tsx:147-162`** — Test assumes first dropdown item is auto-highlighted on open (implementation detail, brittle).
7. **`frontend/src/components/editor/__tests__/LabelInput.test.tsx:113`** — `queryByRole('option')` may produce false negative; other assertions use `queryByText`.
8. **`frontend/src/pages/__tests__/AdminPage.test.tsx:9-20`** — `JSON.parse` in mock constructor will throw `SyntaxError` on plain-text response bodies.
9. **`frontend/src/components/crosspost/__tests__/SocialAccountsPanel.test.tsx:283-285`** — `getAllByText('Connect')[0]!` is brittle index-based selector; prefer role-based query. Also applies to lines 309-311, 332-334, 355-357.
10. **`frontend/src/components/share/__tests__/shareUtils.property.test.ts:154-168`** — `console.warn` spy not restored on assertion failure (needs try/finally).
11. **`frontend/src/components/editor/__tests__/wrapSelection.property.test.ts:72-73`** — `startsWith`/`endsWith` checks allow false positives; use exact-position slice comparisons.
12. **`frontend/src/components/__tests__/Header.test.tsx`** — Enter key test may not deliver keystroke to unfocused input.

## Documentation Issues

13. **`docs/pandoc/08-pandocs-markdown.md:1468`** — `<img href=...>` should be `<img src=...>`.
14. **`docs/pandoc/08-pandocs-markdown.md:1155`** — Inconsistent ellipsis (`..` vs `...`) in XWiki formula entry.
15. **`docs/pandoc/08-pandocs-markdown.md:918`** — Wikipedia YAML link is unlinked.
16. **`docs/pandoc/08-pandocs-markdown.md:1151`** — Missing section number on heading.
17. **`docs/pandoc/10-slide-shows.md:51`** — `--self-contained` is deprecated; use `--embed-resources --standalone`.
18. **`docs/arch/sync.md:80`** — Contradictory conflict resolution wording (server-wins vs client-wins).
19. **`docs/arch/testing.md:173`** — StrykerJS version may be outdated (v9.3.0 vs v9.5.1).
20. **`docs/plans/2026-02-23-pandoc-server-design.md:66-67`** — References `RuntimeError` but implementation uses `RenderError`.

## Infrastructure

21. **`justfile:341-363`** — `health` target always checks default ports, ignoring port overrides passed to `start`.
