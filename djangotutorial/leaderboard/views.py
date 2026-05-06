import json
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Event,
    EventFeedback,
    EventRSVP,
    ImageToEvent,
    LastUpdate,
    PhotoLike,
    User,
    UserPhoto,
    UserToEvent,
)


MINUTES = 5
CACHE_KEY = "leaderboard_data"
CACHE_TTL = MINUTES * 60
CACHE_KEY_MONTH = "leaderboard_data_month"

# RAM optimization: cache heavy queries
CACHE_KEY_HERO_IMAGES = "home_hero_images"
CACHE_TTL_HERO_IMAGES = 60 * 60  # 1 hour — images rarely change
CACHE_KEY_HOME_CONTEXT = "home_context"
CACHE_TTL_HOME_CONTEXT = 5 * 60  # 5 min — stats/upcoming
CACHE_KEY_EVENTS_LIST = "events_list"
CACHE_TTL_EVENTS_LIST = 5 * 60

def get_month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def get_year_start():
    now = timezone.now()
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def leaderboard_total():
    return (
        User.objects
        .annotate(
            events_count=Count("usertoevent", distinct=True),
            total_points=Coalesce(Sum("usertoevent__points"), 0),
        )
        .order_by("-total_points")
    )


def leaderboard_month():
    first_day = get_year_start()
    return (
        User.objects
        .annotate(
            events_count=Count(
                "usertoevent",
                filter=Q(usertoevent__event__date__gte=first_day),
                distinct=True,
            ),
            total_points=Coalesce(
                Sum(
                    "usertoevent__points",
                    filter=Q(usertoevent__event__date__gte=first_day),
                ),
                0,
            ),
        )
        .filter(total_points__gt=0)
        .order_by("-total_points")
    )


def create_leaderboard(leaderboard):
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


def _top_players(limit=5):
    players = (
        User.objects
        .annotate(total_points=Coalesce(Sum("usertoevent__points"), 0))
        .filter(total_points__gt=0)
        .order_by("-total_points")[:limit]
    )
    result = []
    for i, p in enumerate(players, start=1):
        p.rank = i
        result.append(p)
    return result


def _attach_profile_usernames(players):
    """Attach `profile_username` attribute to each leaderboard.User if they have an auth account."""
    if not players:
        return players
    ids = [p.pk for p in players]
    from accounts.models import Profile
    map_ = {
        prof.leaderboard_user_id: prof.user.username
        for prof in Profile.objects.filter(leaderboard_user_id__in=ids).select_related("user")
    }
    for p in players:
        p.profile_username = map_.get(p.pk)
    return players


def _pick_hero_events(count=5):
    """Return up to `count` past events with images for the hero carousel.

    Cached for 1 hour. Each item is a dict with url, name, date, slug.
    """
    cached = cache.get(CACHE_KEY_HERO_IMAGES)
    if cached is not None:
        return cached

    now = timezone.now()
    media_url = settings.MEDIA_URL
    events = list(
        Event.objects
        .filter(date__lt=now)
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-date")[:count * 3]
    )
    result = []
    seen_names = set()
    for ev in events:
        if ev.name in seen_names:
            continue
        seen_names.add(ev.name)
        result.append({
            "url": f"{media_url}{ev.image}",
            "name": ev.name,
            "date": ev.date,
            "slug": ev.slug,
        })
        if len(result) >= count:
            break

    cache.set(CACHE_KEY_HERO_IMAGES, result, CACHE_TTL_HERO_IMAGES)
    return result


