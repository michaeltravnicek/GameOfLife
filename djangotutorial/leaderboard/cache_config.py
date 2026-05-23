"""Single source of truth for cache keys and TTLs.

Anything that reads or writes the Django cache must import from here so:
  - There's one place to audit cache lifetimes.
  - Model `save()` invalidators can't fall out of sync with a renamed key.
  - Tests can clear specific keys without guessing strings.
"""

# ── Leaderboard rankings ───────────────────────────────────────────────
CACHE_KEY_LEADERBOARD_TOTAL = "leaderboard_data"
CACHE_KEY_LEADERBOARD_MONTH = "leaderboard_data_month"
CACHE_TTL_LEADERBOARD = 5 * 60  # 5 min — points change with new check-ins

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

# ── Backward-compat aliases (legacy names used across the codebase) ───
# Keeping these stops a giant rename churn while old code is around.
CACHE_KEY = CACHE_KEY_LEADERBOARD_TOTAL
CACHE_KEY_MONTH = CACHE_KEY_LEADERBOARD_MONTH
CACHE_TTL = CACHE_TTL_LEADERBOARD


# Keys that must be dropped whenever an Event is created/edited/deleted.
# (Used by Event.save() — keep this list in sync with what each endpoint reads.)
EVENT_DEPENDENT_CACHE_KEYS = (
    CACHE_KEY_HERO_IMAGES,
    CACHE_KEY_HOME_CONTEXT,
    CACHE_KEY_HOME_STATS,
    CACHE_KEY_EVENTS_LIST,
    CACHE_KEY_EVENTS_CITIES,
)

# Keys that must be dropped whenever a UserToEvent (= scored attendance) changes.
# Currently only the leaderboards and the home stats depend on points totals.
USER_TO_EVENT_DEPENDENT_CACHE_KEYS = (
    CACHE_KEY_LEADERBOARD_TOTAL,
    CACHE_KEY_LEADERBOARD_MONTH,
    CACHE_KEY_HOME_CONTEXT,
    CACHE_KEY_HOME_STATS,
)
