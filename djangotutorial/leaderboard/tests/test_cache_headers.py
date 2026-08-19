"""Every GET endpoint must say, out loud, whether a shared cache may keep it.

This is the one place where a performance change can create a data leak: if a
CDN stores a response that varied by who asked for it, the next visitor is
served someone else's data. Django's `Vary: Cookie` is not enough on its own --
CDNs commonly ignore Vary values other than Accept-Encoding, and Cloudflare in
front of this site was observed doing exactly that: a request carrying a session
cookie was answered from the edge cache.

What made that dangerous was silence, not a wrong setting. A view with no
decorator sends no `Cache-Control` at all, and the edge then applies a default
TTL of its own choosing -- so "I forgot" and "I decided it is public" look
identical on the wire. `/api/v1/gallery/` reached production that way while
carrying a per-user `liked_by_me` flag.

Hence the sweep below: it walks the URLconf rather than a hand-written list, so
a new endpoint cannot slip through by not being thought of. Every GET view must
carry `@never_cache` or `@cache_control(public=True, ...)`, and the choice
between them is the author's -- the test only insists that one was made.
"""
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from rest_framework.test import APIClient

from leaderboard.models import Event, Season, User as LeaderboardUser

# Sample values for URL parameters. The endpoints are only probed for their
# headers, so these never need to resolve to a real row -- a 404 or a 403 is
# fine and still carries the header, because both decorators sit outside
# @api_view and stamp whatever response comes back.
_SAMPLE = {"int": "1", "slug": "x", "str": "x", "uuid": "0" * 8}

# API prefixes this applies to. The SPA catch-all, the admin and the media view
# are not DRF and are covered by their own tests.
_API_PREFIXES = ("api/v1/",)


def _api_get_endpoints():
    """(url, name) for every DRF endpoint under /api/v1/ that answers GET."""
    found = []

    def walk(patterns, prefix=""):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns, prefix + str(entry.pattern))
                continue
            if not isinstance(entry, URLPattern) or not entry.name:
                continue
            full = prefix + str(entry.pattern)
            if not full.startswith(_API_PREFIXES):
                continue
            # @api_view builds a class and hangs it on the view as `.cls`; a GET
            # handler on it is what tells us this endpoint answers GET at all.
            # POST-only endpoints are irrelevant here -- nothing caches a POST.
            view_cls = getattr(entry.callback, "cls", None)
            if view_cls is None or not hasattr(view_cls, "get"):
                continue
            converters = getattr(entry.pattern, "converters", {}) or {}
            kwargs = {
                name: _SAMPLE.get(type(conv).__name__.replace("Converter", "").lower(), "1")
                for name, conv in converters.items()
            }
            found.append((reverse(entry.name, kwargs=kwargs), entry.name))
        return found

    walk(get_resolver().url_patterns)
    return found


class EveryGetEndpointDeclaresItsCacheabilityTests(TestCase):
    """The sweep. Anonymous, because that is the request a CDN caches."""

    def setUp(self):
        self.client = APIClient()

    def test_no_get_endpoint_is_silent_about_caching(self):
        endpoints = _api_get_endpoints()
        # Guard the guard: if the walk ever stops finding endpoints, this test
        # would pass by examining nothing at all.
        self.assertGreater(len(endpoints), 15, "URLconf walk found almost nothing")

        silent = []
        for url, name in endpoints:
            cache_control = self.client.get(url).headers.get("Cache-Control", "")
            if "no-store" not in cache_control and "public" not in cache_control:
                silent.append(f"{name} ({url}) -> {cache_control!r}")

        self.assertEqual(silent, [], (
            "These GET endpoints send no cache decision, so Cloudflare applies a "
            "TTL of its own — and will serve one visitor's response to the next. "
            "Add @never_cache (personalised) or @cache_control(public=True, "
            "max_age=...) (identical for everyone):\n  " + "\n  ".join(silent)
        ))

    def test_nothing_claims_to_be_both_public_and_uncacheable(self):
        contradictory = []
        for url, name in _api_get_endpoints():
            cache_control = self.client.get(url).headers.get("Cache-Control", "")
            if "no-store" in cache_control and "public" in cache_control:
                contradictory.append(f"{name} -> {cache_control!r}")
        self.assertEqual(contradictory, [])


class NoStoreOnPersonalisedEndpointsTests(TestCase):
    """Named cases, kept alongside the sweep.

    The sweep proves a decision was made; these say which decision is correct
    for the endpoints where it is not obvious from the name. Several of these
    look public at a glance and are not: `events_list` varies by role (admins
    and close/photographer users see unreleased events), and `player_detail`
    varies by the target's privacy flags.
    """

    @classmethod
    def setUpTestData(cls):
        cls.lb_user = LeaderboardUser.objects.create(name="Cache Carl")
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

    def assert_public(self, url):
        resp = self.client.get(url)
        cache_control = resp.headers.get("Cache-Control", "")
        self.assertIn("public", cache_control, f"{url} is not edge-cacheable: {cache_control!r}")
        self.assertNotIn("no-store", cache_control)

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

    def test_my_likes_are_never_cached(self):
        # The personalised half of the gallery. This is the endpoint that exists
        # so the gallery itself does not have to carry per-user state.
        self.assert_no_store(reverse("api-photos-liked"))

    def test_gallery_is_public_and_carries_no_per_user_state(self):
        # The counterpart: the gallery may be cached precisely because the like
        # state moved out of it. If `liked_by_me` ever comes back, the response
        # stops being the same for everyone and this cache turns into a leak.
        url = reverse("api-gallery")
        self.assert_public(url)
        self.assertNotIn("liked_by_me", str(self.client.get(url).json()))

    def test_genuinely_public_endpoints_stay_cacheable(self):
        # This work must not have made everything uncacheable, which would push
        # all traffic back onto the origin.
        self.assert_public(reverse("api-seasons"))
        self.assert_public(reverse("api-leaderboard"))
