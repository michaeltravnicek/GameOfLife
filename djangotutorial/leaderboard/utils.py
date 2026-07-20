"""Small helpers shared across views."""

import re

from datetime import datetime

from django.utils import timezone


def parse_iso_datetime(raw):
    """Parse an ISO-8601 datetime string into a timezone-aware ``datetime``.

    Returns ``None`` for empty input. Raises ``ValueError`` for an unparseable
    string. Naive datetimes are made aware in the current timezone. Replaces the
    repeated ``datetime.fromisoformat(... .replace('Z', '+00:00'))`` + is_naive
    blocks in the event create/update views.
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


def parse_phone_number(raw):
    """Normalize a Czech phone number to the 9-digit int used by ``User.number``.

    Strips non-digits, drops a leading ``420`` country code, and returns an int
    only when exactly 9 digits remain — otherwise ``None``.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("420") and len(digits) == 12:
        digits = digits[3:]
    if len(digits) != 9:
        return None
    return int(digits)


def parse_int_param(raw, default, *, min_val=None, max_val=None):
    """Parse an int query/body param with a default and optional clamping.

    Replaces this repeated five-line block:

        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = default
        n = max(n, min_val)
        n = min(n, max_val)

    `min_val`/`max_val` are optional. None means no clamp on that side.
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
