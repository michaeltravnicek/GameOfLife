"""Public display rules for player names and self-service profile privacy.

Two separate mechanisms live here:

* **Name display** (below) is a GDPR obligation — it applies to people who never
  registered and therefore never agreed to anything.
* **Profile visibility** (`visibility_for`) is a self-service setting a
  registered user turns on themselves.

Points arrive from the Google Sheets sync, which creates a LeaderboardUser for
every attendee — including people who never registered, never saw the privacy
policy and never agreed to anything. Publishing their full name on an open
leaderboard has no legal basis under GDPR.

So a full name is shown only once someone has actively opted in: they have an
account linked to the leaderboard entry AND a current consent on file. Everyone
else is reduced to a shortened form — given name plus the initial of the
surname, "Jan N." — which is enough to recognise yourself and to keep the
ranking meaningful, while withholding the one field that makes a person
searchable and reachable: the surname.

This is pseudonymisation, not anonymisation — in a small community "Jan N."
plus an attendance history may still point at a person, and a given name
narrows the field more than a bare initial does. It is a large improvement, not
a complete answer, and the honest fallback if that matters is to show nothing
at all.
"""
from collections import namedtuple


def short_name(name):
    """'Jan Novák' -> 'Jan N.'  Falls back to a neutral label when unusable."""
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "Hráč"
    if len(parts) == 1:
        # A lone token is a given name or a nickname in practice, and that is
        # exactly what this form publishes anyway — nothing to shorten.
        return parts[0]
    # Only the last token counts as the surname. Middle names are dropped
    # rather than abbreviated: they add identifying detail without helping
    # anyone recognise their own row.
    return f"{parts[0]} {parts[-1][0].upper()}."


def display_name(name, *, consented):
    """Full name only for players who opted in; 'Jan N.' for everyone else."""
    return name if consented else short_name(name)


def public_handle(username):
    """The public profile slug for `username`, or None when it isn't safe to publish.

    `auth.User.username` doubles as the /profil/<slug> handle, but for accounts
    created through allauth / Google login it defaults to the person's e-mail
    address. Emitting that on any public endpoint (leaderboard, player detail,
    gallery credits) hands out a contactable e-mail to anyone — a PII leak, and
    one that slips past the name-consent rules above, which only gate the display
    name, not this field.

    So anything e-mail-shaped is withheld: callers already treat None as "no
    linked handle" and fall back to the /hrac/<id> route, which exposes no e-mail.
    Real chosen handles (no '@') pass through unchanged.
    """
    if not username or "@" in username:
        return None
    return username


def profile_has_consent(profile):
    """True when a linked profile carries a consent matching the current policy.

    Missing profile -> never registered, so nothing was agreed to.
    Missing consent -> registered before the policy existed; that is not
    agreement either, and backfilling one would be inventing a record.
    """
    return bool(profile and profile.has_current_gdpr_consent)


# --- Self-service profile privacy -------------------------------------------

Visibility = namedtuple("Visibility", "members_only hide_pts hide_events")

#: Nothing hidden. Used for profileless players and for privileged viewers.
ALL_VISIBLE = Visibility(False, False, False)


def visibility_for(profile, viewer):
    """Which of `profile`'s privacy flags actually apply to `viewer`.

    Call this at every point that builds profile data, not just the one the UI
    happens to use. The same person is reachable through four endpoints
    (`/profiles/<username>/`, its season sub-resource, `/players/<id>/`, and its
    season sub-resource) -- a flag enforced on some of them is not enforced at
    all, because the client picking the endpoint is the attacker's to choose.

    Two viewers are never gated:
      * the owner, whose own payload prefills the edit form -- hiding fields
        from them would blank those fields on the next save;
      * admins, who cannot moderate what they cannot see.

    `members_only` means "signed-in visitors only", so any authenticated viewer
    clears it; the other two flags apply to everyone but the owner and admins.
    """
    if profile is None:
        return ALL_VISIBLE

    # Local import: accounts depends on leaderboard, so importing it at module
    # level here would close the loop at app-load time.
    from accounts.permissions import is_admin

    authenticated = bool(getattr(viewer, "is_authenticated", False))
    if authenticated and (profile.user_id == viewer.pk or is_admin(viewer)):
        return ALL_VISIBLE

    return Visibility(
        members_only=profile.members_only and not authenticated,
        hide_pts=profile.hide_pts,
        hide_events=profile.hide_events,
    )
