"""Admin-facing attendance + RSVP queries and mutations for a single event.

Attendance lives in UserToEvent (leaderboard user + points), which feeds the
leaderboard — so every write here drops the points-dependent caches. RSVPs live
in EventRSVP (auth user, "I'm coming"), which don't affect points.
"""
from leaderboard.cache_config import invalidate_points_dependent_caches
from leaderboard.models import EventRSVP, UserToEvent


def _linked_usernames(lb_user_ids):
    """Map {leaderboard_user_id: account username} for the given ids."""
    from accounts.models import Profile  # local import — avoid app-load cycle
    return {
        p.leaderboard_user_id: p.user.username
        for p in (
            Profile.objects
            .filter(leaderboard_user_id__in=list(lb_user_ids))
            .select_related("user")
        )
    }


def attendees_for_event(event):
    """`[{user_id, name, points, profile_username}]`, highest points first."""
    utes = list(
        UserToEvent.objects
        .filter(event=event)
        .select_related("user")
        .order_by("-points", "user__name")
    )
    usernames = _linked_usernames(u.user_id for u in utes)
    return [
        {
            "user_id": u.user_id,
            "name": u.user.name,
            "points": u.points,
            "profile_username": usernames.get(u.user_id),
        }
        for u in utes
    ]


def attendee_payload(lb_user, points):
    """One attendee dict (same shape as attendees_for_event rows)."""
    username = _linked_usernames([lb_user.id]).get(lb_user.id)
    return {
        "user_id": lb_user.id,
        "name": lb_user.name,
        "points": points,
        "profile_username": username,
    }


def set_attendance(event, lb_user, points):
    """Create or update the user's attendance row. Returns (row, created)."""
    ute, created = UserToEvent.objects.update_or_create(
        user=lb_user, event=event, defaults={"points": points},
    )
    invalidate_points_dependent_caches()
    return ute, created


def remove_attendance(event, lb_user):
    """Delete the user's attendance row if present. Returns True if one was removed."""
    deleted, _ = UserToEvent.objects.filter(user=lb_user, event=event).delete()
    if deleted:
        invalidate_points_dependent_caches()
    return bool(deleted)


def rsvps_for_event(event):
    """`[{auth_user_id, name, username, created_at}]`, oldest RSVP first."""
    rsvps = (
        EventRSVP.objects
        .filter(event=event)
        .select_related("auth_user")
        .order_by("created_at")
    )
    return [
        {
            "auth_user_id": r.auth_user_id,
            "name": r.auth_user.get_full_name() or r.auth_user.username,
            "username": r.auth_user.username,
            "created_at": r.created_at,
        }
        for r in rsvps
    ]
