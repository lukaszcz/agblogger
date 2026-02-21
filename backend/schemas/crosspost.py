"""Cross-posting schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SocialAccountCreate(BaseModel):
    """Request to connect a social media account."""

    platform: str = Field(min_length=1, description="Platform name, e.g. 'bluesky' or 'mastodon'")
    account_name: str | None = Field(default=None, description="Display name for the account")
    credentials: dict[str, str] = Field(
        description="Platform-specific credentials (stored as JSON)"
    )


class SocialAccountResponse(BaseModel):
    """Response for a connected social account."""

    id: int
    platform: str
    account_name: str | None = None
    created_at: str


class CrossPostRequest(BaseModel):
    """Request to cross-post a blog post."""

    post_path: str = Field(min_length=1, description="Relative file path of the post to cross-post")
    platforms: list[str] = Field(min_length=1, description="List of platform names to post to")
    custom_text: str | None = Field(
        default=None, description="Optional custom text to post instead of auto-generated content"
    )


class CrossPostResponse(BaseModel):
    """Response for a single cross-post result."""

    id: int
    post_path: str
    platform: str
    platform_id: str | None = None
    status: str
    posted_at: str | None = None
    error: str | None = None


class CrossPostHistoryResponse(BaseModel):
    """Response containing cross-post history for a post."""

    items: list[CrossPostResponse]


class BlueskyAuthorizeRequest(BaseModel):
    """Request to start Bluesky OAuth flow."""

    handle: str = Field(min_length=1, description="Bluesky handle, e.g. 'alice.bsky.social'")


class BlueskyAuthorizeResponse(BaseModel):
    """Response with authorization URL for Bluesky OAuth."""

    authorization_url: str


class MastodonAuthorizeRequest(BaseModel):
    """Request to start Mastodon OAuth flow."""

    instance_url: str = Field(
        min_length=1, description="Mastodon instance URL, e.g. 'https://mastodon.social'"
    )


class MastodonAuthorizeResponse(BaseModel):
    """Response with authorization URL for Mastodon OAuth."""

    authorization_url: str
