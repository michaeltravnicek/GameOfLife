"""Home page data: hero carousel, about-stats, and the active check-in feed."""
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from leaderboard.cache_config import (
    CACHE_KEY_HERO_IMAGES,
    CACHE_KEY_HOME_STATS,
    CACHE_TTL_HERO_IMAGES,
    CACHE_TTL_HOME_STATS,
)
from leaderboard.models import Event, User, UserToEvent


def pick_hero_events(count=5):
    """Up to `count` distinct past events with images for the hero carousel (cached 1h)."""
    cached = cache.get(CACHE_KEY_HERO_IMAGES)
    if cached is not None:
        return cached

    now = timezone.now()
    media_url = settings.MEDIA_URL
    events = list(
        Event.objects
        .only("name", "date", "slug", "image")
        .filter(date__lt=now, visible_to_users=True)
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-date")[:count * 3]
    )
    result = []
    seen_names = set()
    for event in events:
        if event.name in seen_names:
            continue
        seen_names.add(event.name)
        result.append({
            "url": f"{media_url}{event.image}",
            "name": event.name,
            "date": event.date,
            "slug": event.slug,
        })
        if len(result) >= count:
            break

    cache.set(CACHE_KEY_HERO_IMAGES, result, CACHE_TTL_HERO_IMAGES)
    return result


def home_stats():
    """Player/event/point counters for the home 'about' block (cached 30 min)."""
    cached = cache.get(CACHE_KEY_HOME_STATS)
    if cached is not None:
        return cached
    stats = {
        "players": User.objects.count(),
        "events": Event.objects.count(),
        "points": UserToEvent.objects.aggregate(s=Sum("points"))["s"] or 0,
    }
    cache.set(CACHE_KEY_HOME_STATS, stats, CACHE_TTL_HOME_STATS)
    return stats


def active_checkin_events(user):
    """Events currently in their check-in window with location set.

    Authenticated + leaderboard-linked users see only events they haven't
    already attended. Guests (and authenticated users without a leaderboard
    link) see every active event — the frontend prompts them to log in when
    they tap the check-in button.
    """
    lb_user = None
    if user and user.is_authenticated:
        from accounts.models import Profile  # local import — avoid app-load loop
        profile = (
            Profile.objects
            .filter(user=user)
            .select_related("leaderboard_user")
            .first()
        )
        lb_user = profile.leaderboard_user if profile else None

    now = timezone.now()
    candidates = (
        Event.objects
        .only("id", "slug", "name", "date", "end_date", "points",
              "latitude", "longitude", "checkin_radius")
        .filter(
            latitude__isnull=False,
            longitude__isnull=False,
            visible_to_users=True,
            date__lte=now + timedelta(minutes=30),
        )
        .order_by("date")
    )

    already_in_ids = set()
    if lb_user is not None:
        already_in_ids = set(
            UserToEvent.objects
            .filter(user=lb_user, event__in=candidates)
            .values_list("event_id", flat=True)
        )

    result = []
    for event in candidates:
        if now > event.checkin_window_end or event.id in already_in_ids:
            continue
        result.append({
            "slug": event.slug,
            "name": event.name,
            "date": event.date,
            "points": event.points,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "checkin_radius": event.checkin_radius,
            "checkin_window_end": event.checkin_window_end,
        })
    return result
