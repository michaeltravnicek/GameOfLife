from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.cache_config import CACHE_KEY_HOME_STATS
from leaderboard.checkin import haversine_distance_m
from leaderboard.models import Event, UserToEvent

from .helpers import BRNO_LAT, BRNO_LON, make_profile_for


class HaversineTests(TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_distance_m(BRNO_LAT, BRNO_LON, BRNO_LAT, BRNO_LON), 0, places=2)

    def test_known_distance_brno_to_prague(self):
        # Prague ≈ 50.0755, 14.4378 — straight line ~ 184 km
        d = haversine_distance_m(BRNO_LAT, BRNO_LON, 50.0755, 14.4378)
        self.assertGreater(d, 180_000)
        self.assertLess(d, 200_000)

    def test_short_distance_100m(self):
        # +0.0009° latitude ≈ 100 m
        d = haversine_distance_m(BRNO_LAT, BRNO_LON, BRNO_LAT + 0.0009, BRNO_LON)
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


class EventCheckinApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="tester", password="testpass")
        self.lb_user = make_profile_for(self.user)

        now = timezone.now()
        self.event = Event.objects.create(
            sheet_id="test_sheet", sheet_list_id="test_list",
            name="Test Event", description="Test", place="Brno",
            date=now - timedelta(minutes=10),
            end_date=now + timedelta(hours=2),
            points=120,
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )
        self.url = reverse("api-event-checkin", kwargs={"slug": self.event.slug})
        self.client.force_authenticate(user=self.user)

    def _post(self, lat, lon):
        return self.client.post(self.url, data={"latitude": lat, "longitude": lon}, format="json")

    def test_successful_checkin_creates_user_to_event(self):
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["already_had"])
        self.assertEqual(data["points"], 120)
        self.assertTrue(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_double_checkin_is_idempotent(self):
        self._post(BRNO_LAT, BRNO_LON)
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["already_had"])
        self.assertEqual(UserToEvent.objects.filter(user=self.lb_user, event=self.event).count(), 1)

    def test_too_far_returns_400_with_distance(self):
        # ~5 km north of Brno — well outside the 500 m radius.
        resp = self._post(BRNO_LAT + 0.045, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("příliš daleko", data["error"])
        self.assertIn("distance_m", data)
        self.assertFalse(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_nan_or_out_of_range_coordinates_award_no_points(self):
        # Whatever the error shape (serializer field error vs. service error), the
        # security property is: rejected, and no attendance row created.
        for lat, lon in (("nan", "nan"), ("inf", "inf"), (999, 999)):
            resp = self.client.post(
                self.url, data={"latitude": lat, "longitude": lon}, format="json",
            )
            self.assertEqual(resp.status_code, 400, (lat, lon))
        self.assertFalse(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_service_rejects_nan_coordinates_directly(self):
        # checkin.py is the documented single source of truth; a caller that
        # doesn't go through the serializer must still not be able to pass NaN
        # (every comparison with which is False) straight through the geo-fence.
        from leaderboard.checkin import validate_and_record_checkin
        result = validate_and_record_checkin(self.event, self.user, float("nan"), float("nan"))
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 400)
        self.assertFalse(UserToEvent.objects.filter(user=self.lb_user, event=self.event).exists())

    def test_outside_time_window_returns_400(self):
        self.event.date = timezone.now() - timedelta(days=1)
        self.event.end_date = timezone.now() - timedelta(hours=20)
        self.event.save()
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("časové okno", resp.json()["error"])

    def test_event_without_coords_returns_400(self):
        self.event.latitude = None
        self.event.longitude = None
        self.event.save()
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nemá aktivní check-in", resp.json()["error"])

    def test_missing_coordinates_returns_400(self):
        resp = self.client.post(self.url, data={"latitude": BRNO_LAT}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_returns_403(self):
        self.client.force_authenticate(user=None)
        resp = self._post(BRNO_LAT, BRNO_LON)
        # DRF returns 403 by default for IsAuthenticated failures.
        self.assertIn(resp.status_code, (401, 403))

    def test_user_without_profile_link_returns_400(self):
        profile = Profile.objects.get(user=self.user)
        profile.leaderboard_user = None
        profile.save()
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("není propojen", resp.json()["error"])

    def test_window_opens_30_minutes_before_start(self):
        # 20 min before start → window already open.
        self.event.date = timezone.now() + timedelta(minutes=20)
        self.event.end_date = timezone.now() + timedelta(hours=3)
        self.event.save()
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 200)

    def test_window_closed_31_minutes_before_start(self):
        # 31 min before start → window not yet open.
        self.event.date = timezone.now() + timedelta(minutes=31)
        self.event.end_date = timezone.now() + timedelta(hours=3)
        self.event.save()
        resp = self._post(BRNO_LAT, BRNO_LON)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("časové okno", resp.json()["error"])

    def test_successful_checkin_invalidates_caches(self):
        cache.set(CACHE_KEY_HOME_STATS, "SENTINEL", 60)
        self._post(BRNO_LAT, BRNO_LON)
        self.assertIsNone(cache.get(CACHE_KEY_HOME_STATS))
