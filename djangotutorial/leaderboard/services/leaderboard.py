"""Leaderboard rankings, season scoping, and cached season entries."""
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from leaderboard.cache_config import CACHE_TTL, season_leaderboard_key
from leaderboard.models import Season, User, UserToEvent

from .catalog import season_dict


def create_leaderboard(leaderboard):
    """Attach a 1-based `rank` to each user, with ties sharing a rank."""
    leaderboard_list = list(leaderboard)
    previous_points = None
    rank = 0
    for i, user in enumerate(leaderboard_list, start=1):
        if user.total_points == previous_points:
            user.rank = rank
        else:
            rank = i
            user.rank = rank
            previous_points = user.total_points
    return leaderboard_list


def leaderboard_total():
    """All-time ranking: every user annotated with event count + total points."""
    return (
        User.objects
        .annotate(
            events_count=Count("usertoevent", distinct=True),
            total_points=Coalesce(Sum("usertoevent__points"), 0),
        )
        .order_by("-total_points")
    )


def _season_window(season):
    """Q filter matching UserToEvent rows whose event falls inside the season."""
    return Q(
        usertoevent__event__date__date__gte=season.start_date,
        usertoevent__event__date__date__lte=season.end_date,
    )


def leaderboard_for_season(season):
    """Ranked users scored only on events within `[season.start, season.end]`."""
    window = _season_window(season)
    ranked = (
        User.objects
        .annotate(
            events_count=Count("usertoevent", filter=window, distinct=True),
            total_points=Coalesce(Sum("usertoevent__points", filter=window), 0),
        )
        .filter(total_points__gt=0)
        .order_by("-total_points")
    )
    return create_leaderboard(ranked)


def season_rank(season, season_pts):
    """1-based rank for a points total within a season, or None if no points."""
    if season_pts <= 0:
        return None
    higher = (
        UserToEvent.objects
        .filter(
            event__date__date__gte=season.start_date,
            event__date__date__lte=season.end_date,
        )
        .values("user")
        .annotate(pts=Sum("points"))
        .filter(pts__gt=season_pts)
        .count()
    )
    return higher + 1


def top_players(limit=5):
    """Top `limit` users by total points, each annotated with a 1-based rank."""
    players = (
        User.objects
        .annotate(
            total_points=Coalesce(Sum("usertoevent__points"), 0),
            events_count=Count("usertoevent", distinct=True),
        )
        .filter(total_points__gt=0)
        .order_by("-total_points")[:limit]
    )
    result = []
    for i, player in enumerate(players, start=1):
        player.rank = i
        result.append(player)
    return result


def attach_profile_usernames(players):
    """Annotate each leaderboard User with `profile_username` + `photo` (if they
    have a registered account with an avatar). The photo lets the leaderboard
    render a small avatar instead of just initials."""
    if not players:
        return players
    ids = [p.pk for p in players]
    from accounts.models import Profile
    from leaderboard.privacy import profile_has_consent, public_handle
    # Consent is resolved in this same query rather than per player — the
    # leaderboard renders hundreds of rows and a lookup inside _entry would be
    # one query each.
    info_by_lb_user = {
        prof.leaderboard_user_id: (
            # public_handle withholds e-mail-shaped usernames — see privacy.py.
            public_handle(prof.user.username),
            prof.photo.url if prof.photo else None,
            profile_has_consent(prof),
        )
        for prof in Profile.objects.filter(leaderboard_user_id__in=ids).select_related("user")
    }
    for player in players:
        username, photo, consented = info_by_lb_user.get(player.pk, (None, None, False))
        player.profile_username = username
        player.photo = photo
        player.name_consented = consented
    return players


def _entry(player):
    """Shape one ranked user into the leaderboard-entry dict the API returns."""
    from leaderboard.privacy import display_name
    return {
        "id": player.id,
        # Shortened to "Jan N." unless the player registered and consented — see
        # leaderboard/privacy.py. Defaults to False so any caller that forgets
        # to annotate publishes less, not more.
        "name": display_name(player.name, consented=getattr(player, "name_consented", False)),
        "rank": getattr(player, "rank", 0),
        "total_points": getattr(player, "total_points", 0),
        "events_count": getattr(player, "events_count", 0),
        "profile_username": getattr(player, "profile_username", None),
        "photo": getattr(player, "photo", None),
    }


def entries_payload(players):
    """Serialize an iterable of ranked, profile-annotated users to entry dicts."""
    return [_entry(p) for p in players]


def season_payload(season):
    """Season metadata for the leaderboard response (None → all-time)."""
    return season_dict(season) if season else None


