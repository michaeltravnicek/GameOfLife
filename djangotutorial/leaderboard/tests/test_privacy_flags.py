"""Privacy flags must be enforced on every endpoint that can reach a profile.

These flags were stored and echoed back for a long time without anything acting
on them, so the point of this suite is less "does the happy path work" and more
"is the flag bypassable by asking a different way". One person's data is
reachable through four URLs, and a flag honoured by three of them is not
honoured at all.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Category, Event, Season, User as LeaderboardUser, UserToEvent


class PrivacyFlagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        UserModel = get_user_model()
        cls.owner = UserModel.objects.create_user(
            username="hidden_hana", password="pw-12345", first_name="Hana",
        )
        cls.other = UserModel.objects.create_user(username="nosy_nikola", password="pw-12345")
        cls.admin_user = UserModel.objects.create_user(username="admin_ada", password="pw-12345")
        Profile.objects.update_or_create(
            user=cls.admin_user, defaults={"role": Profile.ROLE_ADMIN},
        )

        cls.lb_user = LeaderboardUser.objects.create(name="Hana Hidden")
        cls.profile, _ = Profile.objects.update_or_create(
            user=cls.owner, defaults={"leaderboard_user": cls.lb_user},
        )

        category = Category.objects.create(name="Běh")
        cls.event = Event.objects.create(
            sheet_id="pf1", sheet_list_id="x", name="Ranní běh", place="Praha",
            points=10, date=timezone.now() - timedelta(days=7), category=category,
        )
        UserToEvent.objects.create(user=cls.lb_user, event=cls.event, points=10)
        cls.season = Season.objects.create(
            name="2026", start_date="2026-01-01", end_date="2026-12-31", is_active=True,
        )

    def setUp(self):
        self.client = APIClient()
        # The leaderboard endpoint is cached, and the per-season keys are evicted
        # by pattern — which LocMemCache (the test backend) cannot do, so a board
        # cached by an earlier test class would survive into this one and the
        # assertions here would be reading someone else's data.
        cache.clear()

    # --- helpers ---------------------------------------------------------

    def set_flags(self, **flags):
        for field, value in flags.items():
            setattr(self.profile, field, value)
        self.profile.save()

    def profile_url(self):
        return reverse("api-profile", args=[self.owner.username])

    def player_url(self):
        return reverse("api-player", args=[self.lb_user.id])

    # --- members_only ----------------------------------------------------

    def test_members_only_hides_profile_from_anonymous(self):
        self.set_flags(members_only=True)
        self.assertEqual(self.client.get(self.profile_url()).status_code, 404)

    def test_members_only_404s_rather_than_403s(self):
        # A 403 would confirm the account exists, which is the thing being hidden.
        self.set_flags(members_only=True)
        resp = self.client.get(self.profile_url())
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(resp.status_code, 403)

    def test_members_only_allows_any_signed_in_visitor(self):
        self.set_flags(members_only=True)
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(self.profile_url()).status_code, 200)

    def test_members_only_allows_the_owner(self):
        self.set_flags(members_only=True)
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.get(self.profile_url()).status_code, 200)

    def test_members_only_blocks_the_season_sub_resource_too(self):
        self.set_flags(members_only=True)
        url = reverse("api-profile-season", args=[self.owner.username, self.season.id])
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- hide_pts --------------------------------------------------------

    def test_hide_pts_omits_totals_rather_than_zeroing_them(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.profile_url()).json()
        self.assertNotIn("total_points", data)
        self.assertNotIn("rank", data)
        self.assertIn("points", data["hidden"])

    def test_hide_pts_does_not_hide_the_event_list(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.profile_url()).json()
        self.assertIn("past_events", data)

    def test_owner_still_sees_own_points(self):
        self.set_flags(hide_pts=True)
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(self.profile_url()).json()
        self.assertEqual(data["total_points"], 10)
        self.assertEqual(data["hidden"], [])

    def test_admin_still_sees_hidden_points(self):
        self.set_flags(hide_pts=True)
        self.client.force_authenticate(user=self.admin_user)
        data = self.client.get(self.profile_url()).json()
        self.assertEqual(data["total_points"], 10)

    # --- hide_pts must not be reconstructable ----------------------------
    # Omitting `total_points` is not enough on its own. The same number is
    # recoverable by adding up the per-event points, and it is stated outright by
    # the season payloads and by the player's row on the leaderboard. Each test
    # below closes one of those routes.

    def test_hide_pts_strips_per_event_points(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.profile_url()).json()
        for event in data["past_events"]:
            self.assertNotIn("points", event)

    def test_hide_pts_strips_season_totals_from_the_summaries(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.profile_url()).json()
        for season in data["seasons"]:
            self.assertNotIn("season_pts", season)
            self.assertNotIn("rank", season)

    def test_hide_pts_strips_the_season_sub_resource(self):
        """The endpoint states season_pts outright — the shortest route of all."""
        self.set_flags(hide_pts=True)
        url = reverse("api-profile-season", args=[self.owner.username, self.season.id])
        data = self.client.get(url).json()
        self.assertNotIn("season_pts", data)
        self.assertNotIn("rank", data)
        for event in data["events"]:
            self.assertNotIn("pts", event)

    def test_hide_pts_strips_the_player_season_sub_resource(self):
        self.set_flags(hide_pts=True)
        url = reverse("api-player-season", args=[self.lb_user.id, self.season.id])
        data = self.client.get(url).json()
        self.assertNotIn("season_pts", data)
        for event in data["events"]:
            self.assertNotIn("pts", event)

    def test_hide_pts_strips_per_event_points_on_the_player_endpoint(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.player_url()).json()
        for event in data["events"]:
            self.assertNotIn("points", event)

    def test_the_owner_can_still_reconstruct_their_own(self):
        """Everything above is withheld from visitors, never from the person."""
        self.set_flags(hide_pts=True)
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(self.profile_url()).json()
        self.assertEqual([e["points"] for e in data["past_events"]], [10])

    # --- hide_events -----------------------------------------------------

    def test_hide_events_omits_event_sections(self):
        self.set_flags(hide_events=True)
        data = self.client.get(self.profile_url()).json()
        for key in ("past_events", "upcoming_rsvps", "seasons"):
            self.assertNotIn(key, data)
        self.assertIn("events", data["hidden"])

    def test_hide_events_blocks_the_profile_season_endpoint(self):
        # Otherwise the flag is cosmetic: the list is gone from the main payload
        # but still served one request away.
        self.set_flags(hide_events=True)
        url = reverse("api-profile-season", args=[self.owner.username, self.season.id])
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- the parallel /players/<id>/ surface -----------------------------

    def test_player_endpoint_honours_hide_pts(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(self.player_url()).json()
        self.assertNotIn("total_points", data)
        self.assertIn("points", data["hidden"])

    def test_player_endpoint_honours_hide_events(self):
        self.set_flags(hide_events=True)
        data = self.client.get(self.player_url()).json()
        self.assertNotIn("events", data)

    def test_player_season_endpoint_honours_hide_events(self):
        self.set_flags(hide_events=True)
        url = reverse("api-player-season", args=[self.lb_user.id, self.season.id])
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- privacy block is the owner's business only ----------------------

    def test_privacy_block_not_exposed_to_visitors(self):
        self.set_flags(members_only=False, hide_pts=True)
        self.client.force_authenticate(user=self.other)
        self.assertNotIn("privacy", self.client.get(self.profile_url()).json())

    def test_privacy_block_returned_to_owner_for_the_edit_form(self):
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(self.profile_url()).json()
        self.assertIn("privacy", data)

    # --- hide_pts takes the player off the rankings -----------------------

    def test_hide_pts_removes_the_player_from_the_leaderboard(self):
        from leaderboard.services.leaderboard import leaderboard_total

        self.assertIn(self.lb_user, list(leaderboard_total()))
        self.set_flags(hide_pts=True)
        self.assertNotIn(self.lb_user, list(leaderboard_total()))

    def test_hide_pts_removes_the_player_from_the_home_top_players(self):
        from leaderboard.services.leaderboard import top_players

        self.set_flags(hide_pts=True)
        self.assertNotIn(self.lb_user, list(top_players()))

    def test_hide_pts_removes_the_player_from_the_season_board(self):
        from leaderboard.services.leaderboard import leaderboard_for_season

        self.set_flags(hide_pts=True)
        self.assertNotIn(
            self.lb_user, list(leaderboard_for_season(self.season)))

    def test_the_leaderboard_endpoint_does_not_list_them(self):
        self.set_flags(hide_pts=True)
        data = self.client.get(reverse("api-leaderboard")).json()
        self.assertNotIn(self.lb_user.id, [e["id"] for e in data["entries"]])

    def test_a_hidden_player_does_not_push_others_down_the_ranking(self):
        """Their rank must agree with the board they are missing from."""
        from leaderboard.services.leaderboard import season_rank

        rival = LeaderboardUser.objects.create(name="Rival Rivalový")
        UserToEvent.objects.create(user=rival, event=self.event, points=5)
        # Hana has 10 and sits above the rival's 5 → rival is 2nd.
        self.assertEqual(season_rank(self.season, 5), 2)
        self.set_flags(hide_pts=True)
        # With Hana off the board the rival is top, not runner-up to nobody.
        self.assertEqual(season_rank(self.season, 5), 1)

    def test_toggling_the_flag_evicts_the_cached_board(self):
        """Otherwise the switch looks broken until the TTL runs out."""
        from leaderboard.cache_config import CACHE_KEY_LEADERBOARD_TOTAL

        cache.set(CACHE_KEY_LEADERBOARD_TOTAL, "SENTINEL", 60)
        self.set_flags(hide_pts=True)
        self.assertIsNone(cache.get(CACHE_KEY_LEADERBOARD_TOTAL))

    def test_saving_a_profile_without_touching_the_flag_leaves_the_cache(self):
        from leaderboard.cache_config import CACHE_KEY_LEADERBOARD_TOTAL

        cache.set(CACHE_KEY_LEADERBOARD_TOTAL, "SENTINEL", 60)
        self.set_flags(bio="jen popis")
        self.assertEqual(cache.get(CACHE_KEY_LEADERBOARD_TOTAL), "SENTINEL")

    # --- default state ---------------------------------------------------

    def test_nothing_hidden_by_default(self):
        data = self.client.get(self.profile_url()).json()
        self.assertEqual(data["hidden"], [])
        self.assertEqual(data["total_points"], 10)
        self.assertIn("past_events", data)
