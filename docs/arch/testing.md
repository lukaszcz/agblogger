# Testing

## Backend (pytest)

```
tests/
├── conftest.py                  Fixtures: tmp content dir, settings, DB engine/session
├── test_api/
│   └── test_api_integration.py  Full API tests via httpx AsyncClient + ASGITransport
├── test_services/
│   ├── test_config.py           Settings loading
│   ├── test_content_manager.py  ContentManager operations
│   ├── test_crosspost.py        Cross-posting platforms
│   ├── test_database.py         DB engine creation
│   ├── test_datetime_service.py Date/time parsing
│   ├── test_git_service.py      Git service operations
│   ├── test_git_merge_file.py   git merge-file wrapper tests
│   ├── test_frontmatter_merge.py  Semantic front matter merge tests
│   ├── test_hybrid_merge.py     Hybrid merge (front matter + body) tests
│   ├── test_sync_service.py     Sync plan computation
│   └── test_sync_merge_integration.py  Full sync merge API flow
├── test_sync/                   CLI sync client tests
├── test_labels/                 Label service tests
└── test_rendering/              Pandoc rendering tests
```

Configuration in `pyproject.toml`: `asyncio_mode = "auto"`, markers for `slow` and `integration`, coverage via `pytest-cov`.

## Frontend (Vitest)

Vitest with jsdom environment, `@testing-library/react`, and `@testing-library/user-event`.
