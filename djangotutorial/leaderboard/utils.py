"""Small helpers shared across views."""

import re


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
