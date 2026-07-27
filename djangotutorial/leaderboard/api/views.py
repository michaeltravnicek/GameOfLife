from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control, never_cache

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin, IsAdminOrPhotographer, is_admin, is_close_or_above, is_staff_role
from leaderboard.checkin import validate_and_record_checkin
from leaderboard.models import (
    Badge,
    Event,
    EventFeedback,
    EventRSVP,
    PhotoLike,
    Season,
    User as LeaderboardUser,
    UserPhoto,
)
from leaderboard.services import (
    active_checkin_events,
    add_event_images,
    admin_feedback_list,
    attendee_payload,
    attendees_for_event,
    cached_leaderboard_entries,
    categories_cached,
    cities_cached,
    create_user_photo,
    gallery_page,
    home_stats,
    list_events,
    pick_hero_events,
    player_payload,
    remove_attendance,
    resolve_season,
    resolve_season_filter,
    rsvps_for_event,
    season_payload,
    seasons_cached,
    set_attendance,
)
from leaderboard.utils import parse_int_param

from accounts.api.serializers import SeasonDetailSerializer
from .serializers import (
    AdminFeedbacksResponseSerializer,
    AttendeeSerializer,
    AttendeesResponseSerializer,
    AttendeeWriteSerializer,
    BadgeSerializer,
    BadgeWriteSerializer,
    CategoriesResponseSerializer,
    CategorySerializer,
    CheckinEventsResponseSerializer,
    CheckinSerializer,
    EventDetailSerializer,
    EventListSerializer,
    EventWriteSerializer,
    FeedbackSerializer,
    GalleryResponseSerializer,
    HeroResponseSerializer,
    LeaderboardResponseSerializer,
    PhotoUploadSerializer,
    PlayerDetailSerializer,
    RsvpsResponseSerializer,
    SeasonsResponseSerializer,
    StatsResponseSerializer,
)

_SEASON_NOT_FOUND = {"error": "Sezóna nenalezena."}
_SEASON_INVALID = {"error": "Neplatný parametr 'season_id'."}


def _offset_param(default):
    return OpenApiParameter("offset", int, description=f"Rows to skip (default {default}).")


def _limit_param(default, maximum):
    return OpenApiParameter(
        "limit", int, description=f"Page size (default {default}, max {maximum}).")


# season_id on list filters: an id, or "all"/blank for no filter.
_SEASON_FILTER_PARAM = OpenApiParameter(
    "season_id", str,
    description='Season id to filter by, or "all"/omit for no season filter.')

# season_id on the leaderboard: an id, "active" (default) or "all".
_SEASON_BOARD_PARAM = OpenApiParameter(
    "season_id", str,
    description='Season id, "active" (default — the current season) or "all" for all-time.')


