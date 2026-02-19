# Repository Guidelines

AgBlogger is a markdown-first blogging platform where markdown files with YAML front matter are the source of truth for all post content and metadata.

## Architecture

**IMPORTANT**: Read @docs/ARCHITECTURE.md to understand application architecture. Update docs/ARCHITECTURE.md whenever architecture changes – always keep it up-to-date with the codebase.

## Build, Test, and Development Commands

```bash
just start            # Start backend (:8000) + frontend (:5173) in the background
just stop             # Stop the running dev server
just start backend_port=9000 frontend_port=9173  # Custom ports
just check            # Run all type checking, linting, format checks, and tests
just check-backend    # Backend only: mypy, ruff check, ruff format --check, pytest
just check-frontend   # Frontend only: tsc, eslint, vitest
```

```bash
# Backend tests
uv run pytest tests/ -v
uv run pytest tests/ --cov=backend --cov-report=html

# Frontend tests
cd frontend && npm test
cd frontend && npm run test:coverage
```

## Coding Style & Naming Conventions

### Python (backend/, cli/, tests/)

- Formatting: ruff (line length 100)
- Linting: avoid `noqa` comments
- Files/modules: `snake_case` (e.g., `post_service.py`, `auth.py`)
- Functions/variables: `snake_case`; private helpers prefixed with `_` (e.g., `_post_labels()`)
- Classes: `PascalCase` (e.g., `PostCache`, `TokenResponse`)
- Async: all database and I/O operations use `async def`
- Imports: `from __future__ import annotations` at the top of every module; isort ordering (stdlib, third-party, first-party)
- Typing: strict typing discipline; avoid `type: ignore` comments; modern union syntax (`str | None`, `dict[str, Any]`, `list[str]`); `Annotated` for FastAPI dependencies
- Pydantic models: inherit `BaseModel`, snake_case fields, `Field()` for validation, docstrings on every model
- SQLAlchemy models: inherit `Base`, `__tablename__` in snake_case, `Mapped[type]` + `mapped_column()` syntax
- FastAPI routes: `APIRouter` with prefix/tags, `response_model` on decorators, dependencies via `Annotated[Type, Depends(...)]`
- Dependencies: `get_` prefix for providers (e.g., `get_session`), `require_` prefix for auth guards (e.g., `require_auth`)
- Errors: raise `HTTPException` with specific status codes (401, 403, 404, 409)

### TypeScript (frontend/src/)

- Formatting: ESLint with typescript-eslint (type-checked rules); avoid `eslint-disable-line`
- Component files: `PascalCase.tsx` (e.g., `TimelinePage.tsx`, `PostCard.tsx`)
- Utility/store/API files: `camelCase.ts` (e.g., `authStore.ts`, `client.ts`)
- Components: functional, using arrow or function syntax; default export for page components
- Props interfaces: `PascalCase` with `Props` suffix (e.g., `PostCardProps`)
- API response types: `PascalCase` matching backend schemas (e.g., `PostDetail`, `PostSummary`)
- Zustand stores: `use<Name>Store` hook, interface includes state + methods, selector pattern for access
- API functions: `fetch` prefix (e.g., `fetchPosts()`, `fetchMe()`); parameter objects for multi-param functions
- Imports: path alias `@/` for `src/`; grouped as: React/external, local components, stores, API, types
- Event handlers: `handle` prefix (e.g., `handleSearch`)
- Styling: Tailwind utility classes; semantic color tokens (`bg-paper`, `text-ink`, `text-muted`, `border-border`)

## Testing Guidelines

- **IMPORTANT**: Every new feature should include tests that verify its correctness at the appropriate levels (unit, integration, and possibly system level).
- **IMPORTANT**: Follow Test Driven Development (TDD). Write failing tests first, implement changes later to make the tests pass.
- **IMPORTANT**: For every bug found, add a regression test that fails because of the bug, then fix the bug and ensure the test passes.
- Avoid brittle tests. Test user workflows, not implementation details.
- Don't leak expected error output into test run output.

### Backend (pytest)

- Test files: `tests/test_<category>/test_<module>.py`
- Group related tests in classes with `Test` prefix (e.g., `class TestAuth:`)
- Test functions: `test_<what_is_being_tested>()` — descriptive, underscore-separated
- All tests are async (`asyncio_mode = "auto"` in pyproject.toml)
- Fixtures in `conftest.py`: typed, async generators for teardown, fresh per test
- API integration tests use `httpx.AsyncClient` with `ASGITransport`
- Assertions: plain `assert` statements; check status codes, JSON fields, list lengths
- Markers: `@pytest.mark.slow`, `@pytest.mark.integration`

### Frontend (Vitest)

- jsdom environment with `@testing-library/react` and `@testing-library/user-event`
- Test files colocated or in `__tests__/` directories
- Use `render()`, `screen`, `userEvent` from testing-library

## Commit & Pull Request Guidelines

- Commit format: `type: subject` in imperative lowercase (e.g., `feat: add transfer flow`).
- PR title format same as commit format (`type: subject`).
- PR descriptions should summarize changes, rationale and impact. Do not summarize validation or testing. Unless the PR updates documentation only, do not describe documentation changes.
- Keep commits focused; avoid mixing unrelated changes.

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
- When finished browser testing, remove any leftover *.png screenshot files.
- When finished, verify with `just check` that there are no compilation, formatting or test errors.
