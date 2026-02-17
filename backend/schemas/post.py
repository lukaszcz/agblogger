"""Post-related schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PostSummary(BaseModel):
    """Post summary for timeline listing."""

    id: int
    file_path: str
    title: str
    author: str | None = None
    created_at: str
    modified_at: str
    is_draft: bool = False
    excerpt: str | None = None
    labels: list[str] = Field(default_factory=list)


class PostDetail(BaseModel):
    """Full post detail with rendered HTML."""

    id: int
    file_path: str
    title: str
    author: str | None = None
    created_at: str
    modified_at: str
    is_draft: bool = False
    excerpt: str | None = None
    labels: list[str] = Field(default_factory=list)
    rendered_html: str
    content: str | None = None  # Raw markdown, only for authenticated users


class PostCreate(BaseModel):
    """Request to create a new post."""

    file_path: str = Field(description="Relative path under content/, e.g. posts/my-post.md")
    content: str = Field(description="Full markdown content including front matter")


class PostUpdate(BaseModel):
    """Request to update an existing post."""

    content: str = Field(description="Full markdown content including front matter")


class PostListResponse(BaseModel):
    """Paginated post list response."""

    posts: list[PostSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class SearchResult(BaseModel):
    """Search result item."""

    id: int
    file_path: str
    title: str
    excerpt: str | None = None
    created_at: str
    rank: float = 0.0
