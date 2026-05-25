from datetime import date, datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from leaderboard.models import Event, Season, User as LeaderboardUser, UserToEvent


class SeasonLeaderboardApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-leaderboard")
        self.season = Season.objects.create(
            name="2025/26", start_date=date(2025, 9, 1), end_date=date(2026, 6, 30),
            is_active=True,
        )
        self.alice = LeaderboardUser.objects.create(number=1, name="Alice")
        self.bob = LeaderboardUser.objects.create(number=2, name="Bob")
        self.in_event = Event.objects.create(
            sheet_id="in", sheet_list_id="x", name="In Season", place="Brno", points=100,
            date=timezone.make_aware(datetime(2025, 10, 1, 12, 0)),
        )
        self.out_event = Event.objects.create(
            sheet_id="out", sheet_list_id="x", name="Pre Season", place="Brno", points=100,
            date=timezone.make_aware(datetime(2025, 1, 1, 12, 0)),
        )
        UserToEvent.objects.create(user=self.alice, event=self.in_event, points=100)
        UserToEvent.objects.create(user=self.alice, event=self.out_event, points=100)
        UserToEvent.objects.create(user=self.bob, event=self.in_event, points=50)

    def test_season_counts_only_in_window_points(self):
        resp = self.client.get(self.url, {"season_id": self.season.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["season"]["id"], self.season.id)
        by_name = {e["name"]: e for e in data["entries"]}
        self.assertEqual(by_name["Alice"]["total_points"], 100)  # pre-season 100 excluded
        self.assertEqual(by_name["Bob"]["total_points"], 50)

    def test_default_uses_active_season(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["season"]["id"], self.season.id)

    def test_all_returns_alltime_points(self):
        resp = self.client.get(self.url, {"season_id": "all"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["season"])
        by_name = {e["name"]: e for e in data["entries"]}
        self.assertEqual(by_name["Alice"]["total_points"], 200)

    def test_unknown_season_id_returns_404(self):
        resp = self.client.get(self.url, {"season_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_season_param_returns_400(self):
        resp = self.client.get(self.url, {"season_id": "garbage"})
        self.assertEqual(resp.status_code, 400)

    def test_limit_caps_entries(self):
        resp = self.client.get(self.url, {"season_id": "all", "limit": 1})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["entries"]), 1)


class SeasonsListApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-seasons")
        Season.objects.create(name="2024/25", start_date=date(2024, 9, 1),
                              end_date=date(2025, 6, 30), is_active=False)
        Season.objects.create(name="2025/26", start_date=date(2025, 9, 1),
                              end_date=date(2026, 6, 30), is_active=True)

    def test_lists_all_seasons_with_shape(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        seasons = resp.json()["seasons"]
        self.assertEqual(len(seasons), 2)
        for s in seasons:
            for key in ("id", "name", "start", "end", "is_active"):
                self.assertIn(key, s)
