import json
import math
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Event,
    EventFeedback,
    EventRSVP,
    ImageToEvent,
    User,
    UserPhoto,
    UserToEvent,
)
from .serializers import (
    EventDetailSerializer,
    EventListSerializer,
    GalleryPhotoSerializer,
    LeaderboardEntrySerializer,
)
from .views import (
    CACHE_KEY,
    CACHE_KEY_HOME_CONTEXT,
    CACHE_KEY_MONTH,
    _attach_profile_usernames,
    _pick_hero_events,
    _top_players,
    create_leaderboard,
    leaderboard_month,
    leaderboard_total,
)


_EVENTS_LIST_FIELDS = (
    "id", "slug", "name", "description", "place",
    "date", "points", "image", "capacity",
)
CACHE_KEY_EVENTS_CITIES = "api_events_cities"
CACHE_TTL_EVENTS_CITIES = 30 * 60  # 30 min — places change slowly


def _cities_cached():
    """Cities + counts. Cached because the set changes slowly and the query
    scans the whole Event table."""
    cached = cache.get(CACHE_KEY_EVENTS_CITIES)
    if cached is not None:
        return cached
    cities_qs = (
        Event.objects.exclude(place="")
        .values("place")
        .annotate(count=Count("id"))
        .order_by("place")
    )
    result = [{"name": c["place"], "count": c["count"]} for c in cities_qs]
    cache.set(CACHE_KEY_EVENTS_CITIES, result, CACHE_TTL_EVENTS_CITIES)
    return result


