"""Cross-posting API endpoints."""

from __future__ import annotations

import json as json_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
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
    BlueskyAuthorizeRequest,
    BlueskyAuthorizeResponse,
    CrossPostHistoryResponse,
    CrossPostRequest,
    CrossPostResponse,
    MastodonAuthorizeRequest,
    MastodonAuthorizeResponse,
    SocialAccountCreate,
    SocialAccountResponse,
)
from backend.services.crosspost_service import (
    DuplicateAccountError,
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
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
) -> SocialAccountResponse:
    """Connect a social media account for cross-posting."""
    try:
        account = await create_social_account(session, user.id, body, settings.secret_key)
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
            user,
            site_url,
            secret_key=settings.secret_key,
        )
    except ValueError as exc:
        if str(exc).startswith("Post not found"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return [
        CrossPostResponse(
            id=0,  # IDs not needed in response
            post_path=body.post_path,
            platform=body.platforms[i],
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
    user: Annotated[User, Depends(require_auth)],
) -> CrossPostHistoryResponse:
    """Get cross-posting history for a blog post."""
    records = await get_crosspost_history(session, post_path, user.id)
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


@router.get("/bluesky/client-metadata.json")
async def bluesky_client_metadata(
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> dict[str, object]:
    """Serve AT Protocol OAuth client metadata document."""
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bluesky OAuth not configured: BLUESKY_CLIENT_URL not set",
        )
    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"
    jwk = request.app.state.atproto_oauth_jwk
    return {
        "client_id": client_id,
        "client_name": "AgBlogger",
        "client_uri": base_url,
        "grant_types": ["authorization_code", "refresh_token"],
        "scope": "atproto transition:generic",
        "response_types": ["code"],
        "redirect_uris": [redirect_uri],
        "dpop_bound_access_tokens": True,
        "application_type": "web",
        "token_endpoint_auth_method": "private_key_jwt",
        "token_endpoint_auth_signing_alg": "ES256",
        "jwks": {"keys": [jwk]},
    }


@router.post("/bluesky/authorize", response_model=BlueskyAuthorizeResponse)
async def bluesky_authorize(
    body: BlueskyAuthorizeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> BlueskyAuthorizeResponse:
    """Start Bluesky OAuth flow: resolve handle, send PAR, return auth URL."""
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bluesky OAuth not configured: BLUESKY_CLIENT_URL not set",
        )
    from backend.crosspost.atproto_oauth import (
        ATProtoOAuthError,
        discover_auth_server,
        resolve_handle_to_did,
        send_par_request,
    )

    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"
    try:
        did = await resolve_handle_to_did(body.handle)
        auth_meta = await discover_auth_server(did)
        par_result = await send_par_request(
            auth_server_meta=auth_meta,
            client_id=client_id,
            redirect_uri=redirect_uri,
            did=did,
            scope="atproto transition:generic",
            private_key=request.app.state.atproto_oauth_key,
            jwk=request.app.state.atproto_oauth_jwk,
        )
    except ATProtoOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    state_store = request.app.state.bluesky_oauth_state
    state_store.set(
        par_result["state"],
        {
            "pkce_verifier": par_result["pkce_verifier"],
            "dpop_nonce": par_result["dpop_nonce"],
            "user_id": user.id,
            "did": did,
            "handle": body.handle,
            "auth_server_meta": auth_meta,
        },
    )
    return BlueskyAuthorizeResponse(authorization_url=par_result["authorization_url"])


@router.get("/bluesky/callback")
async def bluesky_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    iss: Annotated[str, Query()] = "",
) -> RedirectResponse:
    """Handle Bluesky OAuth callback: exchange code for tokens, store account."""
    state_store = request.app.state.bluesky_oauth_state
    pending = state_store.pop(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    expected_issuer = pending["auth_server_meta"]["issuer"]
    if iss and iss != expected_issuer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issuer mismatch in OAuth callback",
        )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    from backend.crosspost.atproto_oauth import (
        ATProtoOAuthError,
        exchange_code_for_tokens,
    )

    base_url = settings.bluesky_client_url.rstrip("/")
    client_id = f"{base_url}/api/crosspost/bluesky/client-metadata.json"
    redirect_uri = f"{base_url}/api/crosspost/bluesky/callback"
    auth_meta = pending["auth_server_meta"]
    private_key = request.app.state.atproto_oauth_key
    jwk = request.app.state.atproto_oauth_jwk
    try:
        token_data = await exchange_code_for_tokens(
            token_endpoint=auth_meta["token_endpoint"],
            auth_server_issuer=auth_meta["issuer"],
            code=code,
            redirect_uri=redirect_uri,
            pkce_verifier=pending["pkce_verifier"],
            client_id=client_id,
            private_key=private_key,
            jwk=jwk,
            dpop_nonce=pending["dpop_nonce"],
        )
    except ATProtoOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed: {exc}",
        ) from exc
    if token_data.get("sub") != pending["did"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DID mismatch in token response",
        )
    # The DPoP key used for PDS requests must match the key used during token
    # exchange, because the access token is DPoP-bound to that key.
    dpop_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    credentials = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "did": pending["did"],
        "handle": pending["handle"],
        "pds_url": auth_meta["pds_url"],
        "dpop_private_key_pem": dpop_pem,
        "dpop_jwk": json_mod.dumps(jwk),
        "dpop_nonce": token_data.get("dpop_nonce", ""),
        "auth_server_issuer": auth_meta["issuer"],
        "token_endpoint": auth_meta["token_endpoint"],
        "client_id": client_id,
    }
    account_data = SocialAccountCreate(
        platform="bluesky",
        account_name=pending["handle"],
        credentials=credentials,
    )
    try:
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)
    except DuplicateAccountError:
        existing = await get_social_accounts(session, pending["user_id"])
        replaced = False
        for acct in existing:
            if acct.platform == "bluesky" and acct.account_name == pending["handle"]:
                await delete_social_account(session, acct.id, pending["user_id"])
                replaced = True
                break
        if not replaced:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bluesky account already exists",
            ) from None
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)
    return RedirectResponse(url=f"{base_url}/admin", status_code=303)


