"""Small helpers shared across views."""


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
