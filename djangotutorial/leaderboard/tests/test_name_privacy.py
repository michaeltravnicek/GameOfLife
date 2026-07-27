"""Public surfaces must not publish the names of people who never consented.

Points are synced from Google Sheets for every attendee, so most leaderboard
entries belong to people with no account and no agreement to be published.
"""
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, Season, User as LeaderboardUser, UserToEvent
from leaderboard.privacy import display_name, short_name


class ShortNameTests(TestCase):
    def test_two_part_name(self):
        self.assertEqual(short_name("Jan Novák"), "Jan N.")

    def test_single_name_is_kept(self):
        self.assertEqual(short_name("Madonna"), "Madonna")

    def test_extra_whitespace_is_ignored(self):
        self.assertEqual(short_name("  Jan   Novák  "), "Jan N.")

    def test_empty_name_falls_back_to_label(self):
        self.assertEqual(short_name(""), "Hráč")
        self.assertEqual(short_name(None), "Hráč")

    def test_middle_names_are_dropped_not_abbreviated(self):
        self.assertEqual(short_name("Jan Evangelista Purkyně Novák"), "Jan N.")

    def test_lowercase_surname_initial_is_upper_cased(self):
        self.assertEqual(short_name("jan novák"), "jan N.")

    def test_display_name_respects_consent(self):
        self.assertEqual(display_name("Jan Novák", consented=True), "Jan Novák")
        self.assertEqual(display_name("Jan Novák", consented=False), "Jan N.")


class LeaderboardNamePrivacyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # Window must contain the event below, or the leaderboard is empty and
        # the assertions would pass vacuously.
        today = timezone.now().date()
        self.season = Season.objects.create(
            name="Aktuální", start_date=today.replace(month=1, day=1),
            end_date=today.replace(month=12, day=31), is_active=True,
        )
        self.event = Event.objects.create(
            sheet_id="p", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=timezone.now(),
        )
        # Synced from Sheets, never registered — the common case.
        self.stranger = LeaderboardUser.objects.create(number=700000201, name="Neznámý Hráč")
        UserToEvent.objects.create(user=self.stranger, event=self.event, points=10)

        # Registered and consented.
        self.consented = LeaderboardUser.objects.create(number=700000202, name="Souhlas Dal")
        auth = get_user_model().objects.create_user(username="souhlasil", password="x")
        Profile.objects.create(
            user=auth, leaderboard_user=self.consented,
            gdpr_consent_at=timezone.now(),
            gdpr_consent_version=settings.PRIVACY_POLICY_VERSION,
        )
        UserToEvent.objects.create(user=self.consented, event=self.event, points=20)

        # Registered before the policy existed — no consent on record.
        self.no_consent = LeaderboardUser.objects.create(number=700000203, name="Stary Ucet")
        auth2 = get_user_model().objects.create_user(username="stary", password="x")
        Profile.objects.create(user=auth2, leaderboard_user=self.no_consent)
        UserToEvent.objects.create(user=self.no_consent, event=self.event, points=5)

    def _names(self):
        resp = self.client.get(reverse("api-leaderboard"))
        self.assertEqual(resp.status_code, 200)
        return {e["name"] for e in resp.json()["entries"]}

    def test_unregistered_player_shows_short_name(self):
        names = self._names()
        self.assertIn("Neznámý H.", names)
        self.assertNotIn("Neznámý Hráč", names)

    def test_consented_player_shows_full_name(self):
        self.assertIn("Souhlas Dal", self._names())

    def test_registered_without_consent_shows_short_name(self):
        # An account alone is not agreement — the consent record is what counts.
        names = self._names()
        self.assertIn("Stary U.", names)
        self.assertNotIn("Stary Ucet", names)

    def test_player_detail_hides_unconsented_name(self):
        url = reverse("api-player", kwargs={"user_id": self.stranger.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Neznámý H.")

    def test_player_detail_shows_consented_name(self):
        url = reverse("api-player", kwargs={"user_id": self.consented.id})
        self.assertEqual(self.client.get(url).json()["name"], "Souhlas Dal")

    def test_no_phone_number_is_ever_exposed(self):
        body = self.client.get(reverse("api-leaderboard")).content.decode()
        for lb_user in (self.stranger, self.consented, self.no_consent):
            self.assertNotIn(str(lb_user.number), body)