def resolve_season(param):
    """Resolve a ?season_id= value to ``(season_or_None, cache_id)`` for the leaderboard.

    ``all`` → all-time; ``active``/blank → active season (or all-time if none).
    A numeric id resolves that season. Raises ``Season.DoesNotExist`` for an
    unknown id and ``ValueError`` for an otherwise invalid value.
    """
    param = (param or "active").strip()
    if param == "all":
        return None, "all"
    if param == "active":
        season = Season.objects.filter(is_active=True).first()
        return season, (season.id if season else "all")
    if param.isdigit():
        season = Season.objects.filter(pk=int(param)).first()
        if season is None:
            raise Season.DoesNotExist(param)
        return season, season.id
    raise ValueError(param)


def resolve_season_filter(season_id):
    """Resolve a ?season_id= value for list filters → a Season or None (no filter).

    blank/``all`` → None; a numeric id resolves that season. Raises
    ``Season.DoesNotExist`` for an unknown id and ``ValueError`` for junk.
    """
    param = (season_id or "").strip()
    if param in ("", "all"):
        return None
    if param.isdigit():
        season = Season.objects.filter(pk=int(param)).first()
        if season is None:
            raise Season.DoesNotExist(param)
        return season
    raise ValueError(param)


def cached_leaderboard_entries(season, cache_id):
    """Profile-annotated entry dicts for a season (or all-time), cached per season."""
    key = season_leaderboard_key(cache_id)
    entries = cache.get(key)
    if entries is None:
        ranked = create_leaderboard(leaderboard_total()) if season is None \
            else leaderboard_for_season(season)
        entries = entries_payload(attach_profile_usernames(ranked))
        cache.set(key, entries, CACHE_TTL)
    return entries


def player_payload(lb_user, request=None):
    """Public profile for a leaderboard user by id — works whether or not they
    have a registered account (leaderboard users come from the Google Sheets sync).

    `request` is optional only so existing callers keep working; pass it so badge
    image URLs come back absolute (the mobile app can't resolve relative ones).

    Returns totals, all-time rank, the linked account's username (if any), and the
    full list of attended events (newest first).
    """
    agg = UserToEvent.objects.filter(user=lb_user).aggregate(
        total_points=Sum("points"),
        events_count=Count("id"),
    )
    total_points = agg["total_points"] or 0
    events_count = agg["events_count"] or 0

    rank = None
    if total_points > 0:
        rank = (
            User.objects
            .annotate(tp=Coalesce(Sum("usertoevent__points"), 0))
            .filter(tp__gt=total_points).count()
        ) + 1

    # Local imports — avoid app-load cycle (accounts depends on leaderboard).
    from accounts.models import Profile
    from accounts.services import season_summaries
    profile = (
        Profile.objects.filter(leaderboard_user=lb_user).select_related("user").first()
    )

    from leaderboard.privacy import (
        display_name, profile_has_consent, public_handle, visibility_for,
    )
    from leaderboard.services.badges import badges_for

    # Same privacy flags as /profiles/<username>/. This endpoint reaches the same
    # person by leaderboard id instead of username, so enforcing them only there
    # would leave the flag trivially bypassable by switching endpoint.
    # Computed before the event query so a hidden history costs nothing to serve.
    gates = visibility_for(profile, getattr(request, "user", None))

    events = []
    if not gates.hide_events:
        events = [
            {
                "slug": u.event.slug,
                "name": u.event.name,
                "place": u.event.place,
                "date": u.event.date,
                "points": u.points,
                "category": {"id": u.event.category.id, "name": u.event.category.name}
                            if u.event.category else None,
            }
            for u in (
                UserToEvent.objects
                .filter(user=lb_user)
                .select_related("event", "event__category")
                .order_by("-event__date")
            )
        ]

    payload = {
        "id": lb_user.id,
        "name": display_name(lb_user.name, consented=profile_has_consent(profile)),
        # public_handle withholds e-mail-shaped usernames — see privacy.py.
        "profile_username": public_handle(profile.user.username) if profile else None,
        "badges": badges_for(lb_user, request),
        "hidden": [
            name for name, hidden in (
                ("points", gates.hide_pts),
                ("events", gates.hide_events),
            ) if hidden
        ],
    }
    if not gates.hide_pts:
        payload["total_points"] = total_points
        payload["events_count"] = events_count
        payload["rank"] = rank
    if not gates.hide_events:
        payload["events"] = events
        payload["seasons"] = season_summaries(lb_user)
    return payload
