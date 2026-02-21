# Repository Guidelines

AgBlogger is a markdown-first blogging platform where markdown files with YAML front matter are the source of truth for all post content and metadata.

## Architecture

**IMPORTANT**: Read @docs/ARCHITECTURE.md to understand application architecture. Update docs/ARCHITECTURE.md whenever architecture changes – always keep it up-to-date with the codebase.

## Build, Test, and Development Commands

```bash
just start            # Start backend (:8000) + frontend (:5173) in the background
just stop             # Stop the running dev server
just start backend_port=9000 frontend_port=9173  # Custom ports
just check            # Full gate: backend + frontend + Semgrep + Vulture
just check-backend    # mypy, basedpyright, deptry, import-linter, ruff, pip-audit, pytest
just check-frontend   # tsc, eslint, dependency-cruiser, knip, npm audit, vitest
just check-semgrep    # Semgrep SAST (p/ci, p/security-audit, p/secrets, p/python, p/typescript + local rules)
just check-vulture    # Vulture dead-code analysis for backend/ and cli/
```

Always start a dev server with `just start`. Remember to stop a running dev server with `just stop` when finished.

## Coding Style & Naming Conventions

### Python (backend/, cli/, tests/)

- Formatting: ruff (line length 100)
- Linting: ruff + import-linter; avoid `noqa` comments
- Typing: strict discipline (`mypy` strict + `basedpyright`); avoid `type: ignore` comments; modern union syntax (`str | None`, `dict[str, Any]`, `list[str]`); `Annotated` for FastAPI dependencies
- Naming & style: `snake_case` files/functions/variables, `PascalCase` classes; `from __future__ import annotations` everywhere; `async def` for all I/O; follow existing Pydantic/SQLAlchemy/FastAPI patterns in the codebase

### TypeScript (frontend/src/)

- Formatting: ESLint with typescript-eslint (type-checked rules); avoid `eslint-disable-line`
- Static hygiene: keep dependency-cruiser and knip checks passing
- Naming & style: `PascalCase.tsx` components, `camelCase.ts` utilities/stores; `PascalCase` types/interfaces, `fetch` prefix for API functions, `handle` prefix for event handlers; Tailwind with semantic color tokens; follow existing patterns in the codebase

## Testing Guidelines

- **IMPORTANT**: Every new feature should include tests that verify its correctness at the appropriate levels (unit, integration, and possibly system level).
- **IMPORTANT**: Follow Test Driven Development (TDD). Write failing tests first, implement changes later to make the tests pass.
- **IMPORTANT**: For every bug found, add a regression test that fails because of the bug, then fix the bug and ensure the test passes.
- Test warnings are treated as errors (`filterwarnings = ["error"]`), so tests must run warning-free.
- Avoid brittle tests. Test user workflows, not implementation details.
- Don't leak expected error output into test run output.

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
- Use `git add`, `git commit`, `git merge`, etc. Do NOT use `-C` option with `git`.

## Security Guidelines

- Secrets: stored in `.env` (never committed); loaded via `pydantic-settings` `Settings` class
- Passwords: bcrypt hashed; never stored or logged in plaintext
- JWT: access tokens (15 min, HS256), refresh tokens (7 days, random 48-byte string hashed with SHA-256 in DB); rotation on refresh revokes old tokens
- Input validation: all request bodies validated by Pydantic models with `Field()` constraints; query params validated via `Query()`
- No hardcoded secrets: default values in `Settings` are development-only; production must override via environment
- CORS: configured in `main.py` middleware
- Static files: served via FastAPI `StaticFiles`; Caddy adds `Cache-Control: immutable` in production

## Instructions

- **IMPORTANT**: Keep docs/ARCHITECTURE.md in sync with the codebase. Update it after any frontend or backend architecture changes, addition of major new features, database schema updates.
- Avoid code duplication. Abstract common logic into parameterized functions.
- Use the frontend-design skill to design the user interface and user experience.
- Ensure the application works end-to-end. Use the playwright mcp to test in the browser.
- While waiting on an async operation, UI controls should **ALWAYS** be disabled.
- Do NOT try to circumvent static analysis tools. Adapt the code to pass `just check` properly - do not ignore checks or suppress rules. If you absolutely need to bypass a static analysis tool, ALWAYS ask the user for approval and explain why this is necessary.
- When finished browser testing, remove any leftover *.png screenshot files.
- When finished, verify with `just check`.
