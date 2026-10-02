"""Small helpers shared across views."""

import re

from datetime import datetime

from django.utils import timezone


def absolute_url(url, request=None):
    """`url` made absolute against the request's host; as-is without a request
    (management commands and tests build payloads with none)."""
    return request.build_absolute_uri(url) if request else url


def media_url(field_file, request=None):
    """Public URL of a stored file, or None when the field is empty."""
    if not field_file:
        return None
    return absolute_url(field_file.url, request)


def event_logo_url(event, request=None):
    """An event's logo, which is the artwork on its badge. None when unset."""
    return media_url(event.badge.image if event.badge_id else None, request)


def parse_iso_datetime(raw):
    """Parse an ISO-8601 datetime string into a timezone-aware ``datetime``.

    Returns ``None`` for empty input. Raises ``ValueError`` for an unparseable
    string. Naive datetimes are made aware in the current timezone.
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Neplatný formát data.") from exc
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


# Dates hidden in sheet/event names: "27._5._2025", "22.12.2025", "10.12",
# "16. 1. 26" — day.month with optional trailing dot and 2/4-digit year,
# underscores or spaces between the parts.
EVENT_NAME_DATE_RE = re.compile(r"(\d{1,2})\.\s*_?(\d{1,2})\.?(?:\s*_?(\d{4}|\d{2}))?")


def parse_event_date_from_name(name, today=None):
    """Best-effort event date parsed out of a sheet/event name.

    The Google Sheets sync has no date column — only the sheet title, which
    usually embeds one ("Christmas Run, Brno 22.12.2025"). Without this, synced
    events get stamped with the SYNC time, and profile tables/charts attribute
    the points to the wrong day.

    Returns an aware datetime at 12:00 (midday avoids off-by-one days across
    timezones), or None when the name carries no parsable date. A missing year
    resolves to the most recent occurrence not in the future — points are
    always summed after the event happened.
    """
    m = EVENT_NAME_DATE_RE.search(name or "")
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year_raw = m.group(3)
    today = today or timezone.localdate()
    try:
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = today.year
            if datetime(year, month, day).date() > today:
                year -= 1
        return timezone.make_aware(datetime(year, month, day, 12, 0))
    except ValueError:  # 31.2., month 13, …
        return None


def parse_int_param(raw, default, *, min_val=None, max_val=None):
    """Parse an int query/body param with a default and optional clamping.

    `min_val`/`max_val` are optional; None means no clamp on that side.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    if min_val is not None and value < min_val:
        value = min_val
    if max_val is not None and value > max_val:
        value = max_val
    return value
