import multiprocessing
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import User, UserToEvent, Event, ImageToEvent, LastUpdate
from django.db.models import Count, Sum
from django.utils import timezone
from .tasks import main
from datetime import datetime, timedelta, timezone as dt_timezone
from django.db.models import F
from django.utils import timezone
from django.conf import settings
from django.db import connections
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Coalesce


def home_view(request):
    print(settings.MEDIA_ROOT)
    print(settings.MEDIA_URL)
    return render(request, "welcome.html", {})

from django.core.cache import cache
from datetime import timedelta

MINUTES = 5
CACHE_KEY = "leaderboard_data"
CACHE_TTL = MINUTES * 60
CACHE_KEY_MONTH = "leaderboard_data_month"

# Konfigurace časového rámce pro "This month" tab:
# None = od začátku aktuálního měsíce, int = posledních N dní (např. 30)
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
            events_count=Count(
                "usertoevent", distinct=True
            ),
            total_points=Sum(
                "usertoevent__points",
            )
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
                distinct=True
            ),
            total_points=Coalesce(
                Sum(
                    "usertoevent__points",
                    filter=Q(usertoevent__event__date__gte=first_day)
                ),
                0
            )
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


def leaderboard_view(request):
    leaderboard_list_t = cache.get(CACHE_KEY)
    leaderboard_list_m = cache.get(CACHE_KEY_MONTH)

    if leaderboard_list_t is None:
        print("Cache miss")
        last_update_obj = LastUpdate.objects.all().first()
        if last_update_obj is None:
            last_update_obj = LastUpdate.objects.create(
                last_update=datetime.fromtimestamp(0, tz=dt_timezone.utc),
                last_complete_update=None
            )

        now = timezone.now()
        run_all = now.hour < last_update_obj.last_update.hour or last_update_obj.last_complete_update is None

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
    else:
        print("Cache hit")

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

    from_date_ts = request.GET.get('from_date')
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
        "user_points"
    ).order_by("event__date")

    data = {
        "user_name": user.name,
        "actions": list(actions)
    }
    return JsonResponse(data)


def events_view(request):
    events = Event.objects.all()
    today = timezone.now().date()

    for event in events:
        if hasattr(event, "date") and event.date: 
            event.is_past = event.date.date() < today
        else:
            event.is_past = False

    events = sorted(events, key=lambda e: e.date, reverse=True)
    return render(request, "events.html", {"events": events})


def events_image_views(request, event_id: str):
    event = get_object_or_404(Event, id=event_id)

    images = [
        request.build_absolute_uri(img.image.url)
        for img in ImageToEvent.objects.filter(event_id=event)
        if img.image
    ]

    return JsonResponse({
        "event_id": event_id,
        "images": images
    })