def home_view(request):
    # Cache the expensive context (stats, top_players, upcoming events) for 5 min
    cached = cache.get(CACHE_KEY_HOME_CONTEXT)
    if cached is None:
        now = timezone.now()
        upcoming_events = list(
            Event.objects.filter(date__gte=now).order_by("date")[:3]
        )
        top_players = _attach_profile_usernames(_top_players(10))
        about_stats = {
            "players": User.objects.count(),
            "events": Event.objects.count(),
            "points": UserToEvent.objects.aggregate(s=Sum("points"))["s"] or 0,
        }
        cached = {
            "upcoming_events": upcoming_events,
            "top_players": top_players,
            "about_stats": about_stats,
        }
        cache.set(CACHE_KEY_HOME_CONTEXT, cached, CACHE_TTL_HOME_CONTEXT)

    # Hero events cached separately (1 hour)
    hero_events = _pick_hero_events(5)

    return render(request, "home.html", {
        "upcoming_events": cached["upcoming_events"],
        "top_players": cached["top_players"],
        "hero_events": hero_events,
        "about_stats": cached["about_stats"],
    })


def leaderboard_view(request):
    leaderboard_list_t = cache.get(CACHE_KEY)
    leaderboard_list_m = cache.get(CACHE_KEY_MONTH)

    if leaderboard_list_t is None:
        leaderboard_list_t = create_leaderboard(leaderboard_total())
        cache.set(CACHE_KEY, leaderboard_list_t, CACHE_TTL)

        leaderboard_list_m = create_leaderboard(leaderboard_month())
        cache.set(CACHE_KEY_MONTH, leaderboard_list_m, CACHE_TTL)
    elif leaderboard_list_m is None:
        leaderboard_list_m = create_leaderboard(leaderboard_month())
        cache.set(CACHE_KEY_MONTH, leaderboard_list_m, CACHE_TTL)

    _attach_profile_usernames(leaderboard_list_t)
    _attach_profile_usernames(leaderboard_list_m)

    last_update_obj = LastUpdate.objects.first()
    last_update_ts = int(last_update_obj.last_update.timestamp()) if last_update_obj else 0
    month_start_ts = int(get_month_start().timestamp())

    return render(request, "leaderboard.html", {
        "leaderboard_month": leaderboard_list_m,
        "leaderboard_total": leaderboard_list_t,
        "last_update_ts": last_update_ts,
        "month_start_ts": month_start_ts,
    })


def user_detail_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    qs = (
        UserToEvent.objects
        .filter(user=user)
        .select_related("event")
        .annotate(user_points=F("points"))
    )

    from_date_ts = request.GET.get("from_date")
    if from_date_ts:
        try:
            from_dt = datetime.fromtimestamp(int(from_date_ts), tz=dt_timezone.utc)
            qs = qs.filter(event__date__gte=from_dt)
        except (ValueError, TypeError):
            pass

    actions = qs.values(
        "event__name",
        "event__description",
        "event__place",
        "event__date",
        "user_points",
    ).order_by("event__date")

    return JsonResponse({"user_name": user.name, "actions": list(actions)})


def about_points_view(request):
    return render(request, "about_points.html")


def historie_view(request):
    return render(request, "historie.html")


def events_view(request):
    cached = cache.get(CACHE_KEY_EVENTS_LIST)
    if cached is None:
        events = list(Event.objects.all().order_by("-date"))
        today = timezone.now().date()
        for event in events:
            event.is_past = event.date.date() < today if event.date else False

        city_counts = {}
        for e in events:
            if e.place:
                city_counts[e.place] = city_counts.get(e.place, 0) + 1
        cities = [{"name": name, "count": city_counts[name]} for name in sorted(city_counts)]

        cached = {"events": events, "cities": cities}
        cache.set(CACHE_KEY_EVENTS_LIST, cached, CACHE_TTL_EVENTS_LIST)

    return render(request, "events.html", cached)


def events_image_views(request, event_id: str):
    event = get_object_or_404(Event, id=event_id)
    images = [
        request.build_absolute_uri(img.image.url)
        for img in ImageToEvent.objects.filter(event_id=event)
        if img.image
    ]
    return JsonResponse({"event_id": event_id, "images": images})


