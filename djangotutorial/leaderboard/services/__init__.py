"""Business logic for the leaderboard app.

Pure data/query helpers grouped by concern; kept free of HTTP so the API views
stay thin. Re-exported here so callers can `from leaderboard.services import X`
regardless of which submodule X lives in.
"""
from .attendance import (
    attendee_payload,
    attendees_for_event,
    remove_attendance,
    rsvps_for_event,
    set_attendance,
)
from .catalog import (
    categories_cached, cities_cached, profile_questions_cached, season_dict, seasons_cached,
)
from .events import EVENTS_LIST_FIELDS, add_event_images, list_events
from .feedback import admin_feedback_list
from .gallery import create_user_photo, gallery_page
from .home import active_checkin_events, home_stats, pick_hero_events
from .leaderboard import (
    attach_profile_usernames,
    cached_leaderboard_entries,
    create_leaderboard,
    entries_payload,
    leaderboard_for_season,
    leaderboard_total,
    player_payload,
    resolve_season,
    resolve_season_filter,
    season_payload,
    season_rank,
    top_players,
)

__all__ = [
    "attendee_payload", "attendees_for_event", "remove_attendance",
    "rsvps_for_event", "set_attendance",
    "categories_cached", "cities_cached", "profile_questions_cached",
    "season_dict", "seasons_cached",
    "EVENTS_LIST_FIELDS", "add_event_images", "list_events",
    "admin_feedback_list",
    "create_user_photo", "gallery_page",
    "active_checkin_events", "home_stats", "pick_hero_events",
    "attach_profile_usernames", "cached_leaderboard_entries", "create_leaderboard",
    "entries_payload", "leaderboard_for_season", "leaderboard_total", "player_payload",
    "resolve_season", "resolve_season_filter", "season_payload", "season_rank", "top_players",
]
