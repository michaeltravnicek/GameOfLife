"""Open Graph tags rendered into the React shell (mysite.og + mysite.views)."""
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from leaderboard.models import Event
from mysite import og

_SHELL = (
    "<!doctype html>\n<html lang=\"cs\">\n  <head>\n"
    "    <meta charset=\"UTF-8\" />\n"
    "    <title>Game of Life — Život je hra, tak ho hrej</title>\n"
    "  </head>\n  <body><div id=\"root\"></div></body>\n</html>\n"
)


def _make_event(**overrides):
    fields = {
        "sheet_id": "og1", "sheet_list_id": "x",
        "name": "Karaoke Brno 2", "place": "Brno", "points": 50,
        "date": timezone.now() + timedelta(days=7),
        "description": "Zpívání do noci pro odvážné.",
    }
    fields.update(overrides)
    return Event.objects.create(**fields)


class MetadataResolutionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _meta(self, path):
        return og.metadata_for(self.factory.get(path))

    def test_event_detail_uses_event_name_and_description(self):
        event = _make_event()
        meta = self._meta(f"/events/{event.slug}")
        self.assertIn("Karaoke Brno 2", meta["title"])
        self.assertEqual(meta["description"], "Zpívání do noci pro odvážné.")

    def test_event_without_description_falls_back_to_place_date_points(self):
        event = _make_event(description="")
        meta = self._meta(f"/events/{event.slug}")
        self.assertIn("Brno", meta["description"])
        self.assertIn("50 bodů", meta["description"])

    def test_hidden_event_does_not_leak_into_preview(self):
        """Crawlers are anonymous — an unpublished event must stay unnamed."""
        event = _make_event(name="Tajná akce", visible_to_users=False)
        meta = self._meta(f"/events/{event.slug}")
        self.assertNotIn("Tajná akce", meta["title"])
        self.assertEqual(meta["title"], og.DEFAULT_TITLE)

    def test_create_form_path_is_not_treated_as_a_slug(self):
        self.assertEqual(self._meta("/events/vytvorit")["title"], og.DEFAULT_TITLE)

    def test_edit_form_path_is_not_treated_as_a_slug(self):
        event = _make_event()
        self.assertEqual(
            self._meta(f"/events/{event.slug}/upravit")["title"], og.DEFAULT_TITLE
        )

    def test_unknown_slug_falls_back_to_defaults(self):
        self.assertEqual(self._meta("/events/neexistuje")["title"], og.DEFAULT_TITLE)

    def test_static_page_gets_its_own_title(self):
        self.assertEqual(
            self._meta("/leaderboard")["title"], f"Žebříček — {og.SITE_NAME}"
        )

    def test_home_uses_default_title(self):
        self.assertEqual(self._meta("/")["title"], og.DEFAULT_TITLE)

    def test_profile_path_falls_back_to_defaults(self):
        """Player pages deliberately don't put a person's name in a link card."""
        self.assertEqual(self._meta("/profil/michael")["title"], og.DEFAULT_TITLE)

    def test_image_and_url_are_absolute(self):
        meta = self._meta("/")
        self.assertTrue(meta["image"].startswith("http://"))
        self.assertTrue(meta["url"].startswith("http://"))


class RenderAndInjectTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_inject_leaves_exactly_one_title(self):
        meta = og.metadata_for(self.factory.get("/leaderboard"))
        html = og.inject(_SHELL, meta)
        self.assertEqual(html.count("<title>"), 1)
        self.assertIn(f"<title>Žebříček — {og.SITE_NAME}</title>", html)

    def test_inject_appends_when_shell_has_no_title(self):
        html = og.inject(
            "<html><head><meta charset=\"UTF-8\" /></head><body></body></html>",
            og.metadata_for(self.factory.get("/")),
        )
        self.assertIn('property="og:title"', html)

    def test_values_are_html_escaped(self):
        event = _make_event(name='Akce "X" <script>', description="a & b")
        html = og.inject(_SHELL, og.metadata_for(self.factory.get(f"/events/{event.slug}")))
        self.assertNotIn("<script>", html)
        self.assertIn("&quot;X&quot;", html)
        self.assertIn("a &amp; b", html)

    def test_renders_the_tags_crawlers_read(self):
        html = og.inject(_SHELL, og.metadata_for(self.factory.get("/")))
        for needle in ('property="og:title"', 'property="og:description"',
                       'property="og:image"', 'property="og:url"',
                       'property="og:site_name"', 'name="twitter:card"'):
            self.assertIn(needle, html)


class ReactIndexViewTests(TestCase):
    """End-to-end: the HTML Django actually serves carries the tags."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.index_path = os.path.join(self._tmp.name, "index.html")
        with open(self.index_path, "w", encoding="utf-8") as fh:
            fh.write(_SHELL)
        patcher = patch("mysite.views._resolve_index_path", return_value=self.index_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_event_page_serves_event_specific_tags(self):
        event = _make_event()
        response = self.client.get(f"/events/{event.slug}")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Karaoke Brno 2", body)
        self.assertIn('property="og:title"', body)

    def test_home_still_serves_the_spa_shell(self):
        body = self.client.get("/").content.decode()
        self.assertIn('<div id="root">', body)

    def test_injection_failure_still_serves_the_page(self):
        """A metadata bug must never take the whole SPA down."""
        with patch("mysite.og.metadata_for", side_effect=RuntimeError("boom")):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root">', response.content.decode())
