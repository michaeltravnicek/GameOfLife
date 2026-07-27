"""Privacy flags must be enforced on every endpoint that can reach a profile.

These flags were stored and echoed back for a long time without anything acting
on them, so the point of this suite is less "does the happy path work" and more
"is the flag bypassable by asking a different way". One person's data is
reachable through four URLs, and a flag honoured by three of them is not
honoured at all.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
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

        cls.lb_user = LeaderboardUser.objects.create(number=700000501, name="Hana Hidden")
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

    # --- default state ---------------------------------------------------

    def test_nothing_hidden_by_default(self):
        data = self.client.get(self.profile_url()).json()
        self.assertEqual(data["hidden"], [])
        self.assertEqual(data["total_points"], 10)
        self.assertIn("past_events", data)
