"""Small helpers shared across views."""


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
