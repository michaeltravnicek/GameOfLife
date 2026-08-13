"""Everything that changes the leaderboard must evict it.

The board is cached for five minutes under `leaderboard_season:<id>`, and the
cached entries carry rendered display data — the player's name as shown, their
handle, their avatar — not just points. So the cache goes stale on more edits
than "someone got points", and each route below was found stale in an audit.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.services import update_profile
from leaderboard.cache_config import (
    CACHE_KEY_LEADERBOARD_SEASON_PREFIX,
    invalidate_points_dependent_caches,
    season_leaderboard_key,
    suspend_points_cache_invalidation,
)
from leaderboard.models import Event, Season, User as LeaderboardUser, UserToEvent

AuthUser = get_user_model()


class LeaderboardCacheInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.lb = LeaderboardUser.objects.create(name="Stará Jména")
        self.account = AuthUser.objects.create_user("stary_handle", "s@x.cz", "pw12345!")
        Profile.objects.create(user=self.account, leaderboard_user=self.lb)
        self.event = Event.objects.create(
            name="Akce", points=10, date=timezone.now() - timedelta(days=2))
        UserToEvent.objects.create(user=self.lb, event=self.event, points=10)

    def board(self):
        """Fetch the all-time board through the API, which is what caches it."""
        url = reverse("api-leaderboard") + "?season_id=all"
        return self.client.get(url).json()["entries"]

    def test_attendance_added_outside_the_known_call_sites_shows_up(self):
        """A row created straight on the model — i.e. the Django admin, which is
        the documented way to top up somebody whose phone failed at check-in."""
        self.assertEqual(self.board()[0]["total_points"], 10)
        second = Event.objects.create(
            name="Druhá", points=25, date=timezone.now() - timedelta(days=1))
        UserToEvent.objects.create(user=self.lb, event=second, points=25)
        self.assertEqual(self.board()[0]["total_points"], 35)

    def test_removing_attendance_shows_up(self):
        # The all-time board keeps zero-point players, so the row stays — what
        # must not stay is the score it was cached with.
        self.assertEqual(self.board()[0]["total_points"], 10)
        UserToEvent.objects.get(user=self.lb, event=self.event).delete()
        self.assertEqual(self.board()[0]["total_points"], 0)

    def test_renaming_the_player_updates_the_cached_name(self):
        """The board stores the *rendered* name ("Jan N."), not a live lookup."""
        self.assertEqual(self.board()[0]["name"], "Stará J.")
        self.lb.name = "Nové Jméno"
        self.lb.save(update_fields=["name"])
        self.assertEqual(self.board()[0]["name"], "Nové J.")

    def test_changing_the_handle_updates_the_cached_link(self):
        self.assertEqual(self.board()[0]["profile_username"], "stary_handle")
        update_profile(self.account, {"username": "novy_handle"}, {})
        self.assertEqual(self.board()[0]["profile_username"], "novy_handle")

    def test_saving_a_player_without_renaming_leaves_the_cache_alone(self):
        """The sync saves players constantly; only a real rename should evict."""
        self.board()
        key = season_leaderboard_key("all")
        self.lb.email = "kdo@example.com"
        self.lb.save(update_fields=["email"])
        self.assertIsNotNone(cache.get(key))


class SeasonKeyEvictionTests(TestCase):
    """The eviction must not depend on django-redis being configured."""

    def setUp(self):
        cache.clear()
        self.season = Season.objects.create(
            name="2026", start_date="2026-01-01", end_date="2026-12-31", is_active=True)

    def test_named_season_keys_are_evicted_without_delete_pattern(self):
        # LocMemCache (the test backend) has no delete_pattern, exactly like a
        # deployment with REDIS_URL unset.
        self.assertFalse(hasattr(cache, "delete_pattern"))
        keys = [season_leaderboard_key("all"), season_leaderboard_key(self.season.pk)]
        for key in keys:
            cache.set(key, "SENTINEL", 60)

        invalidate_points_dependent_caches()

        for key in keys:
            self.assertIsNone(cache.get(key), f"{key} survived eviction")

    def test_the_key_prefix_matches_what_gets_evicted(self):
        """Guards a rename of one half of the pair without the other."""
        self.assertTrue(
            season_leaderboard_key("all").startswith(CACHE_KEY_LEADERBOARD_SEASON_PREFIX))


class SuspendInvalidationTests(TestCase):
    """Bulk imports batch their evictions instead of one per row."""

    def setUp(self):
        cache.clear()
        self.key = season_leaderboard_key("all")

    def test_suspended_writes_do_not_evict(self):
        cache.set(self.key, "SENTINEL", 60)
        with suspend_points_cache_invalidation():
            invalidate_points_dependent_caches()
            self.assertEqual(cache.get(self.key), "SENTINEL")

    def test_eviction_resumes_after_the_block(self):
        cache.set(self.key, "SENTINEL", 60)
        with suspend_points_cache_invalidation():
            pass
        invalidate_points_dependent_caches()
        self.assertIsNone(cache.get(self.key))

    def test_nesting_does_not_resume_early(self):
        cache.set(self.key, "SENTINEL", 60)
        with suspend_points_cache_invalidation():
            with suspend_points_cache_invalidation():
                pass
            invalidate_points_dependent_caches()
            self.assertEqual(cache.get(self.key), "SENTINEL")

    def test_an_exception_still_lifts_the_suspension(self):
        try:
            with suspend_points_cache_invalidation():
                raise RuntimeError("sync blew up")
        except RuntimeError:
            pass
        cache.set(self.key, "SENTINEL", 60)
        invalidate_points_dependent_caches()
        self.assertIsNone(cache.get(self.key))
