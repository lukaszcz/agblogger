# Repository Guidelines

AgBlogger is a markdown-first blogging platform where markdown files with YAML front matter are the source of truth for all post content and metadata.

## Architecture

**IMPORTANT** Read @docs/arch/index.md for architecture overview. **ALWAYS** read ALL files under docs/arch/ that are relevant to your current task. Read other files in docs/arch/ when you need deeper understanding of application architecture. Update docs/arch/*.md (all relevant files) whenever architecture changes – always keep these files up-to-date with the codebase.

## Build, Test, and Development Commands

```bash
just start            # Start backend (:8000) + frontend (:5173) in the background
just stop             # Stop the running dev server
just start backend_port=9000 frontend_port=9173  # Custom ports
just check            # Full gate: static checks first, then tests
just check-static     # Static-only gate: backend + frontend + Semgrep + Vulture + Trivy
just test             # Test-only gate: backend + frontend tests
just check-backend    # Backend static checks + backend tests
just check-backend-static  # Backend static checks only
just test-backend     # Backend tests only
just check-frontend   # Frontend static checks + frontend tests
just check-frontend-static # Frontend static checks only
just test-frontend    # Frontend tests only
just check-semgrep    # Semgrep SAST
```

Always start a dev server with `just start`. Remember to stop a running dev server with `just stop` when finished.

## Coding Style & Naming Conventions

### Python (backend/, cli/, tests/)

- Formatting: ruff (line length 100)
- Linting: ruff + import-linter
- Typing: strict discipline (`mypy` strict + `basedpyright`); modern union syntax (`str | None`, `dict[str, Any]`, `list[str]`)
- Do NOT use `type: ignore` comments. If ignoring a type rule is necessary, ALWAYS ask the user for permission and explain why it is necessary.
- Do NOT use `noqa` comment. If ignoring a lint rule is necessary, ALWAYS ask the user for permission and explain why it is necessary.
- Naming & style: `snake_case` files/functions/variables, `PascalCase` classes; `from __future__ import annotations` everywhere; `async def` for all I/O; follow existing Pydantic/SQLAlchemy/FastAPI patterns in the codebase

### TypeScript (frontend/src/)

- Formatting: ESLint with typescript-eslint (type-checked rules); avoid `eslint-disable-line`
- Static hygiene: keep dependency-cruiser and knip checks passing
- Naming & style: `PascalCase.tsx` components, `camelCase.ts` utilities/stores; `PascalCase` types/interfaces, `fetch` prefix for API functions, `handle` prefix for event handlers; Tailwind with semantic color tokens; follow existing patterns in the codebase

## Testing Guidelines

- **IMPORTANT**: Every new feature should include tests that verify its correctness at the appropriate levels (unit, integration, and possibly system level).
- **IMPORTANT**: Follow Test Driven Development (TDD). Write failing tests first, implement changes later to make the tests pass.
- **IMPORTANT**: For every bug found, add a regression test that fails because of the bug, then fix the bug and ensure the test passes.
- Use property-based testing (Hypothesis, fast-check) for deterministic logic. Abstract high-invariant logic into independent pure functions to enable property-based testing.
- Avoid brittle tests. Test user workflows, not implementation details.
- Coverage targets 80%, branches 70%.

### Backend (pytest)

- Structure: `tests/test_<category>/test_<module>.py`; `Test` prefix classes; descriptive `test_<what>()` functions
- All tests are async (`asyncio_mode = "auto"`); fixtures in `conftest.py` with async generators
- API tests use `httpx.AsyncClient` with `ASGITransport`; plain `assert` statements

### Frontend (Vitest)

- jsdom environment with `@testing-library/react` and `@testing-library/user-event`
- Test files colocated or in `__tests__/` directories
- Use `render()`, `screen`, `userEvent` from testing-library

## Commit & Pull Request Guidelines

- Commit format: `type: subject` in imperative lowercase (e.g., `feat: add transfer flow`).
- PR title format same as commit format (`type: subject`).
- PR descriptions should summarize changes, rationale and impact. Do not summarize validation or testing. Unless the PR updates documentation only, do not describe documentation changes.
- Keep commits focused; avoid mixing unrelated changes.
- Use `git add`, `git commit`, `git merge`, etc. Do NOT use the `-C` option with `git`.

## Security Guidelines

- All exceptions need to be handled gracefully, especially errors originating from interaction with external services (network, database, pandoc, git, filesystem). Never silently ignore exceptions.
- Never expose internal server error details to clients. Return a generic error message to clients while keeping detailed logging server-side.
- Treat authentication as a coupled system. If you touch login/refresh/logout or cookies, update backend token logic, CSRF middleware, and frontend CSRF header persistence together; do not change one side in isolation.
- Preserve production fail-fast guards in `Settings.validate_runtime_security()` (`SECRET_KEY`, `ADMIN_PASSWORD`, `TRUSTED_HOSTS`). Do not bypass them outside explicit debug/test scenarios.
- Keep auth abuse protections intact: login origin enforcement, failed-attempt rate limiting, hashed refresh token storage, and refresh-token rotation with old-token revocation.
- Use dependency-based authorization (`require_auth`, `require_admin`, `get_current_user`) for protected endpoints. Avoid ad-hoc inline auth checks inside handlers.
- Never log or persist plaintext credentials/tokens. This includes passwords, refresh tokens, PATs, invite codes, and third-party OAuth credentials.
- Cross-post account credentials must remain encrypted at rest via `crypto_service`; do not store raw JSON credentials in DB writes or migrations.
- Keep cookie security defaults intact: `HttpOnly`, `SameSite=Strict`, `Secure` outside debug, and CSRF validation for unsafe `/api/` methods when cookie auth is used.
- Preserve trust-boundary controls (`TrustedHostMiddleware`, strict CORS origins, trusted proxy IP handling). Do not introduce wildcard-style permissive production defaults.
- For file-serving or path logic changes, maintain traversal protections and draft asset access controls in `/api/content`; add regression tests for traversal and unauthorized draft access.
- For markdown/rendering changes, keep HTML sanitization and safe URL-scheme filtering in place before content is stored or served.
- Any security-sensitive bug fix or feature change must include failing-first regression tests that cover abuse paths, not only happy paths.

## Instructions

- **IMPORTANT**: Keep ALL files under docs/arch/ in sync with the codebase. Update them after any frontend or backend architecture changes, addition of major new features, workflow changes.
- Avoid code duplication. Abstract common logic into parameterized functions.
- Use the frontend-design skill to design the user interface and user experience.
- Ensure the application works end-to-end. Use the playwright mcp to test in the browser.
- While waiting on an async operation, UI controls should **ALWAYS** be disabled.
- Do NOT try to circumvent static analysis tools. Adapt the code to pass `just check` properly - do not ignore checks or suppress rules. If you absolutely need to bypass a static analysis tool, ALWAYS ask the user for approval and explain why this is necessary.
- When finished browser testing, remove any leftover *.png screenshot files.
- When finished, verify with `just check`.
