"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.auth import router as auth_router
from backend.api.labels import router as labels_router
from backend.api.pages import router as pages_router
from backend.api.posts import router as posts_router
from backend.api.render import router as render_router
from backend.api.sync import router as sync_router
from backend.config import Settings
from backend.database import create_engine
from backend.filesystem.content_manager import ContentManager
from backend.models.base import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan: startup and shutdown."""
    settings: Settings = app.state.settings
    logger.info("Starting AgBlogger (debug=%s)", settings.debug)

    # Create database engine
    engine, session_factory = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create FTS table
    from sqlalchemy import text

    async with session_factory() as session:
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
                "title, excerpt, content, content='posts_cache', content_rowid='id')"
            )
        )
        await session.commit()

    # Initialize content manager
    content_manager = ContentManager(content_dir=settings.content_dir)
    app.state.content_manager = content_manager

    # Ensure admin user exists
    from backend.services.auth_service import ensure_admin_user

    async with session_factory() as session:
        await ensure_admin_user(session, settings)

    # Rebuild cache from filesystem
    from backend.services.cache_service import rebuild_cache

    async with session_factory() as session:
        post_count = await rebuild_cache(session, content_manager)
        logger.info("Indexed %d posts from filesystem", post_count)

    yield

    # Shutdown
    await engine.dispose()
    logger.info("AgBlogger stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="AgBlogger",
        description="A markdown-first blogging platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(auth_router)
    app.include_router(posts_router)
    app.include_router(labels_router)
    app.include_router(pages_router)
    app.include_router(render_router)
    app.include_router(sync_router)

    # Serve frontend static files in production
    frontend_dir = settings.frontend_dir
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")

    return app


# Default application instance
app = create_app()


def cli_entry() -> None:
    """CLI entry point for running the server."""
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
