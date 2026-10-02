"""Per-season scoring for one player: totals, rank and the event breakdown."""
from django.db.models import Sum

from leaderboard.models import Season, UserToEvent


def season_rank(season, season_pts):
    """1-based rank for a points total within a season, or None if no points.

    Counts only players the board shows: a hidden player still sitting in this
    count would push everyone below them down a place, so the rank on a profile
    and the position on the leaderboard would disagree.
    """
    from leaderboard.privacy import points_hidden_player_ids

    if season_pts <= 0:
        return None
    higher = (
        UserToEvent.objects
        .filter(season.date_window())
        .exclude(user_id__in=points_hidden_player_ids())
        .values("user")
        .annotate(pts=Sum("points"))
        .filter(pts__gt=season_pts)
        .count()
    )
    return higher + 1


def _season_base(season):
    return {
        "id": season.id,
        "label": season.name,
        "start": season.start_date,
        "end": season.end_date,
        "is_active": season.is_active,
    }


def season_summaries(lb_user, hide_pts=False):
    """Lightweight per-season points + rank for a user (no event lists).

    Feeds the profile's season selector; the heavy per-event data is fetched
    lazily per season via `season_detail`.

    Under `hide_pts` the season keeps its label and dates but loses its points
    and rank — a per-season total is still the total this flag withholds, only
    sliced by year.
    """
    result = []
    for season in Season.objects.all():
        if hide_pts:
            result.append(_season_base(season))
            continue
        season_pts = (
            UserToEvent.objects
            .filter(season.date_window(), user=lb_user)
            .aggregate(s=Sum("points"))["s"] or 0
        )
        result.append({
            **_season_base(season),
            "season_pts": season_pts,
            "rank": season_rank(season, season_pts),
        })
    return result


def season_detail(lb_user, season, hide_pts=False):
    """Full breakdown for one season: points, rank, and the event list.

    `hide_pts` strips every number the events could be added up into — the
    season total, the rank, and the per-event points — while leaving the list of
    events itself, which is what the separate `hide_events` flag governs.
    """
    if lb_user is None:
        return {**_season_base(season), "season_pts": 0, "rank": None, "events": []}

    utes = (
        UserToEvent.objects
        .filter(season.date_window(), user=lb_user)
        .select_related("event", "event__category")
        .order_by("event__date")
    )
    season_pts = sum(u.points for u in utes)
    payload = {
        **_season_base(season),
        "events": [
            {
                "slug":     u.event.slug,
                "name":     u.event.name,
                "place":    u.event.place,
                "date":     u.event.date,
                **({} if hide_pts else {"pts": u.points}),
                "category": {"id": u.event.category.id, "name": u.event.category.name}
                            if u.event.category else None,
            }
            for u in utes
        ],
    }
    if not hide_pts:
        payload["season_pts"] = season_pts
        payload["rank"] = season_rank(season, season_pts)
    return payload
