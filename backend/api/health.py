"""Health check endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from backend.api.deps import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


@router.get("/api/health", response_model=HealthResponse)
async def health_check(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    """Health check endpoint for monitoring and load balancers."""
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version="0.1.0",
        database=db_status,
    )