@extend_schema(tags=['Events'],
    operation_id="events_list",
    parameters=[
        OpenApiParameter("period", str, enum=["all", "upcoming", "past"],
                         description='Time filter (default "all").'),
        OpenApiParameter("city", str, description="Filter by place (exact, case-insensitive)."),
        OpenApiParameter("category", int, description="Filter by category id."),
        OpenApiParameter("q", str, description="Full-text search over name/description."),
        _SEASON_FILTER_PARAM,
        _offset_param(0),
        _limit_param(30, 100),
    ],
    responses=inline_serializer("EventListResponse", {
        "events": EventListSerializer(many=True),
        "count": drf_serializers.IntegerField(),
        "has_more": drf_serializers.BooleanField(),
        "cities": inline_serializer("EventCity", {
            "name": drf_serializers.CharField(),
            "count": drf_serializers.IntegerField(),
        }, many=True),
        "categories": CategorySerializer(many=True),
    }),
)
@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def events_list(request):
    """List events with filters + offset/limit pagination.

    Params: period, city, category, q, season_id, offset, limit. Response:
    `{events, count, has_more, cities, categories}` — cities/categories on page 0 only.
    """
    offset = parse_int_param(request.GET.get("offset"), 0, min_val=0)
    limit = parse_int_param(request.GET.get("limit"), 30, min_val=1, max_val=100)
    try:
        season = resolve_season_filter(request.GET.get("season_id"))
    except Season.DoesNotExist:
        return Response(_SEASON_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response(_SEASON_INVALID, status=status.HTTP_400_BAD_REQUEST)

    # Visibility tiers: admin sees everything, close + photographer see the
    # close-preview pool, everyone else sees only visible_to_users=True.
    _is_admin = is_admin(request.user)
    _is_close_preview = is_close_or_above(request.user) and not _is_admin
    page, total = list_events(
        period=request.GET.get("period", "all"),
        city=request.GET.get("city", ""),
        category=request.GET.get("category", ""),
        q=request.GET.get("q", "").strip(),
        season=season,
        offset=offset,
        limit=limit,
        include_hidden=_is_admin,
        include_close_preview=_is_close_preview,
    )
    if offset == 0:
        from django.db.models import Count as _Count, Q as _Q
        city_qs = Event.objects.exclude(place="")
        if not _is_admin:
            if _is_close_preview:
                city_qs = city_qs.filter(_Q(visible_to_users=True) | _Q(visible_to_close=True))
            else:
                city_qs = city_qs.filter(visible_to_users=True)
        if season is not None:
            city_qs = city_qs.filter(
                date__date__gte=season.start_date,
                date__date__lte=season.end_date,
            )
        cities_data = [
            {"name": c["place"], "count": c["count"]}
            for c in city_qs.values("place").annotate(count=_Count("id")).order_by("place")
        ]
    else:
        cities_data = []

    return Response({
        "events": EventListSerializer(page, many=True, context={"request": request}).data,
        "count": total,
        "has_more": (offset + limit) < total,
        "cities": cities_data,
        "categories": categories_cached() if offset == 0 else [],
    }, status=status.HTTP_200_OK)


@extend_schema(tags=['Events'], operation_id="event_detail", responses=EventDetailSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def event_detail(request, slug):
    """Full detail for a single event (hidden events are 404 for non-admin)."""
    event = get_object_or_404(Event, slug=slug)
    if not event.visible_to_users:
        # Hidden events: admin sees everything; close + photographer see only
        # the ones explicitly flagged visible_to_close; everyone else gets 404.
        allowed = is_admin(request.user) or (
            is_close_or_above(request.user) and event.visible_to_close
        )
        if not allowed:
            return Response({"error": "Akce nenalezena."}, status=status.HTTP_404_NOT_FOUND)
    serializer = EventDetailSerializer(event, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=['Events'],
    request=None,
    responses=inline_serializer("RsvpResponse", {
        "rsvp": drf_serializers.BooleanField(),
        "rsvp_count": drf_serializers.IntegerField(),
    }),
)
@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def event_rsvp(request, slug):
    """Set (PUT) or remove (DELETE) the current user's RSVP. Idempotent —
    a retried request confirms the state instead of inverting it (mobile
    clients retry after timeouts). PUT respects capacity (409 when full).
    """
    # Lock the event row so the capacity check + create below are serialized:
    # without it two concurrent requests can both pass the count check and
    # oversell the event (TOCTOU).
    event = get_object_or_404(Event.objects.select_for_update(), slug=slug)

    if request.method == "DELETE":
        EventRSVP.objects.filter(auth_user=request.user, event=event).delete()
        return Response({"rsvp": False, "rsvp_count": event.rsvps.count()},
                        status=status.HTTP_200_OK)

    if EventRSVP.objects.filter(auth_user=request.user, event=event).exists():
        return Response({"rsvp": True, "rsvp_count": event.rsvps.count()},
                        status=status.HTTP_200_OK)
    if event.capacity is not None and event.rsvps.count() >= event.capacity:
        return Response({"error": "Akce je plně obsazena."},
                        status=status.HTTP_409_CONFLICT)
    EventRSVP.objects.create(auth_user=request.user, event=event)
    return Response({"rsvp": True, "rsvp_count": event.rsvps.count()},
                    status=status.HTTP_201_CREATED)


@extend_schema(tags=['Events'],
    request=FeedbackSerializer,
    responses={
        200: inline_serializer("FeedbackUpdatedResponse", {"ok": drf_serializers.BooleanField()}),
        201: inline_serializer("FeedbackCreatedResponse", {"ok": drf_serializers.BooleanField()}),
    },
    examples=[OpenApiExample("Rating with comment",
        value={"rating": 5, "comment": "Skvělá akce!"}, request_only=True)],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def event_feedback(request, slug):
    """Create or update the current user's 1–10 rating + comment for an event."""
    event = get_object_or_404(Event, slug=slug)
    serializer = FeedbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Feedback is keyed on the leaderboard user (form submissions have no auth
    # account). An account with no linked leaderboard user has no attendance
    # either, so it could not have reached this endpoint legitimately.
    profile = getattr(request.user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None
    if lb_user is None:
        return Response({"error": "Účet není propojen s hráčem v žebříčku."},
                        status=status.HTTP_400_BAD_REQUEST)

    _, created = EventFeedback.objects.update_or_create(
        user=lb_user, event=event,
        defaults={**serializer.validated_data, "source": EventFeedback.SOURCE_WEB},
    )
    return Response(
        {"ok": True},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Leaderboard"],
    parameters=[
        _SEASON_BOARD_PARAM,
        OpenApiParameter("limit", int, description="Top-N entries (default 0 = all, max 100)."),
    ],
    responses=LeaderboardResponseSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def leaderboard_view(request):
    """Season-scoped leaderboard. ?season_id=<id|active|all> (default active), ?limit=N."""
    try:
        season, cache_id = resolve_season(request.GET.get("season_id"))
    except Season.DoesNotExist:
        return Response(_SEASON_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response(_SEASON_INVALID, status=status.HTTP_400_BAD_REQUEST)

    entries = cached_leaderboard_entries(season, cache_id)
    limit = parse_int_param(request.GET.get("limit"), 0, min_val=0, max_val=100)
    if limit:
        entries = entries[:limit]
    return Response({"season": season_payload(season), "entries": entries},
                    status=status.HTTP_200_OK)


@extend_schema(tags=["Leaderboard"], responses=SeasonsResponseSerializer)
@cache_control(public=True, max_age=3600)
@api_view(["GET"])
@permission_classes([AllowAny])
def seasons_list(request):
    """All seasons for the season selector. Response: `{seasons: [...]}`."""
    return Response({"seasons": seasons_cached()}, status=status.HTTP_200_OK)


@extend_schema(tags=["Leaderboard"], responses=PlayerDetailSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def player_detail(request, user_id):
    """Public profile for a leaderboard player by id (registered or not).

    Lists the events they attended. `profile_username` is set if the player has a
    linked account (so the frontend can redirect to the full /profiles/ page).
    """
    lb_user = get_object_or_404(LeaderboardUser, id=user_id)
    return Response(player_payload(lb_user, request), status=status.HTTP_200_OK)


@extend_schema(tags=["Leaderboard"], responses=SeasonDetailSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def player_season_detail(request, user_id, season_id):
    """One season's events/points/rank for a leaderboard player (lazy per tab).

    Mirrors the profile season endpoint but keyed by leaderboard-user id, so it
    works for Google-Sheets players who have no account.
    """
    from accounts.models import Profile
    from accounts.services import season_detail  # local import — avoid app-load cycle
    from leaderboard.privacy import visibility_for
    lb_user = get_object_or_404(LeaderboardUser, id=user_id)
    season = get_object_or_404(Season, pk=season_id)
    # Fourth and last way to reach one person's event history — see visibility_for.
    profile = Profile.objects.filter(leaderboard_user=lb_user).first()
    if visibility_for(profile, request.user).hide_events:
        raise Http404("Event history is hidden.")
    return Response(season_detail(lb_user, season), status=status.HTTP_200_OK)


@extend_schema(
    tags=["Gallery"],
    parameters=[_SEASON_FILTER_PARAM, _offset_param(0), _limit_param(60, 200)],
    responses=GalleryResponseSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def gallery_view(request):
    """Combined gallery (official + user photos), date-desc, offset/limit paginated.

    Optional ?season_id filters to photos whose event falls within that season.
    """
    offset = parse_int_param(request.GET.get("offset"), 0, min_val=0)
    limit = parse_int_param(request.GET.get("limit"), 60, min_val=1, max_val=200)
    try:
        season = resolve_season_filter(request.GET.get("season_id"))
    except Season.DoesNotExist:
        return Response(_SEASON_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response(_SEASON_INVALID, status=status.HTTP_400_BAD_REQUEST)

    photos, total = gallery_page(offset, limit, request, season=season)
    return Response({
        "photos": photos,
        "count": total,
        "has_more": (offset + limit) < total,
    }, status=status.HTTP_200_OK)


@extend_schema(tags=["Home"], responses=StatsResponseSerializer)
@cache_control(public=True, max_age=1800)
@api_view(["GET"])
@permission_classes([AllowAny])
def stats_view(request):
    """Global counters for the home 'about' block. Response: `{players, events, points}`."""
    return Response(home_stats(), status=status.HTTP_200_OK)


@extend_schema(tags=["Home"], responses=HeroResponseSerializer)
@cache_control(public=True, max_age=3600)
@api_view(["GET"])
@permission_classes([AllowAny])
def hero_view(request):
    """Hero carousel images (absolute URLs). Response: `{hero_events: [...]}`."""
    hero_data = []
    for h in pick_hero_events(5):
        url = h["url"]
        if not url.startswith("http"):
            url = request.build_absolute_uri(url)
        hero_data.append({"url": url, "name": h["name"], "date": h["date"], "slug": h["slug"]})
    return Response({"hero_events": hero_data}, status=status.HTTP_200_OK)


@extend_schema(tags=["Events"], responses=CheckinEventsResponseSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def checkin_events_view(request):
    """Events the current user can check into right now (`[]` for guests)."""
    return Response({"events": active_checkin_events(request.user)}, status=status.HTTP_200_OK)


@extend_schema(tags=['Events'],
    request=CheckinSerializer,
    responses=inline_serializer("CheckinResponse", {
        "ok": drf_serializers.BooleanField(),
        "error": drf_serializers.CharField(required=False),
        "distance_m": drf_serializers.IntegerField(required=False),
        "points": drf_serializers.IntegerField(required=False),
        "already_had": drf_serializers.BooleanField(required=False),
    }),
    examples=[OpenApiExample("Brno coordinates",
        value={"latitude": 49.1951, "longitude": 16.6068}, request_only=True)],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def event_checkin(request, slug):
    """Submit geo-verified attendance. Body: {latitude, longitude}."""
    event = get_object_or_404(
        Event.objects.only(
            "id", "slug", "name", "date", "end_date",
            "points", "latitude", "longitude", "checkin_radius",
        ),
        slug=slug,
    )
    serializer = CheckinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = validate_and_record_checkin(
        event, request.user,
        serializer.validated_data["latitude"], serializer.validated_data["longitude"],
    )
    payload = {"ok": result.ok}
    if result.error:
        payload["error"] = result.error
    if result.distance_m is not None:
        payload["distance_m"] = result.distance_m
    if result.ok:
        payload["points"] = result.points
        payload["already_had"] = not result.created
    return Response(payload, status=result.status)


@extend_schema(tags=["Events"], responses=CategoriesResponseSerializer)
@cache_control(public=True, max_age=3600)
@api_view(["GET"])
@permission_classes([AllowAny])
def categories_list(request):
    """All event categories. Response: `{categories: [{id, name}]}`."""
    return Response({"categories": categories_cached()}, status=status.HTTP_200_OK)


@extend_schema(tags=['Gallery'],
    request=PhotoUploadSerializer,
    responses=inline_serializer("PhotoUploadResponse", {
        "id": drf_serializers.IntegerField(),
        "url": drf_serializers.URLField(),
        "caption": drf_serializers.CharField(),
        "event_slug": drf_serializers.CharField(),
        "uploaded_by": drf_serializers.CharField(),
        "created_at": drf_serializers.DateTimeField(),
    }),
)
@api_view(["POST"])
@permission_classes([IsAdminOrPhotographer])
def photo_upload(request):
    """Upload a community gallery photo (admin/photographer only, downscaled on save).

    Multipart body: `image` (required), `event` (optional event slug), `caption`.
    """
    serializer = PhotoUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            photo = create_user_photo(
                request.user, data["image"],
                event_slug=data["event"],
                caption=data["caption"],
            )
            payload = {
                "id": photo.id,
                "url": request.build_absolute_uri(photo.image.url),
                "caption": photo.caption,
                "event_slug": photo.event.slug if photo.event else "",
                "uploaded_by": photo.auth_user.get_full_name() or photo.auth_user.username,
                "created_at": photo.created_at,
            }
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except LookupError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Gallery'],
    request=None,
    responses=inline_serializer("PhotoLikeResponse", {
        "liked": drf_serializers.BooleanField(),
        "count": drf_serializers.IntegerField(),
    }),
)
@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def photo_like(request, photo_id):
    """Set (PUT) or remove (DELETE) the current user's like on a photo.

    Idempotent, same reasoning as `event_rsvp`. Response: `{liked, count}`.
    """
    photo = get_object_or_404(UserPhoto, id=photo_id)
    if request.method == "DELETE":
        PhotoLike.objects.filter(photo=photo, auth_user=request.user).delete()
        return Response({"liked": False, "count": photo.likes.count()},
                        status=status.HTTP_200_OK)
    _, created = PhotoLike.objects.get_or_create(photo=photo, auth_user=request.user)
    return Response({"liked": True, "count": photo.likes.count()},
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@extend_schema(tags=['Events'],
    request=inline_serializer("EventImagesRequest", {
        "images": drf_serializers.ListField(child=drf_serializers.ImageField(), required=False),
        "image": drf_serializers.ImageField(required=False),
    }),
    responses=inline_serializer("EventImagesResponse", {
        "images": drf_serializers.ListField(child=drf_serializers.URLField()),
        "count": drf_serializers.IntegerField(),
    }),
)
@api_view(["POST"])
@permission_classes([IsAdminOrPhotographer])
def event_images_upload(request, slug):
    """Attach official images to an event (admin/photographer only, downscaled on save).

    Multipart body: `images` (one or many) or a single `image`.
    """
    event = get_object_or_404(Event, slug=slug)
    files = request.FILES.getlist("images")
    if not files and "image" in request.FILES:
        files = [request.FILES["image"]]
    if not files:
        return Response({"error": "Nahraj prosím obrázky."}, status=status.HTTP_400_BAD_REQUEST)
    # Each file is size/pixel-capped individually by validate_upload, but the
    # list itself was unbounded — 500 files x 15 MB is still 7.5 GB of decoding.
    max_files = getattr(settings, "MAX_UPLOAD_FILES_PER_REQUEST", 30)
    if len(files) > max_files:
        return Response(
            {"error": f"Najednou lze nahrát maximálně {max_files} obrázků."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        with transaction.atomic():
            created = add_event_images(event, files)
            payload = {
                "images": [request.build_absolute_uri(i.image.url) for i in created],
                "count": len(created),
            }
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Admin"], responses=AdminFeedbacksResponseSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_feedbacks(request):
    """All event feedback (admin only) with submitter name + attended-event count."""
    return Response({"feedbacks": admin_feedback_list()}, status=status.HTTP_200_OK)


@extend_schema(tags=["Events"], responses=BadgeSerializer(many=True))
@api_view(["GET"])
@permission_classes([AllowAny])
def badges_list(request):
    """Every badge, for the event form's logo picker and the badge overview.

    Public: the artwork is already visible on event cards, and a name+image list
    is what a collector wants to see before earning one.
    """
    badges = Badge.objects.all()  # Meta.ordering = name
    return Response(
        {"badges": BadgeSerializer(badges, many=True, context={"request": request}).data},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Events"], request=BadgeWriteSerializer, responses=BadgeSerializer)
@api_view(["POST"])
@permission_classes([IsAdmin])
def badge_create(request):
    """Create a badge (admin only). Multipart: name, image, image_scale, description.

    This is the only way new event artwork enters the system now — which is the
    point: one upload, then every edition of the event points at the same row.
    """
    serializer = BadgeWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        badge = serializer.save()
        payload = BadgeSerializer(badge, context={"request": request}).data
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Events'], request=EventWriteSerializer, responses=EventDetailSerializer)
@api_view(["POST"])
@permission_classes([IsAdmin])
def event_create(request):
    """Create a new event (admin only). Multipart body with event fields."""
    serializer = EventWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # Atomic: if response serialization raises, the half-created row rolls back.
    with transaction.atomic():
        event = serializer.save()
        payload = EventDetailSerializer(event, context={"request": request}).data
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Events'], request=EventWriteSerializer, responses=EventDetailSerializer)
@api_view(["PATCH"])
@permission_classes([IsAdmin])
def event_update(request, slug):
    """Update an event (admin only). Multipart body; absent fields stay unchanged."""
    event = get_object_or_404(Event, slug=slug)
    serializer = EventWriteSerializer(event, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        event = serializer.save()
        payload = EventDetailSerializer(event, context={"request": request}).data
    return Response(payload, status=status.HTTP_200_OK)


@extend_schema(tags=['Events'], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAdmin])
def event_delete(request, slug):
    """Delete an event (admin only).

    Cascades to awarded points, RSVPs, feedback and photos — leaderboard
    totals change, so the points-dependent caches are dropped.
    """
    event = get_object_or_404(Event, slug=slug)
    with transaction.atomic():
        event.delete()
    from leaderboard.cache_config import invalidate_points_dependent_caches
    invalidate_points_dependent_caches()
    # 204: the resource is gone, there is nothing meaningful to return.
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Events"], responses=AttendeesResponseSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([IsAdmin])
def event_attendees(request, slug):
    """Who actually attended this event and how many points they got (admin).

    Attendance = UserToEvent rows (from check-in or the Sheets sync), which is
    what feeds the leaderboard — distinct from RSVPs (see `event_rsvps`).
    """
    event = get_object_or_404(Event, slug=slug)
    return Response({"attendees": attendees_for_event(event)}, status=status.HTTP_200_OK)


@extend_schema(methods=["PUT"], tags=["Events"],
               request=AttendeeWriteSerializer, responses=AttendeeSerializer)
@extend_schema(methods=["DELETE"], tags=["Events"], request=None,
               responses=inline_serializer("AttendeeDeleteResponse",
                                           {"ok": drf_serializers.BooleanField()}))
@api_view(["PUT", "DELETE"])
@permission_classes([IsAdmin])
@transaction.atomic
def event_attendee_detail(request, slug, user_id):
    """Set/add (PUT) or remove (DELETE) one leaderboard user's attendance (admin).

    PUT body: `{points}`. Creates the attendance row if it doesn't exist (201)
    or updates the points (200). DELETE removes it. Both change leaderboard
    totals, so the points-dependent caches are dropped by the service layer.
    `user_id` is a leaderboard-user id (the same id used by /players/<id>/).
    """
    event = get_object_or_404(Event, slug=slug)
    lb_user = get_object_or_404(LeaderboardUser, id=user_id)

    if request.method == "DELETE":
        remove_attendance(event, lb_user)
        return Response({"ok": True}, status=status.HTTP_200_OK)

    serializer = AttendeeWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ute, created = set_attendance(event, lb_user, serializer.validated_data["points"])
    return Response(
        attendee_payload(lb_user, ute.points),
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(tags=["Events"], responses=RsvpsResponseSerializer)
@never_cache
@api_view(["GET"])
@permission_classes([IsAdmin])
def event_rsvps(request, slug):
    """Everyone signed up (RSVP'd) for this event (admin).

    RSVPs = intentions to attend (EventRSVP); distinct from actual attendance
    with points (see `event_attendees`).
    """
    event = get_object_or_404(Event, slug=slug)
    return Response({"rsvps": rsvps_for_event(event)}, status=status.HTTP_200_OK)
