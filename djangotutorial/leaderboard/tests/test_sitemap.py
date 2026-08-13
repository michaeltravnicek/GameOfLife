"""/sitemap.xml and /robots.txt — the crawler-facing surface (mysite.sitemaps)."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from leaderboard.models import Event


def _make_event(**overrides):
    fields = {
        "sheet_id": "sm1", "sheet_list_id": "x",
        "name": "Sitemap Akce", "place": "Brno", "points": 10,
        "date": timezone.now() + timedelta(days=3),
    }
    fields.update(overrides)
    return Event.objects.create(**fields)


class SitemapTests(TestCase):
    def test_lists_static_pages_and_visible_events(self):
        event = _make_event()
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/leaderboard", body)
        self.assertIn(f"/events/{event.slug}", body)

    def test_hidden_event_is_not_listed(self):
        hidden = _make_event(sheet_id="sm2", name="Tajná", visible_to_users=False)
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn(f"/events/{hidden.slug}", body)

    def test_served_as_xml_over_https(self):
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("xml", resp["Content-Type"])
        # protocol is pinned to https so crawlers don't index http duplicates.
        self.assertIn("https://", resp.content.decode())


class RobotsTxtTests(TestCase):
    def test_served_as_plain_text(self):
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/plain")

    @override_settings(ADMIN_URL="admin/")
    def test_blocks_private_paths_and_points_at_the_sitemap(self):
        # Force the default admin path — robots only lists /admin/ while it's
        # the default, and a local .env / CI may have moved ADMIN_URL.
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("/sitemap.xml", body)

    def test_does_not_block_public_content(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("Disallow: /events\n", body)
        self.assertNotIn("Disallow: /leaderboard", body)