@api_view(["GET"])
@permission_classes([AllowAny])
def events_list(request):
    """List events with filters and offset/limit pagination.

    Query params:
      ?period=upcoming|past|all
      ?city=<name>
      ?q=<search>
      ?limit=<1..100>  default 30
      ?offset=<int>    default 0

    Response:
      { events, count, has_more, cities }
    `cities` is included only on the first page (offset=0) to save bandwidth.
    """
    period = request.GET.get("period", "all")
    city = request.GET.get("city", "")
    q = request.GET.get("q", "").strip()

    try:
        limit = min(max(int(request.GET.get("limit", 30)), 1), 100)
    except (TypeError, ValueError):
        limit = 30
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    # .only() — fetch ONLY the columns the list serializer needs.
    # Skips heavy fields like rules (TextField), latitude/longitude,
    # checkin_radius, end_date, logo, sheet_id/sheet_list_id.
    qs = Event.objects.only(*_EVENTS_LIST_FIELDS).order_by("-date")

    now = timezone.now()
    if period == "upcoming":
        qs = qs.filter(date__gte=now).order_by("date")
    elif period == "past":
        qs = qs.filter(date__lt=now)

    if city:
        qs = qs.filter(place__iexact=city)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    total = qs.count()
    page = qs[offset:offset + limit]
    serializer = EventListSerializer(page, many=True, context={"request": request})

    return Response({
        "events": serializer.data,
        "count": total,
        "has_more": (offset + limit) < total,
        "cities": _cities_cached() if offset == 0 else [],
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    serializer = EventDetailSerializer(event, context={"request": request})
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_rsvp_toggle(request, slug):
    event = get_object_or_404(Event, slug=slug)
    rsvp = EventRSVP.objects.filter(auth_user=request.user, event=event).first()
    if rsvp:
        rsvp.delete()
        return Response({"rsvp": False, "rsvp_count": event.rsvps.count()})

    rsvp_count = event.rsvps.count()
    if event.capacity is not None and rsvp_count >= event.capacity:
        return Response(
            {"error": "Akce je plně obsazena."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    EventRSVP.objects.create(auth_user=request.user, event=event)
    return Response({"rsvp": True, "rsvp_count": event.rsvps.count()})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_feedback(request, slug):
    event = get_object_or_404(Event, slug=slug)
    try:
        rating = int(request.data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if rating < 1 or rating > 5:
        return Response({"error": "Rating musí být 1–5."}, status=400)

    comment = (request.data.get("comment") or "").strip()
    EventFeedback.objects.update_or_create(
        auth_user=request.user, event=event,
        defaults={"rating": rating, "comment": comment},
    )
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def leaderboard_view(request):
    period = request.GET.get("period", "total")

    cached_t = cache.get(CACHE_KEY)
    cached_m = cache.get(CACHE_KEY_MONTH)
    if cached_t is None:
        cached_t = create_leaderboard(leaderboard_total())
        cache.set(CACHE_KEY, cached_t, 5 * 60)
    if cached_m is None:
        cached_m = create_leaderboard(leaderboard_month())
        cache.set(CACHE_KEY_MONTH, cached_m, 5 * 60)

    chosen = cached_m if period == "month" else cached_t
    _attach_profile_usernames(chosen)

    data = [
        {
            "id": p.id,
            "name": p.name,
            "rank": getattr(p, "rank", 0),
            "total_points": getattr(p, "total_points", 0),
            "events_count": getattr(p, "events_count", 0),
            "profile_username": getattr(p, "profile_username", None),
        }
        for p in chosen
    ]
    return Response({"period": period, "entries": data})


@api_view(["GET"])
@permission_classes([AllowAny])
def gallery_view(request):
    """Combined gallery: official + user photos with pagination.

    Query params:
      ?limit=<1..200>  default 60
      ?offset=<int>    default 0

    Response: { photos, count, has_more }
    """
    try:
        limit = min(max(int(request.GET.get("limit", 60)), 1), 200)
    except (TypeError, ValueError):
        limit = 60
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    # .only() — restrict each queryset to columns we actually serialize.
    # Combined with select_related, this means a single JOIN that pulls a
    # tiny subset of columns instead of full Event / User rows.
    official = (
        ImageToEvent.objects
        .select_related("event_id")
        .exclude(image="")
        .filter(image__isnull=False)
        .only(
            "image",
            "event_id__name", "event_id__slug", "event_id__date",
        )
        .order_by("-event_id__date")
    )
    user_photos = (
        UserPhoto.objects
        .select_related("auth_user", "event")
        .exclude(image="")
        .filter(image__isnull=False)
        .only(
            "image", "created_at",
            "event__name", "event__slug", "event__date",
            "auth_user__first_name", "auth_user__last_name", "auth_user__username",
        )
        .order_by("-created_at")
    )

    total = official.count() + user_photos.count()

    photos = []
    for img in official:
        if not img.image:
            continue
        date = img.event_id.date if img.event_id else None
        photos.append({
            "url": request.build_absolute_uri(img.image.url),
            "event_name": img.event_id.name if img.event_id else "",
            "event_slug": img.event_id.slug if img.event_id else "",
            "event_date": date,
            "is_user_photo": False,
            "uploaded_by": "",
        })
    for up in user_photos:
        if not up.image:
            continue
        date = up.event.date if up.event else None
        photos.append({
            "url": request.build_absolute_uri(up.image.url),
            "event_name": up.event.name if up.event else "",
            "event_slug": up.event.slug if up.event else "",
            "event_date": date,
            "is_user_photo": True,
            "uploaded_by": up.auth_user.get_full_name() or up.auth_user.username,
        })

    # Merge sort by event_date desc; None dates sink to the bottom.
    from datetime import datetime, timezone as _tz
    _SORT_FALLBACK = datetime.min.replace(tzinfo=_tz.utc)
    photos.sort(key=lambda p: p["event_date"] or _SORT_FALLBACK, reverse=True)

    page = photos[offset:offset + limit]
    serializer = GalleryPhotoSerializer(page, many=True)

    return Response({
        "photos": serializer.data,
        "count": total,
        "has_more": (offset + limit) < total,
    })


CACHE_KEY_HOME_STATS = "api_home_stats"
CACHE_TTL_HOME_STATS = 30 * 60  # 30 min — counts change slowly enough


def _home_stats_cached():
    """Three counters that scan large tables. Cached because they're
    expensive AND stale data for half an hour is harmless for an 'about' block.
    """
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


def _active_checkin_events(user):
    """Events the given user can currently check into.

    Mirrors leaderboard.views.home_view's logic but for the API. Only
    authenticated users with a leaderboard profile see anything.
    """
    if not user or not user.is_authenticated:
        return []

    from accounts.models import Profile  # local import — avoid app-load loop

    profile = (
        Profile.objects
        .filter(user=user)
        .select_related("leaderboard_user")
        .first()
    )
    lb_user = profile.leaderboard_user if profile else None
    if lb_user is None:
        return []

    now = timezone.now()
    candidates = (
        Event.objects
        .only("id", "slug", "name", "date", "end_date", "points",
              "latitude", "longitude", "checkin_radius")
        .filter(
            latitude__isnull=False,
            longitude__isnull=False,
            date__lte=now + timedelta(minutes=30),
        )
        .order_by("date")
    )

    already_in_ids = set(
        UserToEvent.objects
        .filter(user=lb_user, event__in=candidates)
        .values_list("event_id", flat=True)
    )

    result = []
    for ev in candidates:
        if now > ev.checkin_window_end:
            continue
        if ev.id in already_in_ids:
            continue
        result.append({
            "slug": ev.slug,
            "name": ev.name,
            "date": ev.date,
            "points": ev.points,
            "latitude": ev.latitude,
            "longitude": ev.longitude,
            "checkin_radius": ev.checkin_radius,
            "checkin_window_end": ev.checkin_window_end,
        })
    return result


@api_view(["GET"])
@permission_classes([AllowAny])
def home_view(request):
    """Aggregated payload for HomePage: hero images, upcoming events, top players, stats."""
    now = timezone.now()

    upcoming_qs = (
        Event.objects
        .only(*_EVENTS_LIST_FIELDS)
        .filter(date__gte=now)
        .order_by("date")[:3]
    )
    upcoming = EventListSerializer(upcoming_qs, many=True, context={"request": request}).data

    top = _attach_profile_usernames(_top_players(10))
    top_data = [
        {
            "id": p.id,
            "name": p.name,
            "rank": getattr(p, "rank", 0),
            "total_points": getattr(p, "total_points", 0),
            "profile_username": getattr(p, "profile_username", None),
        }
        for p in top
    ]

    hero = _pick_hero_events(5)
    hero_data = []
    for h in hero:
        url = h["url"]
        if not url.startswith("http"):
            url = request.build_absolute_uri(url)
        hero_data.append({
            "url": url,
            "name": h["name"],
            "date": h["date"],
            "slug": h["slug"],
        })

    return Response({
        "hero_events": hero_data,
        "upcoming_events": upcoming,
        "top_players": top_data,
        "about_stats": _home_stats_cached(),
        "active_checkin_events": _active_checkin_events(request.user),
    })


# --------------------------------------------------------------------------
# Event check-in (geolocation-gated)
# --------------------------------------------------------------------------

def _haversine_distance_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_checkin(request, slug):
    """Submit geo-verified attendance. Body: {latitude, longitude}.

    Mirrors leaderboard.views.event_checkin_view but JSON-only for the React
    client. Awards `event.points` if the user is within `event.checkin_radius`
    meters and the time window is open.
    """
    event = get_object_or_404(
        Event.objects.only("id", "slug", "name", "date", "end_date",
                           "points", "latitude", "longitude", "checkin_radius"),
        slug=slug,
    )

    if event.latitude is None or event.longitude is None:
        return Response({"ok": False, "error": "Tato akce nemá aktivní check-in."}, status=400)

    now = timezone.now()
    window_open = event.date - timedelta(minutes=30)
    if not (window_open <= now <= event.checkin_window_end):
        return Response({"ok": False, "error": "Check-in je mimo časové okno akce."}, status=400)

    try:
        lat = float(request.data.get("latitude"))
        lon = float(request.data.get("longitude"))
    except (TypeError, ValueError):
        return Response({"ok": False, "error": "Neplatné souřadnice."}, status=400)

    distance = _haversine_distance_m(lat, lon, event.latitude, event.longitude)
    if distance > event.checkin_radius:
        return Response({
            "ok": False,
            "error": (
                f"Jsi příliš daleko ({distance / 1000:.1f} km). "
                f"Check-in vyžaduje být do {event.checkin_radius} m."
            ),
            "distance_m": round(distance),
        }, status=400)

    from accounts.models import Profile
    profile = (
        Profile.objects
        .filter(user=request.user)
        .select_related("leaderboard_user")
        .first()
    )
    lb_user = profile.leaderboard_user if profile else None
    if lb_user is None:
        return Response(
            {"ok": False, "error": "Tvůj účet není propojen s leaderboardem."},
            status=400,
        )

    _, created = UserToEvent.objects.get_or_create(
        user=lb_user, event=event, defaults={"points": event.points},
    )
    if created:
        # Drop leaderboards + home cache so the new points show immediately.
        cache.delete(CACHE_KEY)
        cache.delete(CACHE_KEY_MONTH)
        cache.delete(CACHE_KEY_HOME_CONTEXT)
        cache.delete(CACHE_KEY_HOME_STATS)

    return Response({
        "ok": True,
        "points": event.points if created else 0,
        "already_had": not created,
        "distance_m": round(distance),
    })
