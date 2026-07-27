"""Personalised responses must never be edge-cacheable.

This is the one place where a performance change can create a data leak: if a
CDN stores a response that varied by who asked for it, the next visitor is
served someone else's data. Django's `Vary: Cookie` is not enough on its own --
CDNs commonly ignore Vary values other than Accept-Encoding -- so the endpoints
below say `no-store` explicitly.

The list is deliberately broad. Several of these look public at a glance and are
not: `events_list` varies by role (admins and close/photographer users see
unreleased events), and `player_detail` varies by the target's privacy flags.
"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from leaderboard.models import Event, Season, User as LeaderboardUser


class NoStoreOnPersonalisedEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lb_user = LeaderboardUser.objects.create(number=700000601, name="Cache Carl")
        cls.event = Event.objects.create(
            sheet_id="ch1", sheet_list_id="x", name="Cache Event", place="Praha",
            points=5, date=timezone.now(), visible_to_users=True, slug="cache-event",
        )
        cls.season = Season.objects.create(
            name="2026", start_date="2026-01-01", end_date="2026-12-31", is_active=True,
        )

    def setUp(self):
        self.client = APIClient()

    def assert_no_store(self, url):
        resp = self.client.get(url)
        cache_control = resp.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control, f"{url} is edge-cacheable: {cache_control!r}")

    def test_me_is_never_cached(self):
        self.assert_no_store(reverse("api-me"))

    def test_events_list_is_never_cached(self):
        # Varies by role: admins and close/photographer users see hidden events.
        self.assert_no_store(reverse("api-events-list"))

    def test_event_detail_is_never_cached(self):
        self.assert_no_store(reverse("api-event-detail", args=[self.event.slug]))

    def test_player_detail_is_never_cached(self):
        # Varies by the target's privacy flags and the viewer's identity.
        self.assert_no_store(reverse("api-player", args=[self.lb_user.id]))

    def test_checkin_events_is_never_cached(self):
        self.assert_no_store(reverse("api-checkin-events"))

    def test_genuinely_public_endpoints_stay_cacheable(self):
        # The counterpart check: this work must not have made everything
        # uncacheable, which would push all traffic back onto the origin.
        resp = self.client.get(reverse("api-seasons"))
        self.assertIn("public", resp.headers.get("Cache-Control", ""))
        self.assertNotIn("no-store", resp.headers.get("Cache-Control", ""))
