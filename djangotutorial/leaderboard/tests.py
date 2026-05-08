import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from leaderboard.models import Event, User as LeaderboardUser, UserToEvent
from leaderboard.views import _haversine_distance


# Brno coordinates (used as a reference point in tests)
BRNO_LAT = 49.1951
BRNO_LON = 16.6068


class HaversineTests(TestCase):
    def test_zero_distance(self):
        d = _haversine_distance(BRNO_LAT, BRNO_LON, BRNO_LAT, BRNO_LON)
        self.assertAlmostEqual(d, 0, places=2)

    def test_known_distance_brno_to_prague(self):
        # Prague approx 50.0755, 14.4378 — straight-line ≈ 184 km
        prague_lat, prague_lon = 50.0755, 14.4378
        d = _haversine_distance(BRNO_LAT, BRNO_LON, prague_lat, prague_lon)
        self.assertGreater(d, 180_000)
        self.assertLess(d, 200_000)

    def test_short_distance_100m(self):
        # 100m north (~0.0009 degrees latitude)
        d = _haversine_distance(BRNO_LAT, BRNO_LON, BRNO_LAT + 0.0009, BRNO_LON)
        self.assertGreater(d, 80)
        self.assertLess(d, 120)


class CheckinWindowEndTests(TestCase):
    def test_uses_end_date_when_set(self):
        start = timezone.now()
        end = start + timedelta(hours=2)
        ev = Event(name="X", date=start, end_date=end, points=10, place="Brno", sheet_id="s", sheet_list_id="l")
        self.assertEqual(ev.checkin_window_end, end)

    def test_falls_back_to_date_plus_4h(self):
        start = timezone.now()
        ev = Event(name="X", date=start, points=10, place="Brno", sheet_id="s", sheet_list_id="l")
        self.assertEqual(ev.checkin_window_end, start + timedelta(hours=4))


class EventCheckinViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="tester", password="testpass")

        # Create a leaderboard user and bind via Profile
        self.lb_user = LeaderboardUser.objects.create(number=42, name="Test Tester")
        # Profile auto-created by signal? Check or create explicitly
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.leaderboard_user = self.lb_user
        profile.save()

        # Active event happening NOW with coords at Brno
        now = timezone.now()
        self.event = Event.objects.create(
            sheet_id="test_sheet",
            sheet_list_id="test_list",
            name="Test Event",
            description="Test",
            place="Brno",
            date=now - timedelta(minutes=10),  # Started 10 min ago
            end_date=now + timedelta(hours=2),  # Ends in 2 hours
            points=120,
            latitude=BRNO_LAT,
            longitude=BRNO_LON,
            checkin_radius=500,
        )

        self.client.login(username="tester", password="testpass")
        self.url = reverse("event_checkin", kwargs={"slug": self.event.slug})

    def _post_coords(self, lat, lon):
        return self.client.post(
            self.url,
            data=json.dumps({"latitude": lat, "longitude": lon}),
            content_type="application/json",
        )

    def test_successful_checkin_creates_user_to_event(self):
        # User is right at the venue
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["already_had"])
        self.assertEqual(data["points"], 120)
        self.assertTrue(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_double_checkin_does_not_double_award(self):
        # First check-in succeeds
        self._post_coords(BRNO_LAT, BRNO_LON)
        # Second check-in returns already_had
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["already_had"])
        self.assertEqual(UserToEvent.objects.filter(user=self.lb_user, event=self.event).count(), 1)

    def test_checkin_too_far_returns_400(self):
        # 5 km away (way outside 500m radius)
        resp = self._post_coords(BRNO_LAT + 0.045, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("příliš daleko", data["error"])
        self.assertIn("distance_m", data)
        self.assertFalse(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_checkin_outside_time_window_returns_400(self):
        # Move event into the past so window is closed
        self.event.date = timezone.now() - timedelta(days=1)
        self.event.end_date = timezone.now() - timedelta(hours=20)
        self.event.save()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("časové okno", resp.json()["error"])

    def test_checkin_event_without_coords_returns_400(self):
        self.event.latitude = None
        self.event.longitude = None
        self.event.save()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nemá aktivní check-in", resp.json()["error"])

    def test_invalid_coordinates_returns_400(self):
        resp = self.client.post(
            self.url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Neplatné", resp.json()["error"])

    def test_missing_coordinates_returns_400(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"latitude": BRNO_LAT}),  # missing longitude
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_user_redirected(self):
        self.client.logout()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        # login_required redirects to login (302)
        self.assertEqual(resp.status_code, 302)

    def test_user_without_profile_link_returns_400(self):
        # Strip the profile link
        profile = Profile.objects.get(user=self.user)
        profile.leaderboard_user = None
        profile.save()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("není propojen", resp.json()["error"])

    def test_window_opens_30_minutes_before_start(self):
        # Move event to 20 minutes from now — should be inside the 30-min pre-window
        self.event.date = timezone.now() + timedelta(minutes=20)
        self.event.end_date = timezone.now() + timedelta(hours=3)
        self.event.save()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)

    def test_window_closed_31_minutes_before_start(self):
        # Move event to 31 minutes from now — should be outside the 30-min pre-window
        self.event.date = timezone.now() + timedelta(minutes=31)
        self.event.end_date = timezone.now() + timedelta(hours=3)
        self.event.save()
        resp = self._post_coords(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("časové okno", resp.json()["error"])


class HomePageBannerTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="banner_test", password="x")
        self.lb_user = LeaderboardUser.objects.create(number=99, name="Banner Tester")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.leaderboard_user = self.lb_user
        profile.save()

        now = timezone.now()
        self.active_event = Event.objects.create(
            sheet_id="banner_sheet", sheet_list_id="banner_list",
            name="Active Live Event", place="Brno", points=50,
            date=now - timedelta(minutes=5), end_date=now + timedelta(hours=1),
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )

    # Use a marker that only appears in the rendered banner instance,
    # not in the CSS rule names — "Právě probíhá!" is only in the banner HTML.
    BANNER_MARKER = "Právě probíhá!"

    def test_active_event_appears_in_banner_for_authenticated_user(self):
        self.client.login(username="banner_test", password="x")
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Active Live Event")
        self.assertContains(resp, self.BANNER_MARKER)

    def test_no_banner_for_anonymous_user(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.BANNER_MARKER)

    def test_no_banner_after_user_already_has_points(self):
        UserToEvent.objects.create(user=self.lb_user, event=self.active_event, points=50)
        self.client.login(username="banner_test", password="x")
        resp = self.client.get(reverse("home"))
        self.assertNotContains(resp, self.BANNER_MARKER)

    def test_no_banner_for_event_without_coords(self):
        self.active_event.latitude = None
        self.active_event.longitude = None
        self.active_event.save()
        self.client.login(username="banner_test", password="x")
        resp = self.client.get(reverse("home"))
        self.assertNotContains(resp, self.BANNER_MARKER)