def event_detail_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    now = timezone.now()
    is_future = event.date >= now

    has_rsvp = False
    existing_feedback = None
    if request.user.is_authenticated:
        has_rsvp = EventRSVP.objects.filter(auth_user=request.user, event=event).exists()
        existing_feedback = EventFeedback.objects.filter(
            auth_user=request.user, event=event
        ).first()

    official_images = [
        request.build_absolute_uri(img.image.url)
        for img in ImageToEvent.objects.filter(event_id=event)
        if img.image
    ]

    user_photos = [
        {
            "url": request.build_absolute_uri(up.image.url),
            "uploaded_by": up.auth_user.get_full_name() or up.auth_user.username,
            "caption": up.caption,
        }
        for up in UserPhoto.objects.filter(event=event).select_related("auth_user")
        if up.image
    ]

    rsvp_count = EventRSVP.objects.filter(event=event).count()
    is_full = event.capacity is not None and rsvp_count >= event.capacity

    # Combined list for lightbox (official first, then user)
    all_images_json = json.dumps(
        official_images + [p["url"] for p in user_photos]
    )

    return render(request, "event_detail.html", {
        "event": event,
        "is_future": is_future,
        "has_rsvp": has_rsvp,
        "existing_feedback": existing_feedback,
        "official_images": official_images,
        "user_photos": user_photos,
        "all_images_json": all_images_json,
        "rsvp_count": rsvp_count,
        "is_full": is_full,
    })


@login_required
@require_http_methods(["POST"])
def event_rsvp_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    rsvp = EventRSVP.objects.filter(auth_user=request.user, event=event).first()
    if rsvp:
        rsvp.delete()
        messages.info(request, f"Odhlášeno z akce {event.name}.")
    else:
        rsvp_count = EventRSVP.objects.filter(event=event).count()
        if event.capacity is not None and rsvp_count >= event.capacity:
            messages.error(request, f"Akce {event.name} je plně obsazena.")
        else:
            EventRSVP.objects.create(auth_user=request.user, event=event)
            messages.success(request, f"Přihlášeno na akci {event.name}.")
    return redirect("event_detail", slug=slug)


def gallery_view(request):
    # Official photos (from ImageToEvent)
    official_qs = (
        ImageToEvent.objects
        .select_related("event_id")
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-event_id__date")
    )
    season_names = {}
    js_official = []
    for img in official_qs:
        if not img.image:
            continue
        date = img.event_id.date if img.event_id else None
        year_key = str(date.year) if date else ""
        if year_key and year_key not in season_names:
            season_names[year_key] = f"Sezóna {date.year}"
        js_official.append({
            "url": img.image.url,
            "event_name": img.event_id.name if img.event_id else "",
            "event_slug": img.event_id.slug if img.event_id else "",
            "event_date": date.strftime("%d. %m. %Y") if date else "",
            "month": int(date.month) if date else 0,
            "season": year_key,
            "is_user_photo": False,
            "uploaded_by": "",
        })

    # User-uploaded photos
    user_qs = (
        UserPhoto.objects
        .select_related("auth_user", "event")
        .exclude(image="")
        .filter(image__isnull=False)
        .order_by("-created_at")
    )
    js_user = []
    for up in user_qs:
        if not up.image:
            continue
        date = up.event.date if up.event else None
        year_key = str(date.year) if date else ""
        if year_key and year_key not in season_names:
            season_names[year_key] = f"Sezóna {date.year}"
        js_user.append({
            "id": up.id,
            "url": up.image.url,
            "event_name": up.event.name if up.event else "",
            "event_slug": up.event.slug if up.event else "",
            "event_date": date.strftime("%d. %m. %Y") if date else "",
            "month": int(date.month) if date else 0,
            "season": year_key,
            "is_user_photo": True,
            "uploaded_by": up.auth_user.get_full_name() or up.auth_user.username,
        })

    # Like counts and current user's liked IDs for community photos
    user_photo_ids = [p["id"] for p in js_user]
    like_counts = {
        str(row["photo_id"]): row["c"]
        for row in PhotoLike.objects.filter(photo_id__in=user_photo_ids)
        .values("photo_id")
        .annotate(c=Count("id"))
    }
    liked_ids = []
    if request.user.is_authenticated:
        liked_ids = list(
            PhotoLike.objects.filter(photo_id__in=user_photo_ids, user=request.user)
            .values_list("photo_id", flat=True)
        )

    # Events for upload form selector
    events_for_form = list(
        Event.objects.filter(date__lt=timezone.now()).order_by("-date").values("id", "name", "date")
    )

    return render(request, "gallery.html", {
        "js_official": json.dumps(js_official),
        "js_user": json.dumps(js_user),
        "season_names_json": json.dumps(season_names),
        "like_counts_json": json.dumps(like_counts),
        "liked_ids_json": json.dumps(liked_ids),
        "events_for_form": events_for_form,
    })


