"""Datetime parsing: lax input -> strict output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pendulum

if TYPE_CHECKING:
    pass

# Strict output format: YYYY-MM-DD HH:MM:SS.ffffff±TZ
STRICT_FORMAT = "%Y-%m-%d %H:%M:%S.%f%z"


def parse_datetime(value: str | datetime, default_tz: str = "UTC") -> datetime:
    """Parse a lax datetime string into a strict timezone-aware datetime.

    Accepts various formats:
    - 2026-02-02 22:21:29.975359+00
    - 2026-02-02 22:21:29+00
    - 2026-02-02 22:21+00
    - 2026-02-02 22:21
    - 2026-02-02
    - ISO 8601 variants with T separator

    Missing timezone defaults to default_tz.
    Missing time components default to zeros.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            tz = pendulum.timezone(default_tz)
            value = value.replace(tzinfo=tz)  # type: ignore[arg-type]
        return value

    value_str = value.strip()

    parsed = pendulum.parse(value_str, tz=default_tz, strict=False)
    if not isinstance(parsed, pendulum.DateTime):
        # pendulum.parse returns Date for date-only strings
        parsed = pendulum.datetime(
            parsed.year, parsed.month, parsed.day, tz=default_tz  # type: ignore[union-attr]
        )
    return parsed  # type: ignore[return-value]


def format_datetime(dt: datetime) -> str:
    """Format a datetime to the strict output format.

    Output: YYYY-MM-DD HH:MM:SS.ffffff+HH:MM
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(STRICT_FORMAT)


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso(dt: datetime) -> str:
    """Format datetime as ISO 8601 for JSON serialization."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
