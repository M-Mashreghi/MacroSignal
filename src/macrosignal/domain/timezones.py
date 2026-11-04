"""Shared timezone validation for canonical domain models.

Domain timezones must be IANA timezone-database names so DST transitions come
from the database; fixed UTC offsets are rejected (docs/RELEASE_CALENDAR_SPEC.md).
"""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_UTC_ALIASES = frozenset({"UTC", "Etc/UTC"})


def validate_iana_timezone(name: str, *, field: str = "timezone") -> str:
    """Return ``name`` if it is an IANA region/city zone (or UTC), else raise ``ValueError``."""
    if name.startswith("Etc/GMT") or name.upper().startswith(("UTC+", "UTC-", "GMT+", "GMT-")):
        raise ValueError(
            f"{field} {name!r} is a fixed UTC offset; use an IANA zone such as "
            "'America/New_York'"
        )
    if name not in _UTC_ALIASES and "/" not in name:
        raise ValueError(f"{field} {name!r} is not an IANA region/city zone name")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"{field} {name!r} is not in the timezone database") from exc
    return name