@login_required
@require_http_methods(["POST"])
def upload_user_photo_view(request):
    image = request.FILES.get("image")
    if not image:
        messages.error(request, "Žádná fotografie nebyla nahrána.")
        return redirect(request.POST.get("next") or "gallery")

    event_id = request.POST.get("event_id")
    event = None
    if event_id:
        event = Event.objects.filter(pk=event_id).first()

    caption = (request.POST.get("caption") or "").strip()[:255]
    UserPhoto.objects.create(auth_user=request.user, event=event, image=image, caption=caption)
    messages.success(request, "Fotografie nahrána, díky!")
    return redirect(request.POST.get("next") or "gallery")


@login_required
@require_http_methods(["POST"])
def toggle_photo_like_view(request, photo_id):
    photo = get_object_or_404(UserPhoto, id=photo_id)
    like, created = PhotoLike.objects.get_or_create(photo=photo, user=request.user)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    return JsonResponse({"liked": liked, "count": photo.likes.count()})


def public_user_view(request, user_id):
    leaderboard_user = get_object_or_404(User, pk=user_id)
    past_events_qs = (
        UserToEvent.objects
        .filter(user=leaderboard_user)
        .select_related("event")
        .order_by("-event__date")
    )
    return render(request, "leaderboard/public_user.html", {
        "leaderboard_user": leaderboard_user,
        "past_events": past_events_qs,
    })


def profile_monthly_points_api(request, username):
    from django.contrib.auth.models import User as AuthUser
    auth_user = get_object_or_404(AuthUser, username=username)
    profile = getattr(auth_user, "profile", None)
    leaderboard_user = profile.leaderboard_user if profile else None

    try:
        year = int(request.GET.get("year", timezone.now().year))
    except (TypeError, ValueError):
        year = timezone.now().year

    monthly = []
    if leaderboard_user is not None:
        rows = (
            UserToEvent.objects
            .filter(user=leaderboard_user, event__date__year=year)
            .annotate(month=TruncMonth("event__date"))
            .values("month")
            .annotate(total=Sum("points"))
            .order_by("month")
        )
        monthly = [{"month": r["month"].month, "points": r["total"] or 0} for r in rows]

    return JsonResponse({"year": year, "monthly": monthly})


@login_required
@require_http_methods(["POST"])
def event_feedback_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    rating_raw = request.POST.get("rating")
    comment = (request.POST.get("comment") or "").strip()
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 0
    if rating < 1 or rating > 5:
        messages.error(request, "Vyber prosím rating 1–5.")
        return redirect("event_detail", slug=slug)

    EventFeedback.objects.update_or_create(
        auth_user=request.user,
        event=event,
        defaults={"rating": rating, "comment": comment},
    )

    # Award attendance points if not yet received
    from accounts.models import Profile
    profile = Profile.objects.filter(user=request.user).select_related("leaderboard_user").first()
    lb_user = profile.leaderboard_user if profile else None
    if lb_user is not None:
        _, created = UserToEvent.objects.get_or_create(
            user=lb_user,
            event=event,
            defaults={"points": event.points},
        )
        if created:
            cache.delete(CACHE_KEY)
            cache.delete(CACHE_KEY_MONTH)
            cache.delete(CACHE_KEY_HOME_CONTEXT)
            messages.success(request, f"Zpětná vazba uložena a připsáno {event.points} bodů za účast!")
        else:
            messages.success(request, "Díky za zpětnou vazbu!")
    else:
        messages.success(request, "Díky za zpětnou vazbu!")

    return redirect("event_detail", slug=slug)
