"""Single source of truth for cache keys and TTLs.

Anything that reads or writes the Django cache must import from here so:
  - There's one place to audit cache lifetimes.
  - Model `save()` invalidators can't fall out of sync with a renamed key.
  - Tests can clear specific keys without guessing strings.
"""

# ── Leaderboard rankings ───────────────────────────────────────────────
CACHE_KEY_LEADERBOARD_TOTAL = "leaderboard_data"
CACHE_TTL_LEADERBOARD = 5 * 60  # 5 min — points change with new check-ins

# Per-season leaderboards are cached under a dynamic key (one per season id).
# Use the prefix to build keys and to evict the whole family with delete_pattern.
CACHE_KEY_LEADERBOARD_SEASON_PREFIX = "leaderboard_season"


def season_leaderboard_key(season_id):
    """Cache key for a single season's leaderboard (``"all"`` for all-time)."""
    return f"{CACHE_KEY_LEADERBOARD_SEASON_PREFIX}:{season_id}"

# ── Home (HTML legacy + API) ───────────────────────────────────────────
CACHE_KEY_HERO_IMAGES = "home_hero_images"
CACHE_TTL_HERO_IMAGES = 60 * 60  # 1 hour — hero photos rarely change

CACHE_KEY_HOME_CONTEXT = "home_context"
CACHE_TTL_HOME_CONTEXT = 5 * 60  # 5 min — stats/upcoming

# Used only by /api/home/ (separate cache from the HTML home_context).
CACHE_KEY_HOME_STATS = "api_home_stats"
CACHE_TTL_HOME_STATS = 30 * 60  # 30 min — counts barely move

# ── Events list (HTML legacy + API) ────────────────────────────────────
CACHE_KEY_EVENTS_LIST = "events_list"
CACHE_TTL_EVENTS_LIST = 5 * 60

# Cities filter for /api/events/. Changes only when an Event is added/edited.
CACHE_KEY_EVENTS_CITIES = "api_events_cities"
CACHE_TTL_EVENTS_CITIES = 30 * 60

# Categories list for /api/categories/. Changes only when a Category is added/renamed.
CACHE_KEY_CATEGORIES = "api_categories"
CACHE_TTL_CATEGORIES = 60 * 60  # 1 hour

# Seasons list for /api/seasons/. Changes only when a Season is added/edited.
CACHE_KEY_SEASONS = "api_seasons"
CACHE_TTL_SEASONS = 60 * 60  # 1 hour

# ── Short alias (legacy name still used across the codebase) ───────────
CACHE_KEY = CACHE_KEY_LEADERBOARD_TOTAL
CACHE_TTL = CACHE_TTL_LEADERBOARD


# Keys that must be dropped whenever an Event is created/edited/deleted.
# (Used by Event.save() — keep this list in sync with what each endpoint reads.)
EVENT_DEPENDENT_CACHE_KEYS = (
    CACHE_KEY_HERO_IMAGES,
    CACHE_KEY_HOME_CONTEXT,
    CACHE_KEY_HOME_STATS,
    CACHE_KEY_EVENTS_LIST,
    CACHE_KEY_EVENTS_CITIES,
    CACHE_KEY_CATEGORIES,
)

# Keys that must be dropped whenever a UserToEvent (= scored attendance) changes.
# The leaderboards (total + every season) and the home stats depend on points totals.
USER_TO_EVENT_DEPENDENT_CACHE_KEYS = (
    CACHE_KEY_LEADERBOARD_TOTAL,
    CACHE_KEY_HOME_STATS,
)


import logging

logger = logging.getLogger(__name__)


def _evict(keys=(), pattern=None):
    """Best-effort cache eviction. A cache outage must never break a DB write.

    `delete_pattern` is django-redis-specific, so it's skipped on backends that
    lack it (e.g. LocMemCache in tests). Any backend error is logged and swallowed.
    """
    from django.core.cache import cache

    try:
        for key in keys:
            cache.delete(key)
        if pattern:
            delete_pattern = getattr(cache, "delete_pattern", None)
            if delete_pattern is not None:
                delete_pattern(pattern)
    except Exception:  # noqa: BLE001 — cache is non-critical; never fail the caller
        logger.warning("Cache eviction failed (continuing).", exc_info=True)


def invalidate_event_caches():
    """Drop caches that depend on the Event table (called from Event.save())."""
    _evict(EVENT_DEPENDENT_CACHE_KEYS)


def invalidate_category_cache():
    """Drop the category list cache (called from Category.save()/delete()).

    The list is cached for an hour, which is fine until someone adds a category
    from the event form and expects to pick it in the next breath.
    """
    _evict((CACHE_KEY_CATEGORIES,))


def invalidate_hero_cache():
    """Drop the hero-carousel cache (called from ImageToEvent.save())."""
    _evict((CACHE_KEY_HERO_IMAGES,))


def invalidate_points_dependent_caches():
    """Evict everything that depends on points totals after attendance changes.

    Covers the static keys plus the dynamic per-season leaderboard family
    (`leaderboard_season:*`), which can't be listed individually.
    """
    _evict(USER_TO_EVENT_DEPENDENT_CACHE_KEYS,
           pattern=f"{CACHE_KEY_LEADERBOARD_SEASON_PREFIX}:*")
