from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, User as LeaderboardUser, UserToEvent


class PlayerDetailApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()
        self.event1 = Event.objects.create(
            sheet_id="p1", sheet_list_id="x", name="Akce 1", place="Brno", points=30,
            date=now - timedelta(days=2),
        )
        self.event2 = Event.objects.create(
            sheet_id="p2", sheet_list_id="x", name="Akce 2", place="Praha", points=20,
            date=now - timedelta(days=1),
        )
        # Unregistered player — straight from the Google Sheets sync, no account.
        self.player = LeaderboardUser.objects.create(number=700000042, name="Sheet Only")
        UserToEvent.objects.create(user=self.player, event=self.event1, points=30)
        UserToEvent.objects.create(user=self.player, event=self.event2, points=20)

    def test_unregistered_player_lists_attended_events(self):
        url = reverse("api-player", kwargs={"user_id": self.player.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Initials, not the full name: this player was synced from Sheets and
        # never registered, so nothing was consented to (leaderboard/privacy.py).
        self.assertEqual(data["name"], "S. O.")
        self.assertEqual(data["total_points"], 50)
        self.assertEqual(data["events_count"], 2)
        self.assertIsNone(data["profile_username"])  # not registered
        # Newest first.
        self.assertEqual([e["name"] for e in data["events"]], ["Akce 2", "Akce 1"])

    def test_registered_player_exposes_username(self):
        auth = get_user_model().objects.create_user(username="linked", password="x")
        Profile.objects.create(user=auth, leaderboard_user=self.player)
        resp = self.client.get(reverse("api-player", kwargs={"user_id": self.player.id}))
        self.assertEqual(resp.json()["profile_username"], "linked")

    def test_unknown_player_returns_404(self):
        resp = self.client.get(reverse("api-player", kwargs={"user_id": 999999}))
        self.assertEqual(resp.status_code, 404)