@router.post("/mastodon/authorize", response_model=MastodonAuthorizeResponse)
async def mastodon_authorize(
    body: MastodonAuthorizeRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_auth)],
    request: Request,
) -> MastodonAuthorizeResponse:
    """Start Mastodon OAuth flow: register app dynamically, return auth URL."""
    if not settings.bluesky_client_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth not configured: BLUESKY_CLIENT_URL not set",
        )
    from backend.crosspost.mastodon import _normalize_instance_url

    instance_url = _normalize_instance_url(body.instance_url)
    if instance_url is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instance URL",
        )

    import hashlib
    import secrets

    base_url = settings.bluesky_client_url.rstrip("/")
    redirect_uri = f"{base_url}/api/crosspost/mastodon/callback"

    # PKCE: generate code_verifier and code_challenge (S256)
    unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    code_verifier = "".join(secrets.choice(unreserved) for _ in range(64))
    code_challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
    import base64

    code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).rstrip(b"=").decode("ascii")

    # Random state parameter
    oauth_state = secrets.token_hex(32)

    # Dynamically register the app with the Mastodon instance
    import httpx

    try:
        async with httpx.AsyncClient() as http_client:
            reg_resp = await http_client.post(
                f"{instance_url}/api/v1/apps",
                data={
                    "client_name": "AgBlogger",
                    "redirect_uris": redirect_uri,
                    "scopes": "read:accounts write:statuses",
                    "website": base_url,
                },
                timeout=15.0,
            )
            if reg_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"App registration failed: {reg_resp.status_code}",
                )
            reg_data = reg_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect to Mastodon instance: {exc}",
        ) from exc

    client_id = reg_data["client_id"]
    client_secret = reg_data["client_secret"]

    # Store pending state
    state_store = request.app.state.mastodon_oauth_state
    state_store.set(
        oauth_state,
        {
            "instance_url": instance_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "pkce_verifier": code_verifier,
            "user_id": user.id,
            "redirect_uri": redirect_uri,
        },
    )

    # Build authorization URL
    from urllib.parse import urlencode

    auth_params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "read:accounts write:statuses",
            "state": oauth_state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorization_url = f"{instance_url}/oauth/authorize?{auth_params}"

    return MastodonAuthorizeResponse(authorization_url=authorization_url)


@router.get("/mastodon/callback")
async def mastodon_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Handle Mastodon OAuth callback: exchange code for token, store account."""
    state_store = request.app.state.mastodon_oauth_state
    pending = state_store.pop(state)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    instance_url: str = pending["instance_url"]
    redirect_uri: str = pending["redirect_uri"]

    # Exchange authorization code for access token
    import httpx

    try:
        async with httpx.AsyncClient() as http_client:
            token_resp = await http_client.post(
                f"{instance_url}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": pending["client_id"],
                    "client_secret": pending["client_secret"],
                    "redirect_uri": redirect_uri,
                    "code_verifier": pending["pkce_verifier"],
                },
                timeout=15.0,
            )
            if token_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Token exchange failed: {token_resp.status_code}",
                )
            token_data = token_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange HTTP error: {exc}",
        ) from exc

    access_token = token_data["access_token"]

    # Verify credentials and get account info
    try:
        async with httpx.AsyncClient() as http_client:
            verify_resp = await http_client.get(
                f"{instance_url}/api/v1/accounts/verify_credentials",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            if verify_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to verify Mastodon credentials",
                )
            verify_data = verify_resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Credential verification HTTP error: {exc}",
        ) from exc

    from urllib.parse import urlparse

    hostname = urlparse(instance_url).hostname or ""
    acct = verify_data.get("acct", "")
    account_name = f"@{acct}@{hostname}"

    credentials = {
        "access_token": access_token,
        "instance_url": instance_url,
    }
    account_data = SocialAccountCreate(
        platform="mastodon",
        account_name=account_name,
        credentials=credentials,
    )
    try:
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)
    except DuplicateAccountError:
        existing = await get_social_accounts(session, pending["user_id"])
        replaced = False
        for acct_record in existing:
            if acct_record.platform == "mastodon" and acct_record.account_name == account_name:
                await delete_social_account(session, acct_record.id, pending["user_id"])
                replaced = True
                break
        if not replaced:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mastodon account already exists",
            ) from None
        await create_social_account(session, pending["user_id"], account_data, settings.secret_key)

    base_url = settings.bluesky_client_url.rstrip("/")
    return RedirectResponse(url=f"{base_url}/admin", status_code=303)
