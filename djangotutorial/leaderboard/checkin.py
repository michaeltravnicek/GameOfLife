"""Single source of truth for event check-in.

The geo-gated "I'm here, give me points" flow runs through `validate_and_record_checkin`.
Tests target this function directly; the API view is a thin shim over it.
"""

from dataclasses import dataclass
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

from .cache_config import USER_TO_EVENT_DEPENDENT_CACHE_KEYS


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    R = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return R * 2 * asin(sqrt(a))


@dataclass
class CheckinResult:
    """Outcome of a check-in attempt.

    `ok=True` means points were already awarded OR are now newly awarded.
    `created` distinguishes the two (False = user had already checked in).
    """
    ok: bool
    status: int = 200
    error: Optional[str] = None
    distance_m: Optional[int] = None
    created: bool = False
    points: int = 0


def validate_and_record_checkin(event, auth_user, latitude, longitude) -> CheckinResult:
    """Validate the time window + distance, then award points (idempotent).

    Used by the API endpoint. The function knows nothing about HTTP — it just
    returns a CheckinResult that the caller maps to a response.
    """
    if event.latitude is None or event.longitude is None:
        return CheckinResult(ok=False, status=400, error="Tato akce nemá aktivní check-in.")

    now = timezone.now()
    window_open = event.date - timedelta(minutes=30)
    if not (window_open <= now <= event.checkin_window_end):
        return CheckinResult(ok=False, status=400, error="Check-in je mimo časové okno akce.")

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return CheckinResult(ok=False, status=400, error="Neplatné souřadnice.")

    distance = haversine_distance_m(lat, lon, event.latitude, event.longitude)
    if distance > event.checkin_radius:
        return CheckinResult(
            ok=False,
            status=400,
            error=(
                f"Jsi příliš daleko ({distance / 1000:.1f} km). "
                f"Check-in vyžaduje být do {event.checkin_radius} m."
            ),
            distance_m=round(distance),
        )

    # Late import — `accounts.models` depends on this app's models, so a
    # module-level import would create a circular load order.
    from accounts.models import Profile
    from .models import UserToEvent

    profile = (
        Profile.objects
        .filter(user=auth_user)
        .select_related("leaderboard_user")
        .first()
    )
    lb_user = profile.leaderboard_user if profile else None
    if lb_user is None:
        return CheckinResult(
            ok=False,
            status=400,
            error="Tvůj účet není propojen s leaderboardem.",
        )

    _, created = UserToEvent.objects.get_or_create(
        user=lb_user, event=event, defaults={"points": event.points},
    )
    if created:
        for key in USER_TO_EVENT_DEPENDENT_CACHE_KEYS:
            cache.delete(key)

    return CheckinResult(
        ok=True,
        status=200,
        created=created,
        points=event.points if created else 0,
        distance_m=round(distance),
    )
