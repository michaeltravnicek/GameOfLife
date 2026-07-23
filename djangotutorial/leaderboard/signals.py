"""Automatic badge awarding.

Attendance (`UserToEvent`) is created from four different places -- geo check-in,
the admin attendance editor, the award-points command, and the Google-Sheets
sync. A post_save signal is the one hook that covers all of them without each
call site having to remember to award.

Awarding is best-effort: it must never break the attendance write that triggered
it. A sheets sync creating a thousand rows cannot fail because one badge insert
hit a snag.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserBadge, UserToEvent

logger = logging.getLogger(__name__)


def award_badge(user, badge, event=None):
    """Give `user` the `badge` if they don't already have it. Returns created?.

    Idempotent via the (user, badge) unique constraint: get_or_create absorbs the
    duplicate, so attending three events that share a badge collects it once.
    """
    _, created = UserBadge.objects.get_or_create(
        user=user, badge=badge, defaults={"event": event},
    )
    return created


@receiver(post_save, sender=UserToEvent, dispatch_uid="award_badge_on_attendance")
def award_badge_on_attendance(sender, instance, created, **kwargs):
    """Award the event's badge when attendance is recorded.

    Fires on every save (not just `created`): the sheets sync uses
    update_or_create, so a row that existed before its event got a badge still
    needs the badge on the next sync.
    """
    badge_id = instance.event.badge_id
    if not badge_id:
        return
    try:
        # A savepoint isolates a badge failure: on Postgres an unhandled
        # IntegrityError would otherwise poison the caller's whole transaction
        # (e.g. abort the rest of a sheets sync batch).
        with transaction.atomic():
            award_badge(instance.user, instance.event.badge, instance.event)
    except Exception:  # noqa: BLE001 -- badge award is derived data, never critical
        logger.warning(
            "Failed to award badge for attendance %s (continuing).",
            instance.pk, exc_info=True,
        )
