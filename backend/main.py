"""FastAPI application entry point."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.auth import router as auth_router
from backend.api.crosspost import router as crosspost_router
from backend.api.health import router as health_router
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


def _configure_logging(debug: bool) -> None:
    """Configure structured logging."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )
    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if debug else logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan: startup and shutdown."""
    settings: Settings = app.state.settings
    _configure_logging(settings.debug)
    logger.info("Starting AgBlogger (debug=%s)", settings.debug)

    engine, session_factory = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy import text

    async with session_factory() as session:
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5("
                "title, excerpt, content, content='posts_cache', content_rowid='id')"
            )
        )
        await session.commit()

    content_manager = ContentManager(content_dir=settings.content_dir)
    app.state.content_manager = content_manager

    from backend.services.auth_service import ensure_admin_user

    async with session_factory() as session:
        await ensure_admin_user(session, settings)

    from backend.services.cache_service import rebuild_cache

    async with session_factory() as session:
        post_count, warnings = await rebuild_cache(session, content_manager)
        logger.info("Indexed %d posts from filesystem", post_count)
        for warning in warnings:
            logger.warning("Cache rebuild: %s", warning)

    yield

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

    app.add_middleware(GZipMiddleware, minimum_size=500)

    cors_origins = ["http://localhost:5173", "http://localhost:8000"] if settings.debug else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(posts_router)
    app.include_router(labels_router)
    app.include_router(pages_router)
    app.include_router(render_router)
    app.include_router(sync_router)
    app.include_router(crosspost_router)

    # Serve frontend static files in production
    frontend_dir = settings.frontend_dir
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")

    return app


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
