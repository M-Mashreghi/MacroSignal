"""Minimal iCalendar (RFC 5545) VEVENT reader for official release schedules.

Only what release calendars need: line unfolding, property parameters, and
``DTSTART`` parsing.  Timestamps are returned timezone-aware; a ``TZID`` is
mapped through an explicit alias table to an IANA zone, a trailing ``Z`` means
UTC, and *floating* times are only accepted when the caller supplies the
source's documented default timezone.  Date-only values (no time) are returned
as dates so callers can decide not to invent a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


class IcsParseError(ValueError):
    """Malformed or unsupported iCalendar content."""


@dataclass(frozen=True)
class IcsProperty:
    name: str
    params: dict[str, str]
    value: str


@dataclass(frozen=True)
class IcsEvent:
    properties: dict[str, IcsProperty] = field(default_factory=dict)

    def get(self, name: str) -> IcsProperty | None:
        return self.properties.get(name.upper())

    def text(self, name: str) -> str | None:
        prop = self.get(name)
        if prop is None:
            return None
        return (
            prop.value.replace("\\n", "\n")
            .replace("\\N", "\n")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\\\", "\\")
            .strip()
        )


def unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _parse_line(line: str) -> IcsProperty:
    head, sep, value = line.partition(":")
    if not sep:
        raise IcsParseError(f"line without ':' separator: {line!r}")
    name, *raw_params = head.split(";")
    params: dict[str, str] = {}
    for item in raw_params:
        key, eq, val = item.partition("=")
        if not eq:
            raise IcsParseError(f"bad parameter {item!r} in {line!r}")
        params[key.upper()] = val.strip('"')
    return IcsProperty(name.upper(), params, value)


def parse_events(text: str) -> list[IcsEvent]:
    events: list[IcsEvent] = []
    current: dict[str, IcsProperty] | None = None
    depth_other = 0
    for line in unfold(text):
        prop = _parse_line(line)
        if prop.name == "BEGIN" and prop.value.upper() == "VEVENT":
            if current is not None:
                raise IcsParseError("nested VEVENT")
            current = {}
        elif prop.name == "END" and prop.value.upper() == "VEVENT":
            if current is None:
                raise IcsParseError("END:VEVENT without BEGIN")
            events.append(IcsEvent(current))
            current = None
        elif prop.name == "BEGIN" and current is not None:
            depth_other += 1  # e.g. VALARM inside an event: ignore its properties
        elif prop.name == "END" and current is not None and depth_other:
            depth_other -= 1
        elif current is not None and not depth_other:
            current.setdefault(prop.name, prop)
    if current is not None:
        raise IcsParseError("unterminated VEVENT")
    return events


def parse_datetime(
    prop: IcsProperty, tz_aliases: dict[str, str], default_tz: str | None
) -> datetime | date:
    """Parse a DATE or DATE-TIME property into an aware datetime (or a date)."""
    value = prop.value.strip()
    if prop.params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and value.isdigit()):
        try:
            return datetime.strptime(value, "%Y%m%d").date()
        except ValueError as exc:
            raise IcsParseError(f"bad DATE value {value!r}") from exc
    utc = value.endswith("Z")
    try:
        naive = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise IcsParseError(f"bad DATE-TIME value {value!r}") from exc
    if utc:
        return naive.replace(tzinfo=UTC)
    tzid = prop.params.get("TZID")
    if tzid is not None:
        zone = tz_aliases.get(tzid)
        if zone is None:
            raise IcsParseError(f"unsupported TZID {tzid!r}")
        return naive.replace(tzinfo=ZoneInfo(zone))
    if default_tz is None:
        raise IcsParseError(f"floating time {value!r} without a documented source timezone")
    return naive.replace(tzinfo=ZoneInfo(default_tz))
