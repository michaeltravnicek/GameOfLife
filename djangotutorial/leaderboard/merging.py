"""Fold one leaderboard player into another, reversibly.

Registration now creates a player for every account
(`accounts.services.ensure_leaderboard_user`), so an account is never *missing*
a player -- it just may have a second one sitting in the Google-Forms archive
under the same human. Attaching that history is therefore a merge of two player
rows, not the link it used to be.

A merge moves rows and is destructive in a way a link never was, so it is a soft
merge: the source row survives, marked `merged_into`, and drops out of
`User.objects` (see ActivePlayerManager). `unmerge_players` puts it back. That
matters because the thing that decides a merge is still a name similarity -- a
human judgement that will occasionally be wrong.

Collisions are the interesting part. Both rows can hold attendance for the same
event (the person filled the form *and* checked in) or the same badge, and both
of those carry a unique constraint. The rules:

* attendance: keep one row, with the higher points. Losing the higher score to a
  merge would be a silent points cut, and every other tie-break is arbitrary.
* badge: keep the older award. A badge is "you did this", and the first time is
  when they did it.
* feedback: unique per (user, event) too, and the same human really can have
  rated one event twice -- once in the Google Form, once on the web. Keep the
  newer one: a rating is an opinion, and the later one is the one they hold now.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class MergeError(ValueError):
    """A merge that must not happen: refused before anything is written."""


def _resolve(player):
    """Follow a merge chain to the player who actually holds the points.

    A→B then B→C leaves A pointing at B, and B is no longer a real player.
    Everything that accepts a player id has to land on C.
    """
    seen = set()
    while player is not None and player.merged_into_id is not None:
        if player.pk in seen:  # a cycle can only come from hand-edited data
            raise MergeError(f"Cyklus ve sloučení hráčů u #{player.pk}.")
        seen.add(player.pk)
        player = player.merged_into
    return player


def resolve_player_id(player_id):
    """Public form of `_resolve`: id in, live player out (or None)."""
    from .models import User

    player = User.all_objects.filter(pk=player_id).first()
    return _resolve(player)


def _check_mergeable(source, target):
    """Refuse the merges that would lose or steal data. Raises MergeError."""
    from accounts.models import Profile

    if source.pk == target.pk:
        raise MergeError("Hráče nelze sloučit sám se sebou.")
    if source.merged_into_id is not None:
        raise MergeError(f"Hráč {source.name} už byl sloučen.")
    if target.merged_into_id is not None:
        raise MergeError(
            f"Cíl {target.name} sám byl sloučen do jiného hráče — "
            f"slučuj do toho."
        )
    # The source is about to disappear from the leaderboard. If an account is
    # attached to it, that account's owner would lose their whole history
    # without anyone touching their profile.
    if Profile.objects.filter(leaderboard_user=source).exists():
        raise MergeError(
            f"Hráč {source.name} patří registrovanému účtu. "
            f"Nejdřív ho odpoj, nebo slučuj opačným směrem."
        )


@transaction.atomic
def merge_players(source, target, performed_by=None, automatic=False):
    """Move everything from `source` onto `target`; mark `source` merged.

    Returns a dict of what moved -- the admin shows it, and the tests assert on
    it. Refuses (MergeError) rather than half-merging: the whole thing is one
    transaction.
    """
    from .cache_config import invalidate_points_dependent_caches
    from .models import EventFeedback, User, UserBadge, UserToEvent

    # Lock both rows for the duration: two admins merging the same archive
    # player into different targets would otherwise both pass the checks.
    # The instances the caller handed us are then refreshed from those locked
    # rows and mutated in place -- returning the merge on a private copy would
    # leave the caller holding an object that says the merge never happened.
    list(User.all_objects.select_for_update().filter(pk__in=[source.pk, target.pk]))
    source.refresh_from_db()
    target.refresh_from_db()
    _check_mergeable(source, target)

    moved = {"attendance": 0, "attendance_points_kept": 0, "badges": 0, "feedback": 0}

    target_points = {
        row.event_id: row
        for row in UserToEvent.objects.filter(user=target)
    }
    for row in UserToEvent.objects.filter(user=source):
        clash = target_points.get(row.event_id)
        if clash is None:
            row.user = target
            row.save(update_fields=["user"])
            moved["attendance"] += 1
            continue
        # Same event on both sides: keep the better score, drop the duplicate.
        if row.points > clash.points:
            clash.points = row.points
            clash.save(update_fields=["points"])
            moved["attendance_points_kept"] += 1
        row.delete()

    target_badges = set(
        UserBadge.objects.filter(user=target).values_list("badge_id", flat=True)
    )
    for row in UserBadge.objects.filter(user=source):
        if row.badge_id in target_badges:
            row.delete()  # already collected; the earlier award stays
            continue
        row.user = target
        row.save(update_fields=["user"])
        moved["badges"] += 1

    target_feedback = {
        row.event_id: row for row in EventFeedback.objects.filter(user=target)
    }
    for row in EventFeedback.objects.filter(user=source):
        clash = target_feedback.get(row.event_id)
        if clash is None:
            row.user = target
            row.save(update_fields=["user"])
            moved["feedback"] += 1
            continue
        # Rated the same event on both sides: the later rating wins, because it
        # is the opinion this person arrived at last.
        if row.created_at and clash.created_at and row.created_at > clash.created_at:
            clash.delete()
            row.user = target
            row.save(update_fields=["user"])
            moved["feedback"] += 1
        else:
            row.delete()

    # The e-mail is the one exact identity key there is, and it is unique, so it
    # cannot sit on both rows. It belongs to whoever is still on the leaderboard
    # -- otherwise a later signup with that address resolves to a merged ghost.
    if source.email and not target.email:
        target.email, source.email = source.email, None
        source.save(update_fields=["email"])
        target.save(update_fields=["email"])

    source.merged_into = target
    source.merged_at = timezone.now()
    source.save(update_fields=["merged_into", "merged_at"])

    invalidate_points_dependent_caches()
    logger.info(
        "Merged player #%s (%s) into #%s (%s) by %s%s: %s",
        source.pk, source.name, target.pk, target.name,
        performed_by or "system", " [automatic]" if automatic else "", moved,
    )
    return moved


@transaction.atomic
def unmerge_players(source):
    """Undo the merge flag. Rows that moved stay moved -- see below.

    This is the escape hatch for a wrong merge, not a full inverse: attendance
    and badges are not tracked back to where they came from, so what returns is
    the player row and its identity, not its history. In practice that is what
    the mistake case needs -- the archive player reappears on the leaderboard
    and an admin re-merges it into the right account.
    """
    from .cache_config import invalidate_points_dependent_caches

    if source.merged_into_id is None:
        raise MergeError(f"Hráč {source.name} není sloučený.")
    source.merged_into = None
    source.merged_at = None
    source.save(update_fields=["merged_into", "merged_at"])
    invalidate_points_dependent_caches()
    logger.info("Unmerged player #%s (%s)", source.pk, source.name)
    return source
