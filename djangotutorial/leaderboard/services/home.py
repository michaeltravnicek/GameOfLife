"""Home page data: hero carousel and the active check-in feed."""
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from leaderboard.cache_config import (
    CACHE_KEY_HERO_IMAGES,
    CACHE_TTL_HERO_IMAGES,
)
from leaderboard.image_utils import variant_url
from leaderboard.models import Event, UserToEvent


def pick_hero_events(count=5):
    """Up to `count` distinct past events with images for the hero carousel (cached 1h)."""
    cached = cache.get(CACHE_KEY_HERO_IMAGES)
    if cached is not None:
        return cached

    now = timezone.now()
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
            # Both URLs must come from the storage backend, never from
            # MEDIA_URL: on S3/R2 the backend answers with the CDN host while
            # MEDIA_URL stays "/media/", a local-disk route holding nothing
            # uploaded after the cutover. Hand-building this one left the hero
            # serving mobile variants from the CDN and 404ing the full sizes.
            "url": event.image.url,
            "url_mobile": variant_url(event.image),
            "name": event.name,
            "date": event.date,
            "slug": event.slug,
        })
        if len(result) >= count:
            break

    cache.set(CACHE_KEY_HERO_IMAGES, result, CACHE_TTL_HERO_IMAGES)
    return result


def active_checkin_events(user):
    """Events currently in their check-in window with location set.

    Authenticated + leaderboard-linked users see only events they haven't
    already attended. Guests (and authenticated users without a leaderboard
    link) see every active event — the frontend prompts them to log in when
    they tap the check-in button.
    """
    from accounts.models import leaderboard_user_for  # local import — avoid app-load loop

    lb_user = leaderboard_user_for(user)

    now = timezone.now()
    candidates = (
        Event.objects
        .only("id", "slug", "name", "date", "end_date", "points",
              "latitude", "longitude", "checkin_radius")
        .filter(
            latitude__isnull=False,
            longitude__isnull=False,
            visible_to_users=True,
            date__lte=now + Event.CHECKIN_PRE_WINDOW,
        )
        # Lower bound on the window, so this stays a handful of rows instead
        # of every geo-located event ever held.
        .filter(
            Q(end_date__gte=now)
            | Q(end_date__isnull=True, date__gte=now - Event.CHECKIN_DEFAULT_LENGTH)
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
