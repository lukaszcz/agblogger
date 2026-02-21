"""Platform registry for cross-posting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.crosspost.bluesky import BlueskyCrossPoster
from backend.crosspost.facebook import FacebookCrossPoster
from backend.crosspost.mastodon import MastodonCrossPoster
from backend.crosspost.x import XCrossPoster

if TYPE_CHECKING:
    from backend.crosspost.base import CrossPoster

PLATFORMS: dict[
    str,
    type[BlueskyCrossPoster]
    | type[FacebookCrossPoster]
    | type[MastodonCrossPoster]
    | type[XCrossPoster],
] = {
    "bluesky": BlueskyCrossPoster,
    "mastodon": MastodonCrossPoster,
    "x": XCrossPoster,
    "facebook": FacebookCrossPoster,
}


async def get_poster(platform: str, credentials: dict[str, str]) -> CrossPoster:
    """Create and authenticate a cross-poster for the given platform.

    Raises ValueError if the platform is unknown or authentication fails.
    """
    poster_cls = PLATFORMS.get(platform)
    if poster_cls is None:
        msg = f"Unknown platform: {platform!r}. Available: {list(PLATFORMS)}"
        raise ValueError(msg)

    poster = poster_cls()
    authenticated = await poster.authenticate(credentials)
    if not authenticated:
        msg = f"Failed to authenticate with {platform}"
        raise ValueError(msg)

    return poster


def list_platforms() -> list[str]:
    """Return the list of supported platform names."""
    return list(PLATFORMS.keys())
