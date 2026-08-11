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
        self.assertIn("Karaoke Brno 2", meta.title)
        self.assertEqual(meta.description, "Zpívání do noci pro odvážné.")

    def test_event_without_description_falls_back_to_place_date_points(self):
        event = _make_event(description="")
        meta = self._meta(f"/events/{event.slug}")
        self.assertIn("Brno", meta.description)
        self.assertIn("50 bodů", meta.description)

    def test_hidden_event_does_not_leak_into_preview(self):
        """Crawlers are anonymous — an unpublished event must stay unnamed."""
        event = _make_event(name="Tajná akce", visible_to_users=False)
        meta = self._meta(f"/events/{event.slug}")
        self.assertNotIn("Tajná akce", meta.title)
        self.assertEqual(meta.title, og.DEFAULT_TITLE)

    def test_create_form_path_is_not_treated_as_a_slug(self):
        self.assertEqual(self._meta("/events/vytvorit").title, og.DEFAULT_TITLE)

    def test_edit_form_path_is_not_treated_as_a_slug(self):
        event = _make_event()
        self.assertEqual(
            self._meta(f"/events/{event.slug}/upravit").title, og.DEFAULT_TITLE
        )

    def test_unknown_slug_falls_back_to_defaults(self):
        self.assertEqual(self._meta("/events/neexistuje").title, og.DEFAULT_TITLE)

    def test_static_page_gets_its_own_title(self):
        self.assertEqual(
            self._meta("/leaderboard").title, f"Žebříček — {og.SITE_NAME}"
        )

    def test_home_uses_default_title(self):
        self.assertEqual(self._meta("/").title, og.DEFAULT_TITLE)

    def test_unknown_profile_falls_back_to_defaults(self):
        """A profile URL with no matching account carries no name."""
        self.assertEqual(self._meta("/profil/michael").title, og.DEFAULT_TITLE)

    def test_image_and_url_are_absolute(self):
        meta = self._meta("/")
        self.assertTrue(meta.image.startswith("http://"))
        self.assertTrue(meta.url.startswith("http://"))


class PlayerMetadataTests(TestCase):
    """Player/profile cards: name gated by consent, and never a personal photo."""

    def setUp(self):
        self.factory = RequestFactory()

    def _meta(self, path):
        return og.metadata_for(self.factory.get(path))

    def _player(self, name="Jan Novák", *, consented, username="jan"):
        """Create a leaderboard user. `consented=None` means no account at all."""
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from accounts.models import Profile
        from leaderboard.models import User as LeaderboardUser

        lb = LeaderboardUser.objects.create(name=name)
        if consented is None:
            return lb
        account = get_user_model().objects.create_user(username=username, password="x")
        profile = Profile.objects.create(user=account, leaderboard_user=lb)
        if consented:
            profile.gdpr_consent_at = timezone.now()
            profile.gdpr_consent_version = settings.PRIVACY_POLICY_VERSION
            profile.save()
        return lb

    def test_player_without_consent_shows_short_name(self):
        lb = self._player("Jan Novák", consented=None)
        meta = self._meta(f"/hrac/{lb.id}")
        self.assertIn("Jan N.", meta.title)
        self.assertNotIn("Jan Novák", meta.title)

    def test_player_with_consent_shows_full_name(self):
        lb = self._player("Jan Novák", consented=True)
        self.assertIn("Jan Novák", self._meta(f"/hrac/{lb.id}").title)

    def test_registered_but_unconsented_player_shows_short_name(self):
        """An account without a current consent is not agreement — shortened."""
        lb = self._player("Jan Novák", consented=False)
        meta = self._meta(f"/hrac/{lb.id}")
        self.assertIn("Jan N.", meta.title)
        self.assertNotIn("Jan Novák", meta.title)

    def test_player_card_never_uses_a_personal_photo(self):
        lb = self._player("Jan Novák", consented=True)
        self.assertIn(og.DEFAULT_IMAGE, self._meta(f"/hrac/{lb.id}").image)

    def test_profile_username_resolves_through_the_link(self):
        self._player("Jan Novák", consented=True, username="jan")
        self.assertIn("Jan Novák", self._meta("/profil/jan").title)

    def test_unknown_player_id_falls_back_to_defaults(self):
        self.assertEqual(self._meta("/hrac/999999").title, og.DEFAULT_TITLE)

    def test_members_only_player_is_withheld_from_previews(self):
        """A members-only profile 404s for anonymous browsers; the anonymous
        link-preview crawler must not leak the name either."""
        from accounts.models import Profile

        lb = self._player("Jan Novák", consented=True, username="tajny")
        Profile.objects.filter(leaderboard_user=lb).update(members_only=True)
        # Reachable both by /hrac/<id> and /profil/<username> — neither may show it.
        self.assertEqual(self._meta(f"/hrac/{lb.id}").title, og.DEFAULT_TITLE)
        self.assertEqual(self._meta("/profil/tajny").title, og.DEFAULT_TITLE)


