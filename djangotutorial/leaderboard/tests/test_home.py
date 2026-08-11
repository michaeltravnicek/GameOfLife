from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, User as LeaderboardUser, UserToEvent

from .helpers import BRNO_LAT, BRNO_LON, make_profile_for


class CheckinEventsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-checkin-events")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="home_test", password="x")
        self.lb_user = make_profile_for(self.user)

        now = timezone.now()
        self.active = Event.objects.create(
            sheet_id="active", sheet_list_id="x",
            name="Active Live Event", place="Brno", points=50,
            date=now - timedelta(minutes=5),
            end_date=now + timedelta(hours=1),
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )

    def test_anonymous_user_sees_active_events(self):
        # Guests see active events; the frontend prompts login on check-in tap.
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        slugs = [e["slug"] for e in resp.json()["events"]]
        self.assertIn(self.active.slug, slugs)

    def test_authenticated_user_sees_active_event(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        slugs = [e["slug"] for e in resp.json()["events"]]
        self.assertIn(self.active.slug, slugs)

    def test_user_already_checked_in_does_not_see_event(self):
        UserToEvent.objects.create(user=self.lb_user, event=self.active, points=50)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["events"], [])

    def test_event_without_coords_excluded(self):
        self.active.latitude = None
        self.active.longitude = None
        self.active.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["events"], [])

    def test_user_without_profile_link_sees_active_events(self):
        # Same as guests: unlinked accounts see events; check-in itself is gated.
        profile = Profile.objects.get(user=self.user)
        profile.leaderboard_user = None
        profile.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        slugs = [e["slug"] for e in resp.json()["events"]]
        self.assertIn(self.active.slug, slugs)


class StatsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-stats")
        lb_user = LeaderboardUser.objects.create(name="A")
        ev = Event.objects.create(
            sheet_id="s", sheet_list_id="x", name="E", place="Brno", points=10,
            date=timezone.now() - timedelta(days=1),
        )
        UserToEvent.objects.create(user=lb_user, event=ev, points=10)

    def test_shape_and_cache_header(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ("players", "events", "points"):
            self.assertIn(key, data)
        self.assertEqual(data["events"], 1)
        self.assertEqual(data["points"], 10)
        self.assertIn("max-age", resp["Cache-Control"])


class HeroApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-hero")

    def test_shape_and_cache_header(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("hero_events", resp.json())
        self.assertIsInstance(resp.json()["hero_events"], list)
        self.assertIn("max-age", resp["Cache-Control"])
