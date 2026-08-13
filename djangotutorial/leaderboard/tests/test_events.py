from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.cache_config import EVENT_DEPENDENT_CACHE_KEYS
from leaderboard.models import Event, Season


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
                        "date", "points", "image", "logo", "capacity", "is_past"):
                self.assertIn(key, ev)


class EventsListLogoTests(TestCase):
    """The list endpoint must surface each event's logo so the homepage cards
    stop falling back to the generic C50 badge.

    The artwork lives on the linked Badge now, but the response keeps the `logo`
    key — the cards did not change, only where the file hangs.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-events-list")

    def test_logo_present_in_list_payload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from leaderboard.models import Badge

        # 1x1 transparent GIF — enough for an ImageField to accept it.
        gif = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02D\x01\x00;"
        )
        badge = Badge.objects.create(
            name="Karaoke", image_scale=1.5,
            image=SimpleUploadedFile("logo.gif", gif, content_type="image/gif"),
        )
        Event.objects.create(
            name="With Logo", place="Brno", points=10,
            date=timezone.now() + timedelta(days=1), badge=badge,
        )
        events = self.client.get(self.url).json()["events"]
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertIn("logo", ev)
        self.assertTrue(ev["logo"], "logo URL should be a non-empty absolute URL")
        self.assertIn("badges/", ev["logo"])
        # The scale travels with the artwork, not with the event.
        self.assertEqual(ev["logo_scale"], 1.5)
        self.assertEqual(ev["badge_id"], badge.id)

    def test_logo_is_null_when_unset(self):
        Event.objects.create(
            name="No Logo", place="Brno", points=10,
            date=timezone.now() + timedelta(days=1),
        )
        ev = self.client.get(self.url).json()["events"][0]
        self.assertIsNone(ev["logo"])
        # A badgeless event still renders at 1x rather than blowing up the card.
        self.assertEqual(ev["logo_scale"], 1.0)

    def test_one_badge_serves_many_events(self):
        """The whole point: N events, one artwork row, one file."""
        from leaderboard.models import Badge

        badge = Badge.objects.create(name="Sdílené logo")
        for i in range(3):
            Event.objects.create(
                name=f"Edice {i}", place="Brno", points=10,
                date=timezone.now() + timedelta(days=i + 1), badge=badge,
            )
        events = self.client.get(self.url).json()["events"]
        self.assertEqual({ev["badge_id"] for ev in events}, {badge.id})


class EventsSeasonFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-events-list")
        self.season = Season.objects.create(
            name="2025/26", start_date=date(2025, 9, 1), end_date=date(2026, 6, 30),
            is_active=True,
        )
        Event.objects.create(
            sheet_id="in", sheet_list_id="x", name="In Season", place="Brno", points=10,
            date=timezone.make_aware(datetime(2025, 10, 1, 12, 0)),
        )
        Event.objects.create(
            sheet_id="out", sheet_list_id="x", name="Out Season", place="Brno", points=10,
            date=timezone.make_aware(datetime(2025, 1, 1, 12, 0)),
        )

    def test_season_id_filters_to_window(self):
        resp = self.client.get(self.url, {"season_id": self.season.id})
        self.assertEqual(resp.status_code, 200)
        names = [e["name"] for e in resp.json()["events"]]
        self.assertEqual(names, ["In Season"])

    def test_no_season_id_returns_all(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["count"], 2)

    def test_unknown_season_id_returns_404(self):
        resp = self.client.get(self.url, {"season_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_season_id_returns_400(self):
        resp = self.client.get(self.url, {"season_id": "garbage"})
        self.assertEqual(resp.status_code, 400)


class EventVisibilityApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()
        self.visible = Event.objects.create(
            sheet_id="v", sheet_list_id="x", name="Visible", place="Brno", points=10,
            date=now + timedelta(days=1), visible_to_users=True,
        )
        self.hidden = Event.objects.create(
            sheet_id="h", sheet_list_id="x", name="Hidden", place="Brno", points=10,
            date=now + timedelta(days=2), visible_to_users=False,
        )

    def test_public_list_hides_invisible_events(self):
        resp = self.client.get(reverse("api-events-list"))
        names = [e["name"] for e in resp.json()["events"]]
        self.assertIn("Visible", names)
        self.assertNotIn("Hidden", names)

    def test_public_detail_of_hidden_is_404(self):
        resp = self.client.get(reverse("api-event-detail", kwargs={"slug": self.hidden.slug}))
        self.assertEqual(resp.status_code, 404)

    def test_admin_sees_hidden_in_list_and_detail(self):
        admin = get_user_model().objects.create_user(username="adm", password="x")
        Profile.objects.create(user=admin, role=Profile.ROLE_ADMIN)
        self.client.force_authenticate(user=admin)
        names = [e["name"] for e in self.client.get(reverse("api-events-list")).json()["events"]]
        self.assertIn("Hidden", names)
        detail = self.client.get(reverse("api-event-detail", kwargs={"slug": self.hidden.slug}))
        self.assertEqual(detail.status_code, 200)


class EventModelTests(TestCase):
    def test_create_without_google_sheets(self):
        # Sheets are optional now — no sheet_id / sheet_list_id required.
        ev = Event.objects.create(name="Manual", place="Brno", points=10, date=timezone.now())
        self.assertTrue(ev.slug)
        # A second sheet-less event must not collide (unique_together was dropped).
        ev2 = Event.objects.create(name="Manual2", place="Brno", points=10, date=timezone.now())
        self.assertNotEqual(ev.slug, ev2.slug)

    def test_half_set_coordinates_rejected(self):
        ev = Event(name="X", place="Brno", points=10, date=timezone.now(), latitude=49.2)
        with self.assertRaises(ValidationError):
            ev.full_clean()

    def test_survey_url_in_detail(self):
        ev = Event.objects.create(
            sheet_id="su", sheet_list_id="x", name="Survey", place="Brno", points=10,
            date=timezone.now(), survey_url="https://example.com/form",
        )
        resp = self.client.get(reverse("api-event-detail", kwargs={"slug": ev.slug}))
        self.assertEqual(resp.json()["survey_url"], "https://example.com/form")
