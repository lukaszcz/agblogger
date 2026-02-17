"""Cross-posting schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SocialAccountCreate(BaseModel):
    """Request to connect a social media account."""

    platform: str = Field(description="Platform name, e.g. 'bluesky' or 'mastodon'")
    account_name: str | None = Field(
        default=None, description="Display name for the account"
    )
    credentials: dict[str, str] = Field(
        description="Platform-specific credentials (stored encrypted)"
    )


class SocialAccountResponse(BaseModel):
    """Response for a connected social account."""

    id: int
    platform: str
    account_name: str | None = None
    created_at: str


class CrossPostRequest(BaseModel):
    """Request to cross-post a blog post."""

    post_path: str = Field(description="Relative file path of the post to cross-post")
    platforms: list[str] = Field(
        description="List of platform names to post to"
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
