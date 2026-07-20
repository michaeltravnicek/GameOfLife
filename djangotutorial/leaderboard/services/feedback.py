"""Admin-only feedback overview."""
from django.db.models import Count

from leaderboard.models import EventFeedback, UserToEvent


def admin_feedback_list():
    """All event feedback, each annotated with the submitter's name + attended-event count.

    Returns a list of dicts (newest first):
    ``{id, rating, comment, source, created_at, updated_at,
       user:{name, attended_events}, event:{slug, name, date}}``.
    """
    feedbacks = list(
        EventFeedback.objects
        .select_related("event", "user")
        .order_by("-updated_at")
    )

    attended = {
        row["user"]: row["c"]
        for row in (
            UserToEvent.objects
            .filter(user_id__in=[f.user_id for f in feedbacks])
            .values("user")
            .annotate(c=Count("id"))
        )
    }

    return [
        {
            "id": f.id,
            "rating": f.rating,
            "comment": f.comment,
            "source": f.source,
            "created_at": f.created_at,
            "updated_at": f.updated_at,
            "user": {
                "name": f.user.name,
                "attended_events": attended.get(f.user_id, 0),
            },
            "event": {
                "slug": f.event.slug,
                "name": f.event.name,
                "date": f.event.date,
            },
        }
        for f in feedbacks
    ]
