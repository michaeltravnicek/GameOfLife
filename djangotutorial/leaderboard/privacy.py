"""Public display rules for player names.

Points arrive from the Google Sheets sync, which creates a LeaderboardUser for
every attendee — including people who never registered, never saw the privacy
policy and never agreed to anything. Publishing their full name on an open
leaderboard has no legal basis under GDPR.

So a full name is shown only once someone has actively opted in: they have an
account linked to the leaderboard entry AND a current consent on file. Everyone
else is reduced to initials, which is enough to recognise yourself and to keep
the ranking meaningful, while not publishing an identity nobody agreed to.

Initials are pseudonymisation, not anonymisation — in a small community "J. N."
plus an attendance history may still point at a person. It is a large
improvement, not a complete answer, and the honest fallback if that matters is
to show nothing at all.
"""


def initials(name):
    """'Jan Novák' -> 'J. N.'  Falls back to a neutral label when unusable."""
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "Hráč"
    return " ".join(f"{p[0].upper()}." for p in parts[:3])


def display_name(name, *, consented):
    """Full name only for players who opted in; initials for everyone else."""
    return name if consented else initials(name)


def profile_has_consent(profile):
    """True when a linked profile carries a consent matching the current policy.

    Missing profile -> never registered, so nothing was agreed to.
    Missing consent -> registered before the policy existed; that is not
    agreement either, and backfilling one would be inventing a record.
    """
    return bool(profile and profile.has_current_gdpr_consent)
