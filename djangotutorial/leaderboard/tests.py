from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.cache_config import (
    CACHE_KEY_EVENTS_CITIES,
    CACHE_KEY_HOME_STATS,
    EVENT_DEPENDENT_CACHE_KEYS,
)
from leaderboard.checkin import haversine_distance_m
from leaderboard.models import Event, User as LeaderboardUser, UserToEvent
from leaderboard.utils import parse_int_param


# Brno reference point used by all check-in tests.
BRNO_LAT = 49.1951
BRNO_LON = 16.6068


def _make_profile_for(auth_user, *, number):
    """Helper: link `auth_user` to a fresh LeaderboardUser via Profile."""
    lb_user = LeaderboardUser.objects.create(number=number, name=f"Tester {number}")
    profile, _ = Profile.objects.get_or_create(user=auth_user)
    profile.leaderboard_user = lb_user
    profile.save()
    return lb_user


# ────────────────────────────────────────────────────────────────────────
# Geo primitives
# ────────────────────────────────────────────────────────────────────────

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


# ────────────────────────────────────────────────────────────────────────
# Event model
# ────────────────────────────────────────────────────────────────────────

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


class EventSaveCacheInvalidationTests(TestCase):
    """Event.save() must drop every cache key listed in cache_config.EVENT_DEPENDENT_CACHE_KEYS."""

    def test_save_drops_all_dependent_caches(self):
        # Seed every dependent key with a sentinel so we can check it's gone.
        for key in EVENT_DEPENDENT_CACHE_KEYS:
            cache.set(key, "SENTINEL", 60)
        Event.objects.create(
            sheet_id="cache_inv", sheet_list_id="x",
            name="Cache test", place="Brno", points=10,
            date=timezone.now() + timedelta(days=1),
        )
        for key in EVENT_DEPENDENT_CACHE_KEYS:
            self.assertIsNone(cache.get(key), f"Event.save() should have evicted {key}")


# ────────────────────────────────────────────────────────────────────────
# Utils
# ────────────────────────────────────────────────────────────────────────

class ParseIntParamTests(TestCase):
    def test_parses_valid_int(self):
        self.assertEqual(parse_int_param("5", 10), 5)

    def test_falls_back_on_garbage(self):
        self.assertEqual(parse_int_param("xxx", 10), 10)
        self.assertEqual(parse_int_param(None, 10), 10)

    def test_clamps_max(self):
        self.assertEqual(parse_int_param("999", 10, max_val=100), 100)

    def test_clamps_min(self):
        self.assertEqual(parse_int_param("-5", 10, min_val=0), 0)

    def test_no_clamp_without_bounds(self):
        self.assertEqual(parse_int_param("999", 10), 999)


# ────────────────────────────────────────────────────────────────────────
# /api/events/<slug>/checkin/  (DRF JSON endpoint — the only check-in path)
# ────────────────────────────────────────────────────────────────────────

class EventCheckinApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="tester", password="testpass")
        self.lb_user = _make_profile_for(self.user, number=42)

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


# ────────────────────────────────────────────────────────────────────────
# /api/home/  — active_checkin_events block
# ────────────────────────────────────────────────────────────────────────

class HomeApiActiveCheckinTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-home")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="home_test", password="x")
        self.lb_user = _make_profile_for(self.user, number=99)

        now = timezone.now()
        self.active = Event.objects.create(
            sheet_id="active", sheet_list_id="x",
            name="Active Live Event", place="Brno", points=50,
            date=now - timedelta(minutes=5),
            end_date=now + timedelta(hours=1),
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )

    def test_anonymous_user_sees_no_active_events(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["active_checkin_events"], [])

    def test_authenticated_user_sees_active_event(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        slugs = [e["slug"] for e in resp.json()["active_checkin_events"]]
        self.assertIn(self.active.slug, slugs)

    def test_user_already_checked_in_does_not_see_event(self):
        UserToEvent.objects.create(user=self.lb_user, event=self.active, points=50)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["active_checkin_events"], [])

    def test_event_without_coords_excluded(self):
        self.active.latitude = None
        self.active.longitude = None
        self.active.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["active_checkin_events"], [])

    def test_user_without_profile_link_sees_nothing(self):
        profile = Profile.objects.get(user=self.user)
        profile.leaderboard_user = None
        profile.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["active_checkin_events"], [])


# ────────────────────────────────────────────────────────────────────────
# /api/events/  — pagination + cities first-page-only
# ────────────────────────────────────────────────────────────────────────

class EventsListPaginationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-events-list")
        now = timezone.now()
        # Seed 5 events spread across two cities, all in the future.
        for i in range(5):
            Event.objects.create(
                sheet_id=f"ev{i}", sheet_list_id="x",
                name=f"Event {i}", place=("Brno" if i % 2 == 0 else "Praha"),
                date=now + timedelta(days=i + 1), points=10,
            )

    def test_first_page_includes_cities(self):
        resp = self.client.get(self.url, {"limit": 2, "offset": 0})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["events"]), 2)
        self.assertTrue(len(data["cities"]) >= 1)

    def test_subsequent_pages_omit_cities(self):
        resp = self.client.get(self.url, {"limit": 2, "offset": 2})
        self.assertEqual(resp.json()["cities"], [])

    def test_count_and_has_more(self):
        resp = self.client.get(self.url, {"limit": 2, "offset": 0})
        self.assertEqual(resp.json()["count"], 5)
        self.assertTrue(resp.json()["has_more"])
        resp = self.client.get(self.url, {"limit": 100, "offset": 0})
        self.assertFalse(resp.json()["has_more"])

    def test_limit_clamping(self):
        # Garbage limit → default; > max → clamped to 100; negative → clamped to 1.
        resp = self.client.get(self.url, {"limit": "garbage"})
        self.assertEqual(resp.status_code, 200)
        # Max clamp:
        resp = self.client.get(self.url, {"limit": 999})
        self.assertLessEqual(len(resp.json()["events"]), 100)

    def test_offset_negative_clamped(self):
        resp = self.client.get(self.url, {"offset": "-5", "limit": 2})
        # offset should clamp to 0 — meaning first page (cities present).
        self.assertNotEqual(resp.json()["cities"], [])

    def test_only_does_not_break_serializer(self):
        # Sanity: every field the EventListSerializer declares must serialize.
        resp = self.client.get(self.url, {"limit": 5, "offset": 0})
        for ev in resp.json()["events"]:
            for key in ("id", "slug", "name", "description", "place",
                        "date", "points", "image", "capacity", "is_past"):
                self.assertIn(key, ev)


# ────────────────────────────────────────────────────────────────────────
# /api/auth/password-reset/ — anti-enumeration + email send
# ────────────────────────────────────────────────────────────────────────

class PasswordResetApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-password-reset")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="reset_me", email="me@example.com", password="x",
        )

    def test_valid_email_sends_reset_email(self):
        resp = self.client.post(self.url, data={"email": "me@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("me@example.com", mail.outbox[0].to)

    def test_nonexistent_email_still_returns_200(self):
        # Anti-enumeration: response must look identical for unknown emails.
        resp = self.client.post(self.url, data={"email": "nobody@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(len(mail.outbox), 0)  # but no email actually sent

    def test_empty_email_returns_400(self):
        resp = self.client.post(self.url, data={"email": ""}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_response_message_does_not_leak_existence(self):
        ok_msg = self.client.post(self.url, data={"email": "me@example.com"}, format="json").json()
        miss_msg = self.client.post(self.url, data={"email": "nobody@example.com"}, format="json").json()
        self.assertEqual(ok_msg.get("message"), miss_msg.get("message"))


# ────────────────────────────────────────────────────────────────────────
# /api/auth/login/  — Remember me flag
# ────────────────────────────────────────────────────────────────────────

class LoginRememberTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-login")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="remember_me", password="topsecret",
        )

    def _login(self, **extra):
        return self.client.post(
            self.url,
            data={"identifier": "remember_me", "password": "topsecret", **extra},
            format="json",
        )

    def test_remember_true_persists_session(self):
        resp = self._login(remember=True)
        self.assertEqual(resp.status_code, 200)
        # The Django session is stored under the session cookie; its
        # get_expiry_age() must be > 0 (i.e. NOT expire on browser close).
        session = self.client.session
        self.assertGreater(session.get_expiry_age(), 24 * 60 * 60)

    def test_remember_false_expires_on_browser_close(self):
        resp = self._login(remember=False)
        self.assertEqual(resp.status_code, 200)
        session = self.client.session
        # set_expiry(0) means expire on browser close — get_expire_at_browser_close() True.
        self.assertTrue(session.get_expire_at_browser_close())

    def test_default_no_remember_expires_on_browser_close(self):
        resp = self._login()  # no `remember` key at all
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
