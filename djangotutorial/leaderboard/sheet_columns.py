"""Recognising Google Form columns by their header text.

The forms behind the attendance sheets all use the same question wording, so a
column is identified by matching its header against a known set of strings
rather than by position -- Forms reorders and inserts columns freely, and every
event's sheet is generated fresh.

Matching is exact on the wording but tolerant of the noise Sheets adds around
it: leading/trailing space, doubled inner spaces, and case. Add older or
reworded variants to the sets below; nothing else needs to change.
"""

import re

# "Timestamp | Telefon (bez předvolby) | Jméno a příjmení | Zúčastnil/a ses
#  této akce? | Jak hodnotíš tuto akci? | Pokud máš ještě něco na srdci, ..."
#
# Newer forms have "Collect email addresses" switched on, which prepends an
# "Email Address" column, and no longer ask for a phone number at all.
EMAIL_HEADERS = {
    "email address",
    "e-mail address",
    "emailová adresa",
    "e-mailová adresa",
    "email",
    "e-mail",
}
NAME_HEADERS = {
    "jméno a příjmení",
    "jméno",
}
ATTENDED_HEADERS = {
    "zúčastnil/a ses této akce?",
}
RATING_HEADERS = {
    "jak hodnotíš tuto akci?",
}
COMMENT_HEADERS = {
    "pokud máš ještě něco na srdci, tady je prostor.",
}
POINTS_HEADERS = {
    "body",
}

# Answers to "Zúčastnil/a ses této akce?" that mean "no". Anything else --
# including a blank cell -- counts as attended, because the column is a late
# addition and older rows simply predate it.
NEGATIVE_ANSWERS = {"ne", "no", "nezúčastnil", "nezúčastnila", "nezúčastnil/a"}


def normalize_header(raw) -> str:
    """Lowercase, collapse internal whitespace, strip the ends."""
    return re.sub(r"\s+", " ", str(raw or "")).strip().lower()


def header_map(header_row) -> dict[str, int]:
    """Map role name -> column index for the roles present in ``header_row``.

    Roles: ``email``, ``name``, ``attended``, ``rating``, ``comment``,
    ``points``. Absent roles are simply missing from the result. On duplicate
    headers the first wins.
    """
    roles = (
        ("email", EMAIL_HEADERS),
        ("name", NAME_HEADERS),
        ("attended", ATTENDED_HEADERS),
        ("rating", RATING_HEADERS),
        ("comment", COMMENT_HEADERS),
        ("points", POINTS_HEADERS),
    )
    found: dict[str, int] = {}
    for i, cell in enumerate(header_row or []):
        norm = normalize_header(cell)
        for role, headers in roles:
            if norm in headers and role not in found:
                found[role] = i
    return found


def cell(rec, index) -> str:
    """Value at ``index``, or "" when the column is absent or the row is short.

    Sheets truncates trailing empty cells, so rows are routinely shorter than
    the header.
    """
    if index is None or index >= len(rec):
        return ""
    return str(rec[index]).strip()


def parse_rating(raw) -> int | None:
    """First integer in the cell, if it lands in 1-10. Otherwise None.

    Tolerates "8", "8/10", "8 - skvělé" -- the Forms scale question exports as a
    bare number, but hand-edited sheets vary.
    """
    m = re.search(r"(?<!-)\d+", str(raw or ""))
    if not m:
        return None
    value = int(m.group())
    return value if 1 <= value <= 10 else None


def is_negative_attendance(raw) -> bool:
    """True when the attendance answer explicitly says "no"."""
    return normalize_header(raw).rstrip(".") in NEGATIVE_ANSWERS