class ExistenceTests(TestCase):
    """`PageMeta.exists` — does the URL name real content?

    It is the difference between "no preview card" and "no such page", which is
    what lets the view answer 404 instead of a soft 404. A page that merely
    hides its card from anonymous crawlers still exists.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self._n = 800000000

    def _meta(self, path):
        return og.metadata_for(self.factory.get(path))

    def test_real_event_exists(self):
        self.assertTrue(self._meta(f"/events/{_make_event().slug}").exists)

    def test_unknown_slug_does_not_exist(self):
        self.assertFalse(self._meta("/events/neexistuje").exists)

    def test_hidden_event_still_exists(self):
        """A draft is a real page for staff — withhold the card, not the page."""
        event = _make_event(name="Tajná akce", visible_to_users=False)
        meta = self._meta(f"/events/{event.slug}")
        self.assertTrue(meta.exists)
        self.assertEqual(meta.title, og.DEFAULT_TITLE)

    def test_forms_and_static_pages_exist(self):
        event = _make_event()
        for path in ("/", "/leaderboard", "/events/vytvorit",
                     f"/events/{event.slug}/upravit", "/naprosto/neznama/cesta"):
            self.assertTrue(self._meta(path).exists, path)

    def test_unknown_player_does_not_exist(self):
        self.assertFalse(self._meta("/hrac/999999").exists)

    def test_unknown_profile_username_does_not_exist(self):
        self.assertFalse(self._meta("/profil/nikdo").exists)

    def test_members_only_player_still_exists(self):
        """Signed-in visitors can open it, so it must not become a 404."""
        from django.contrib.auth import get_user_model
        from accounts.models import Profile
        from leaderboard.models import User as LeaderboardUser

        lb = LeaderboardUser.objects.create(name="Jan Novák")
        account = get_user_model().objects.create_user(username="skryty", password="x")
        Profile.objects.create(
            user=account, leaderboard_user=lb, members_only=True
        )
        self.assertTrue(self._meta(f"/hrac/{lb.id}").exists)
        self.assertTrue(self._meta("/profil/skryty").exists)

    def test_account_without_leaderboard_link_still_exists(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Profile

        account = get_user_model().objects.create_user(username="novy", password="x")
        Profile.objects.filter(user=account).delete()
        Profile.objects.create(user=account, leaderboard_user=None)
        meta = self._meta("/profil/novy")
        self.assertTrue(meta.exists)
        self.assertEqual(meta.title, og.DEFAULT_TITLE)


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

    def test_optional_fields_emit_nothing_when_unset(self):
        """Nobody sets canonical/robots/jsonld yet — the output must not change."""
        html = og.render_tags(og.metadata_for(self.factory.get("/")))
        self.assertNotIn("rel=\"canonical\"", html)
        self.assertNotIn('name="robots"', html)
        self.assertNotIn("ld+json", html)

    def test_optional_fields_render_when_set(self):
        from dataclasses import replace

        meta = replace(
            og.metadata_for(self.factory.get("/")),
            canonical="https://example.com/x",
            robots="noindex, follow",
            jsonld={"@type": "Event", "name": "Akce"},
        )
        html = og.render_tags(meta)
        self.assertIn('<link rel="canonical" href="https://example.com/x" />', html)
        self.assertIn('<meta name="robots" content="noindex, follow" />', html)
        self.assertIn('<script type="application/ld+json">', html)

    def test_jsonld_cannot_break_out_of_the_script_tag(self):
        """HTML-escaping would corrupt JSON, so `<` is escaped JSON-side instead."""
        tag = og._jsonld_tag({"name": "</script><script>alert(1)</script>"})
        self.assertNotIn("<script>alert", tag)
        self.assertIn("\\u003c/script", tag)
        # Still valid JSON, and the escape decodes back to the original text.
        import json
        payload = tag.split(">", 1)[1].rsplit("<", 1)[0]
        self.assertEqual(
            json.loads(payload)["name"], "</script><script>alert(1)</script>"
        )


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
