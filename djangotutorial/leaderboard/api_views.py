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


@api_view(["GET"])
@permission_classes([AllowAny])
def events_list(request):
    """List events with filters: ?period=upcoming|past|all & ?city= & ?q="""
    period = request.GET.get("period", "all")
    city = request.GET.get("city", "")
    q = request.GET.get("q", "").strip()

    qs = Event.objects.all().order_by("-date")
    now = timezone.now()
    if period == "upcoming":
        qs = qs.filter(date__gte=now).order_by("date")
    elif period == "past":
        qs = qs.filter(date__lt=now)

    if city:
        qs = qs.filter(place__iexact=city)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    serializer = EventListSerializer(qs, many=True, context={"request": request})

    cities_qs = (
        Event.objects.exclude(place="")
        .values("place")
        .annotate(count=Count("id"))
        .order_by("place")
    )
    cities = [{"name": c["place"], "count": c["count"]} for c in cities_qs]

    return Response({"events": serializer.data, "cities": cities})


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
    """Combined gallery: official + user photos."""
    photos = []
    request_for_url = request

    official = (
        ImageToEvent.objects.select_related("event_id")
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-event_id__date")
    )
    for img in official:
        if not img.image:
            continue
        date = img.event_id.date if img.event_id else None
        photos.append({
            "url": request_for_url.build_absolute_uri(img.image.url),
            "event_name": img.event_id.name if img.event_id else "",
            "event_slug": img.event_id.slug if img.event_id else "",
            "event_date": date,
            "is_user_photo": False,
            "uploaded_by": "",
        })

    user_photos = (
        UserPhoto.objects.select_related("auth_user", "event")
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-created_at")
    )
    for up in user_photos:
        if not up.image:
            continue
        date = up.event.date if up.event else None
        photos.append({
            "url": request_for_url.build_absolute_uri(up.image.url),
            "event_name": up.event.name if up.event else "",
            "event_slug": up.event.slug if up.event else "",
            "event_date": date,
            "is_user_photo": True,
            "uploaded_by": up.auth_user.get_full_name() or up.auth_user.username,
        })

    serializer = GalleryPhotoSerializer(photos, many=True)
    return Response({"photos": serializer.data})


@api_view(["GET"])
@permission_classes([AllowAny])
def home_view(request):
    """Aggregated payload for HomePage: hero images, upcoming events, top players, stats."""
    now = timezone.now()

    upcoming_qs = Event.objects.filter(date__gte=now).order_by("date")[:3]
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

    stats = {
        "players": User.objects.count(),
        "events": Event.objects.count(),
        "points": UserToEvent.objects.aggregate(s=Sum("points"))["s"] or 0,
    }

    return Response({
        "hero_events": hero_data,
        "upcoming_events": upcoming,
        "top_players": top_data,
        "about_stats": stats,
    })
