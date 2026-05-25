"""Admin-only feedback overview."""
from django.db.models import Count

from leaderboard.models import EventFeedback, UserToEvent


def admin_feedback_list():
    """All event feedback, each annotated with the submitter's name + attended-event count.

    Returns a list of dicts (newest first):
    ``{id, rating, comment, created_at, updated_at, user:{name, attended_events}, event:{slug, name, date}}``.
    """
    from accounts.models import Profile  # local import — avoid app-load cycle

    feedbacks = list(
        EventFeedback.objects
        .select_related("event", "auth_user")
        .order_by("-updated_at")
    )

    # auth_user → leaderboard_user, then a single grouped count of attendances.
    lb_user_by_auth = {
        p.user_id: p.leaderboard_user_id
        for p in Profile.objects.filter(user_id__in=[f.auth_user_id for f in feedbacks])
    }
    attended = {
        row["user"]: row["c"]
        for row in (
            UserToEvent.objects
            .filter(user_id__in=[v for v in lb_user_by_auth.values() if v])
            .values("user")
            .annotate(c=Count("id"))
        )
    }

    result = []
    for f in feedbacks:
        lb_id = lb_user_by_auth.get(f.auth_user_id)
        result.append({
            "id": f.id,
            "rating": f.rating,
            "comment": f.comment,
            "created_at": f.created_at,
            "updated_at": f.updated_at,
            "user": {
                "name": f.auth_user.get_full_name() or f.auth_user.username,
                "attended_events": attended.get(lb_id, 0) if lb_id else 0,
            },
            "event": {
                "slug": f.event.slug,
                "name": f.event.name,
                "date": f.event.date,
            },
        })
    return result
