"""Base protocol and data classes for cross-posting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class CrossPostContent:
    """Content to be cross-posted to a social platform."""

    title: str
    excerpt: str
    url: str
    image_url: str | None = None
    labels: list[str] = field(default_factory=list)
    custom_text: str | None = None


@dataclass
class CrossPostResult:
    """Result of a cross-post attempt."""

    platform_id: str
    url: str
    success: bool
    error: str | None = None


@runtime_checkable
class CrossPoster(Protocol):
    """Protocol for platform-specific cross-posting implementations."""

    platform: str

    async def authenticate(self, credentials: dict[str, str]) -> bool:
        """Authenticate with the platform. Returns True on success."""
        ...

    async def post(self, content: CrossPostContent) -> CrossPostResult:
        """Post content to the platform."""
        ...

    async def validate_credentials(self) -> bool:
        """Validate that current credentials are still valid."""
        ...
