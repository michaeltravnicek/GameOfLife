"""Cached lookup lists: categories, cities, seasons."""
from django.core.cache import cache
from django.db.models import Count

from leaderboard.cache_config import (
    CACHE_KEY_CATEGORIES,
    CACHE_KEY_EVENTS_CITIES,
    CACHE_KEY_SEASONS,
    CACHE_TTL_CATEGORIES,
    CACHE_TTL_EVENTS_CITIES,
    CACHE_TTL_SEASONS,
)
from leaderboard.models import Category, Event, Season


def season_dict(season):
    """Serialize a Season to the shape used by the API."""
    return {
        "id": season.id,
        "name": season.name,
        "start": season.start_date,
        "end": season.end_date,
        "is_active": season.is_active,
    }


def categories_cached():
    """All categories as `[{id, name}]` (cached 1h)."""
    cached = cache.get(CACHE_KEY_CATEGORIES)
    if cached is not None:
        return cached
    result = list(Category.objects.values("id", "name"))
    cache.set(CACHE_KEY_CATEGORIES, result, CACHE_TTL_CATEGORIES)
    return result


def cities_cached():
    """Distinct event places + counts as `[{name, count}]` (cached 30 min)."""
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


def seasons_cached():
    """All seasons as `[{id, name, start, end, is_active}]` (cached 1h)."""
    cached = cache.get(CACHE_KEY_SEASONS)
    if cached is not None:
        return cached
    result = [season_dict(s) for s in Season.objects.all()]
    cache.set(CACHE_KEY_SEASONS, result, CACHE_TTL_SEASONS)
    return result
