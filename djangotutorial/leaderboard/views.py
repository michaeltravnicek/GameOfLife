import json
import multiprocessing
import random
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connections
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
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
    User,
    UserToEvent,
)
from .tasks import main


MINUTES = 5
CACHE_KEY = "leaderboard_data"
CACHE_TTL = MINUTES * 60
CACHE_KEY_MONTH = "leaderboard_data_month"

MONTH_DAYS = None
YEAR_DAYS = None


def get_month_start():
    now = timezone.now()
    if MONTH_DAYS is None:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=MONTH_DAYS)


def get_year_start():
    now = timezone.now()
    if YEAR_DAYS is None:
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=YEAR_DAYS)


def leaderboard_total():
    return (
        User.objects
        .annotate(
            events_count=Count("usertoevent", distinct=True),
            total_points=Sum("usertoevent__points"),
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


def _pick_hero_images(count=12):
    """Pick a list of image URLs from ImageToEvent + Event, up to `count`."""
    urls = []
    for img in ImageToEvent.objects.exclude(image="").filter(image__isnull=False)[:200]:
        if img.image:
            urls.append(img.image.url)
    for ev in Event.objects.exclude(image="").filter(image__isnull=False)[:200]:
        if ev.image:
            urls.append(ev.image.url)
    urls = list(dict.fromkeys(urls))  # de-dupe, keep order
    random.shuffle(urls)
    if not urls:
        return []
    # Repeat to ensure we have `count` tiles
    while len(urls) < count:
        urls.extend(urls[: count - len(urls)])
    return urls[:count]


def home_view(request):
    now = timezone.now()
    upcoming_events = list(
        Event.objects.filter(date__gte=now).order_by("date")[:3]
    )
    top_players = _attach_profile_usernames(_top_players(5))
    hero_images = _pick_hero_images(24)

    about_stats = {
        "players": User.objects.count(),
        "events": Event.objects.count(),
        "points": UserToEvent.objects.aggregate(s=Sum("points"))["s"] or 0,
    }

    return render(request, "home.html", {
        "upcoming_events": upcoming_events,
        "top_players": top_players,
        "hero_images": hero_images,
        "about_stats": about_stats,
    })


def leaderboard_view(request):
    leaderboard_list_t = cache.get(CACHE_KEY)
    leaderboard_list_m = cache.get(CACHE_KEY_MONTH)

    if leaderboard_list_t is None:
        last_update_obj = LastUpdate.objects.all().first()
        if last_update_obj is None:
            last_update_obj = LastUpdate.objects.create(
                last_update=datetime.fromtimestamp(0, tz=dt_timezone.utc),
                last_complete_update=None,
            )

        now = timezone.now()
        run_all = (
            now.hour < last_update_obj.last_update.hour
            or last_update_obj.last_complete_update is None
        )

        if now - last_update_obj.last_update > timedelta(minutes=MINUTES):
            for conn in connections.all():
                conn.close()
            p = multiprocessing.Process(target=main, args=(run_all,))
            p.start()
            last_update_obj.last_update = now
            if run_all:
                last_update_obj.last_complete_update = now
            last_update_obj.save()
            p.join()

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


def events_view(request):
    events = list(Event.objects.all())
    today = timezone.now().date()
    for event in events:
        event.is_past = event.date.date() < today if event.date else False
    events.sort(key=lambda e: e.date, reverse=True)

    city_counts = {}
    for e in events:
        if e.place:
            city_counts[e.place] = city_counts.get(e.place, 0) + 1
    cities = [{"name": name, "count": city_counts[name]} for name in sorted(city_counts)]

    return render(request, "events.html", {
        "events": events,
        "cities": cities,
    })


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

    images = [
        request.build_absolute_uri(img.image.url)
        for img in ImageToEvent.objects.filter(event_id=event)
        if img.image
    ]

    rsvp_count = EventRSVP.objects.filter(event=event).count()

    return render(request, "event_detail.html", {
        "event": event,
        "is_future": is_future,
        "has_rsvp": has_rsvp,
        "existing_feedback": existing_feedback,
        "images": images,
        "images_json": json.dumps(images),
        "rsvp_count": rsvp_count,
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
        EventRSVP.objects.create(auth_user=request.user, event=event)
        messages.success(request, f"Přihlášeno na akci {event.name}.")
    return redirect("event_detail", slug=slug)


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
    messages.success(request, "Díky za zpětnou vazbu!")
    return redirect("event_detail", slug=slug)
