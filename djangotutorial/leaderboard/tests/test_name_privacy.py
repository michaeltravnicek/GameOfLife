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
from leaderboard.privacy import display_name, public_handle, short_name


class PublicHandleTests(TestCase):
    """A username is only publishable when it's a chosen handle, not an e-mail."""

    def test_plain_handle_passes_through(self):
        self.assertEqual(public_handle("honza"), "honza")

    def test_email_shaped_username_is_withheld(self):
        # allauth / Google logins default the username to the e-mail address.
        self.assertIsNone(public_handle("honza@example.com"))
        self.assertIsNone(public_handle("a.b+tag@seznam.cz"))

    def test_empty_is_withheld(self):
        self.assertIsNone(public_handle(""))
        self.assertIsNone(public_handle(None))


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
        self.stranger = LeaderboardUser.objects.create(name="Neznámý Hráč")
        UserToEvent.objects.create(user=self.stranger, event=self.event, points=10)

        # Registered and consented.
        self.consented = LeaderboardUser.objects.create(name="Souhlas Dal")
        auth = get_user_model().objects.create_user(username="souhlasil", password="x")
        Profile.objects.create(
            user=auth, leaderboard_user=self.consented,
            gdpr_consent_at=timezone.now(),
            gdpr_consent_version=settings.PRIVACY_POLICY_VERSION,
        )
        UserToEvent.objects.create(user=self.consented, event=self.event, points=20)

        # Registered before the policy existed — no consent on record.
        self.no_consent = LeaderboardUser.objects.create(name="Stary Ucet")
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

    def test_no_player_email_is_ever_exposed(self):
        # Phone numbers are gone from the model (migration 0026); the e-mail the
        # form collects took over as the player's identity, so it inherits the
        # rule the number had — it exists to join rows, never to be published.
        for lb_user in (self.stranger, self.consented, self.no_consent):
            lb_user.email = f"{lb_user.id}@example.com"
            lb_user.save(update_fields=["email"])
        body = self.client.get(reverse("api-leaderboard")).content.decode()
        for lb_user in (self.stranger, self.consented, self.no_consent):
            self.assertNotIn(lb_user.email, body)


class EmailUsernameNotLeakedTests(TestCase):
    """A social-login account's username IS the person's e-mail. It must never
    surface as `profile_username` on any public endpoint — that would hand out a
    contactable address and slip past the name-consent rules entirely."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        today = timezone.now().date()
        Season.objects.create(
            name="Aktuální", start_date=today.replace(month=1, day=1),
            end_date=today.replace(month=12, day=31), is_active=True,
        )
        self.event = Event.objects.create(
            sheet_id="e", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=timezone.now(),
        )
        self.player = LeaderboardUser.objects.create(name="Anna Culka")
        self.email = "anna.culka@icloud.com"
        auth = get_user_model().objects.create_user(username=self.email, password="x")
        Profile.objects.create(user=auth, leaderboard_user=self.player)
        UserToEvent.objects.create(user=self.player, event=self.event, points=10)

    def test_leaderboard_withholds_email_username(self):
        resp = self.client.get(reverse("api-leaderboard"))
        self.assertNotIn(self.email, resp.content.decode())
        entry = next(e for e in resp.json()["entries"] if e["id"] == self.player.id)
        self.assertIsNone(entry["profile_username"])

    def test_player_detail_withholds_email_username(self):
        resp = self.client.get(reverse("api-player", kwargs={"user_id": self.player.id}))
        self.assertNotIn(self.email, resp.content.decode())
        self.assertIsNone(resp.json()["profile_username"])
