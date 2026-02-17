"""Cross-posting API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    get_content_manager,
    get_session,
    get_settings,
    require_auth,
)
from backend.config import Settings
from backend.filesystem.content_manager import ContentManager
from backend.models.user import User
from backend.schemas.crosspost import (
    CrossPostHistoryResponse,
    CrossPostRequest,
    CrossPostResponse,
    SocialAccountCreate,
    SocialAccountResponse,
)
from backend.services.crosspost_service import (
    create_social_account,
    crosspost,
    delete_social_account,
    get_crosspost_history,
    get_social_accounts,
)

router = APIRouter(prefix="/api/crosspost", tags=["crosspost"])


@router.post("/accounts", response_model=SocialAccountResponse, status_code=201)
async def create_account_endpoint(
    body: SocialAccountCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_auth)],
) -> SocialAccountResponse:
    """Connect a social media account for cross-posting."""
    try:
        account = await create_social_account(session, user.id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return SocialAccountResponse(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        created_at=account.created_at,
    )


@router.get("/accounts", response_model=list[SocialAccountResponse])
async def list_accounts_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_auth)],
) -> list[SocialAccountResponse]:
    """List connected social accounts."""
    accounts = await get_social_accounts(session, user.id)
    return [
        SocialAccountResponse(
            id=acct.id,
            platform=acct.platform,
            account_name=acct.account_name,
            created_at=acct.created_at,
        )
        for acct in accounts
    ]


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account_endpoint(
    account_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_auth)],
) -> None:
    """Delete a connected social account."""
    deleted = await delete_social_account(session, account_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Social account not found",
        )


@router.post("/post", response_model=list[CrossPostResponse])
async def crosspost_endpoint(
    body: CrossPostRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    content_manager: Annotated[ContentManager, Depends(get_content_manager)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
) -> list[CrossPostResponse]:
    """Cross-post a blog post to selected platforms."""
    # Build site URL from settings
    site_url = f"http{'s' if not settings.debug else ''}://{settings.host}"
    if settings.port not in (80, 443):
        site_url += f":{settings.port}"

    try:
        results = await crosspost(
            session,
            content_manager,
            body.post_path,
            body.platforms,
            user.id,
            site_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return [
        CrossPostResponse(
            id=0,  # IDs not needed in response
            post_path=body.post_path,
            platform=body.platforms[i] if i < len(body.platforms) else "",
            platform_id=r.platform_id or None,
            status="posted" if r.success else "failed",
            posted_at=None,
            error=r.error,
        )
        for i, r in enumerate(results)
    ]


@router.get("/history/{post_path:path}", response_model=CrossPostHistoryResponse)
async def history_endpoint(
    post_path: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CrossPostHistoryResponse:
    """Get cross-posting history for a blog post."""
    records = await get_crosspost_history(session, post_path)
    return CrossPostHistoryResponse(
        items=[
            CrossPostResponse(
                id=cp.id,
                post_path=cp.post_path,
                platform=cp.platform,
                platform_id=cp.platform_id,
                status=cp.status,
                posted_at=cp.posted_at,
                error=cp.error,
            )
            for cp in records
        ]
    )
