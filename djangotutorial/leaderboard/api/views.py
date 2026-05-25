from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin, IsAdminOrPhotographer, is_staff_role
from leaderboard.checkin import validate_and_record_checkin
from leaderboard.models import (
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
    cached_leaderboard_entries,
    categories_cached,
    cities_cached,
    create_user_photo,
    gallery_page,
    home_stats,
    list_events,
    pick_hero_events,
    player_payload,
    resolve_season,
    resolve_season_filter,
    season_payload,
    seasons_cached,
)
from leaderboard.utils import parse_int_param

from .serializers import EventDetailSerializer, EventListSerializer

_SEASON_NOT_FOUND = {"error": "Sezóna nenalezena."}
_SEASON_INVALID = {"error": "Neplatný parametr 'season_id'."}


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

    page, total = list_events(
        period=request.GET.get("period", "all"),
        city=request.GET.get("city", ""),
        category=request.GET.get("category", ""),
        q=request.GET.get("q", "").strip(),
        season=season,
        offset=offset,
        limit=limit,
        include_hidden=is_staff_role(request.user),
    )
    return Response({
        "events": EventListSerializer(page, many=True, context={"request": request}).data,
        "count": total,
        "has_more": (offset + limit) < total,
        "cities": cities_cached() if offset == 0 else [],
        "categories": categories_cached() if offset == 0 else [],
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def event_detail(request, slug):
    """Full detail for a single event (hidden events are 404 for non-staff)."""
    event = get_object_or_404(Event, slug=slug)
    if not event.visible_to_users and not is_staff_role(request.user):
        return Response({"error": "Akce nenalezena."}, status=status.HTTP_404_NOT_FOUND)
    serializer = EventDetailSerializer(event, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_rsvp_toggle(request, slug):
    """Toggle the current user's RSVP for an event (respects capacity)."""
    event = get_object_or_404(Event, slug=slug)
    rsvp = EventRSVP.objects.filter(auth_user=request.user, event=event).first()
    if rsvp:
        rsvp.delete()
        return Response({"rsvp": False, "rsvp_count": event.rsvps.count()},
                        status=status.HTTP_200_OK)

    if event.capacity is not None and event.rsvps.count() >= event.capacity:
        return Response({"error": "Akce je plně obsazena."},
                        status=status.HTTP_400_BAD_REQUEST)
    EventRSVP.objects.create(auth_user=request.user, event=event)
    return Response({"rsvp": True, "rsvp_count": event.rsvps.count()},
                    status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_feedback(request, slug):
    """Create or update the current user's 1–5 rating + comment for an event."""
    event = get_object_or_404(Event, slug=slug)
    try:
        rating = int(request.data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if rating < 1 or rating > 5:
        return Response({"error": "Rating musí být 1–5."}, status=status.HTTP_400_BAD_REQUEST)

    comment = (request.data.get("comment") or "").strip()
    EventFeedback.objects.update_or_create(
        auth_user=request.user, event=event,
        defaults={"rating": rating, "comment": comment},
    )
    return Response({"ok": True}, status=status.HTTP_200_OK)


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


@cache_control(public=True, max_age=3600)
@api_view(["GET"])
@permission_classes([AllowAny])
def seasons_list(request):
    """All seasons for the season selector. Response: `{seasons: [...]}`."""
    return Response({"seasons": seasons_cached()}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def player_detail(request, user_id):
    """Public profile for a leaderboard player by id (registered or not).

    Lists the events they attended. `profile_username` is set if the player has a
    linked account (so the frontend can redirect to the full /profiles/ page).
    """
    lb_user = get_object_or_404(LeaderboardUser, id=user_id)
    return Response(player_payload(lb_user), status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def player_season_detail(request, user_id, season_id):
    """One season's events/points/rank for a leaderboard player (lazy per tab).

    Mirrors the profile season endpoint but keyed by leaderboard-user id, so it
    works for Google-Sheets players who have no account.
    """
    from accounts.services import season_detail  # local import — avoid app-load cycle
    lb_user = get_object_or_404(LeaderboardUser, id=user_id)
    season = get_object_or_404(Season, pk=season_id)
    return Response(season_detail(lb_user, season), status=status.HTTP_200_OK)


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


@cache_control(public=True, max_age=1800)
@api_view(["GET"])
@permission_classes([AllowAny])
def stats_view(request):
    """Global counters for the home 'about' block. Response: `{players, events, points}`."""
    return Response(home_stats(), status=status.HTTP_200_OK)


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


@api_view(["GET"])
@permission_classes([AllowAny])
def checkin_events_view(request):
    """Events the current user can check into right now (`[]` for guests)."""
    return Response({"events": active_checkin_events(request.user)}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def event_checkin(request, slug):
    """Submit geo-verified attendance. Body: {latitude, longitude}."""
    event = get_object_or_404(
        Event.objects.only(
            "id", "slug", "name", "date", "end_date",
            "points", "latitude", "longitude", "checkin_radius",
        ),
        slug=slug,
    )
    result = validate_and_record_checkin(
        event, request.user,
        request.data.get("latitude"), request.data.get("longitude"),
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


@cache_control(public=True, max_age=3600)
@api_view(["GET"])
@permission_classes([AllowAny])
def categories_list(request):
    """All event categories. Response: `{categories: [{id, name}]}`."""
    return Response({"categories": categories_cached()}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAdminOrPhotographer])
def photo_upload(request):
    """Upload a community gallery photo (admin/photographer only, downscaled on save).

    Multipart body: `image` (required), `event` (optional event slug), `caption`.
    """
    image = request.FILES.get("image")
    if not image:
        return Response({"error": "Nahraj prosím obrázek."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        photo = create_user_photo(
            request.user, image,
            event_slug=request.data.get("event", ""),
            caption=request.data.get("caption", ""),
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except LookupError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        "id": photo.id,
        "url": request.build_absolute_uri(photo.image.url),
        "caption": photo.caption,
        "event_slug": photo.event.slug if photo.event else "",
        "uploaded_by": photo.auth_user.get_full_name() or photo.auth_user.username,
        "created_at": photo.created_at,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def photo_like_toggle(request, photo_id):
    """Toggle the current user's like on a community photo. Response: `{liked, count}`."""
    photo = get_object_or_404(UserPhoto, id=photo_id)
    like, created = PhotoLike.objects.get_or_create(photo=photo, user=request.user)
    if not created:
        like.delete()
    return Response({"liked": created, "count": photo.likes.count()},
                    status=status.HTTP_200_OK)


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
    try:
        created = add_event_images(event, files)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "images": [request.build_absolute_uri(i.image.url) for i in created],
        "count": len(created),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_feedbacks(request):
    """All event feedback (admin only) with submitter name + attended-event count."""
    return Response({"feedbacks": admin_feedback_list()}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAdmin])
def event_create(request):
    """Create a new event (admin only). Multipart body with event fields."""
    try:
        name = request.data.get('name', '').strip()
        if not name:
            return Response({"error": "Název akce je povinný."}, status=status.HTTP_400_BAD_REQUEST)

        date_str = request.data.get('date', '')
        date = None
        if date_str:
            from datetime import datetime
            try:
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return Response({"error": "Neplatný formát data."}, status=status.HTTP_400_BAD_REQUEST)

        place = request.data.get('place', '').strip()
        points = int(request.data.get('points', 0)) if request.data.get('points') else 0
        capacity = int(request.data.get('capacity')) if request.data.get('capacity') else None
        description = request.data.get('description', '').strip()
        rules = request.data.get('rules', '').strip()
        survey_url = request.data.get('survey_url', '').strip()
        visible_to_users = request.data.get('visible_to_users', '1') in ('1', 'true', 'True')

        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        try:
            latitude = float(latitude) if latitude else None
            longitude = float(longitude) if longitude else None
        except (ValueError, TypeError):
            latitude = longitude = None

        checkin_radius = int(request.data.get('checkin_radius', 500)) if request.data.get('checkin_radius') else 500
        category_id = request.data.get('category')
        category = None
        if category_id:
            from leaderboard.models import Category
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        event = Event.objects.create(
            name=name,
            date=date,
            place=place,
            points=points,
            capacity=capacity,
            description=description,
            rules=rules,
            survey_url=survey_url,
            visible_to_users=visible_to_users,
            latitude=latitude,
            longitude=longitude,
            checkin_radius=checkin_radius,
            category=category,
        )

        if 'image' in request.FILES:
            event.image = request.FILES['image']
        if 'logo' in request.FILES:
            event.logo = request.FILES['logo']

        event.save()

        return Response(
            EventDetailSerializer(event, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
@permission_classes([IsAdmin])
def event_update(request, slug):
    """Update an event (admin only). Multipart body with event fields to update."""
    try:
        event = get_object_or_404(Event, slug=slug)

        if 'name' in request.data:
            event.name = request.data.get('name', '').strip()

        if 'date' in request.data:
            date_str = request.data.get('date', '')
            if date_str:
                from datetime import datetime
                try:
                    event.date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    return Response({"error": "Neplatný formát data."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                event.date = None

        if 'place' in request.data:
            event.place = request.data.get('place', '').strip()
        if 'points' in request.data:
            event.points = int(request.data.get('points', 0)) if request.data.get('points') else 0
        if 'capacity' in request.data:
            event.capacity = int(request.data.get('capacity')) if request.data.get('capacity') else None
        if 'description' in request.data:
            event.description = request.data.get('description', '').strip()
        if 'rules' in request.data:
            event.rules = request.data.get('rules', '').strip()
        if 'survey_url' in request.data:
            event.survey_url = request.data.get('survey_url', '').strip()
        if 'visible_to_users' in request.data:
            event.visible_to_users = request.data.get('visible_to_users', '1') in ('1', 'true', 'True')

        if 'latitude' in request.data or 'longitude' in request.data:
            try:
                lat = request.data.get('latitude')
                lon = request.data.get('longitude')
                event.latitude = float(lat) if lat else None
                event.longitude = float(lon) if lon else None
            except (ValueError, TypeError):
                event.latitude = event.longitude = None

        if 'checkin_radius' in request.data:
            event.checkin_radius = int(request.data.get('checkin_radius', 500))

        if 'category' in request.data:
            category_id = request.data.get('category')
            if category_id:
                from leaderboard.models import Category
                try:
                    event.category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    event.category = None
            else:
                event.category = None

        if 'image' in request.FILES:
            event.image = request.FILES['image']
        if 'logo' in request.FILES:
            event.logo = request.FILES['logo']

        event.save()

        return Response(
            EventDetailSerializer(event, context={"request": request}).data,
            status=status.HTTP_200_OK
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
