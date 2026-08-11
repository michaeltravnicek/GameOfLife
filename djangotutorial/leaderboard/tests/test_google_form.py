"""Reading and submitting Google Forms.

The parser reads an undocumented blob off Google's respondent page, so the
fixture here is a real one (captured from a live form) rather than something
hand-written to match the parser. The tests that matter are the *refusals*: an
unparseable form must degrade to the iframe embed, never raise and never post a
half-filled response.

Nothing here touches the network — `requests` is patched throughout.
"""
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from django.contrib.auth.models import User as AuthUser
from leaderboard import google_form
from leaderboard.models import Event

FIXTURE = Path(__file__).parent / "fixtures" / "google_form_page.html"
FORM_HTML = FIXTURE.read_text(encoding="utf-8")
SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSd05dlpgq/viewform"


class ParseSchemaTests(TestCase):
    def test_reads_every_question_from_a_real_form(self):
        schema = google_form.parse_schema(FORM_HTML)
        self.assertEqual(schema["title"], "Kokosy na sněhu, 30.1 Kouty")
        self.assertEqual(
            [f["type"] for f in schema["fields"]],
            ["short_text", "short_text", "radio", "scale", "long_text"],
        )

    def test_reads_entry_ids_labels_and_required_flags(self):
        fields = {f["label"]: f for f in google_form.parse_schema(FORM_HTML)["fields"]}
        phone = fields["Telefon (bez předvolby)"]
        self.assertEqual(phone["entry_id"], "entry.1329707069")
        self.assertTrue(phone["required"])
        self.assertFalse(fields["Pokud máš ještě něco na srdci, tady je prostor."]["required"])

    def test_reads_choice_options(self):
        fields = {f["label"]: f for f in google_form.parse_schema(FORM_HTML)["fields"]}
        self.assertEqual(fields["Zúčastnil/a ses této akce?"]["options"], ["Ano", "Ne"])
        self.assertEqual(len(fields["Jak hodnotíš tuto akci?"]["options"]), 10)

    def test_a_page_without_the_blob_is_not_an_error(self):
        # Google changing their page format must degrade to the embed, not 500.
        self.assertIsNone(google_form.parse_schema("<html><body>nope</body></html>"))

    def test_malformed_blob_returns_none(self):
        html = "<script>var FB_PUBLIC_LOAD_DATA_ = [1,2,;</script>"
        self.assertIsNone(google_form.parse_schema(html))

    def test_multi_page_forms_are_refused(self):
        # Page breaks (type 8) need a pageHistory field we don't model, so a
        # partial submission would be silently accepted by Google.
        html = self._blob('[[["i",[[0,null,1]]],["p","",null,8]]]')
        self.assertIsNone(google_form.parse_schema(html))

    def test_unknown_question_types_are_refused(self):
        # Better the whole form falls back than one question quietly vanishes.
        html = self._blob('[[["q","Grid?",null,7,[[1,null,1]]]]]')
        self.assertIsNone(google_form.parse_schema(html))

    def test_grid_questions_are_refused(self):
        html = self._blob('[[["q","Rows",null,0,[[1,null,1],[2,null,1]]]]]')
        self.assertIsNone(google_form.parse_schema(html))

    def _blob(self, items):
        return f"<script>var FB_PUBLIC_LOAD_DATA_ = [null,[null,{items},null,null,null,null,null,null,\"T\"]];</script>"


class FetchSchemaTests(TestCase):
    def setUp(self):
        cache.clear()

    def _resp(self, *, text=FORM_HTML, url=SURVEY_URL, ok=True):
        class R:
            def __init__(self):
                self.text, self.url, self.ok = text, url, ok

            def raise_for_status(self):
                pass
        return R()

    @patch("leaderboard.google_form.requests.get")
    def test_learns_the_responder_id_from_the_url_it_lands_on(self, get):
        # Admins paste the /edit URL; Google redirects to the responder form,
        # and only that id works for submitting.
        get.return_value = self._resp(
            url="https://docs.google.com/forms/d/e/1FAIpQLSrealone/viewform")
        schema = google_form.fetch_schema(
            "https://docs.google.com/forms/d/1FileId/edit?ouid=123")
        self.assertEqual(schema["form_id"], "1FAIpQLSrealone")

    @patch("leaderboard.google_form.requests.get")
    def test_result_is_cached(self, get):
        get.return_value = self._resp()
        google_form.fetch_schema(SURVEY_URL)
        google_form.fetch_schema(SURVEY_URL)
        self.assertEqual(get.call_count, 1)

    @patch("leaderboard.google_form.requests.get")
    def test_failure_is_cached_too(self, get):
        # Without this an unparseable form re-fetches from Google on every
        # single page view.
        get.return_value = self._resp(text="<html>nope</html>")
        self.assertIsNone(google_form.fetch_schema(SURVEY_URL))
        self.assertIsNone(google_form.fetch_schema(SURVEY_URL))
        self.assertEqual(get.call_count, 1)

    @patch("leaderboard.google_form.requests.get",
           side_effect=google_form.requests.Timeout("slow"))
    def test_a_google_outage_returns_none(self, _get):
        self.assertIsNone(google_form.fetch_schema(SURVEY_URL))

    @patch("leaderboard.google_form.requests.get")
    def test_requests_carry_a_timeout(self, get):
        get.return_value = self._resp()
        google_form.fetch_schema(SURVEY_URL)
        self.assertEqual(get.call_args.kwargs["timeout"], google_form.TIMEOUT)


class SubmitTests(TestCase):
    @patch("leaderboard.google_form.requests.post")
    def test_posts_to_the_form_response_endpoint(self, post):
        post.return_value = type("R", (), {"ok": True, "status_code": 200})()
        self.assertTrue(google_form.submit("FORMID", {"entry.1": ["Ano"]}))
        url, = post.call_args.args
        self.assertEqual(url, "https://docs.google.com/forms/d/e/FORMID/formResponse")
        self.assertEqual(post.call_args.kwargs["data"], {"entry.1": ["Ano"]})

    @patch("leaderboard.google_form.requests.post")
    def test_a_rejected_submission_reports_failure(self, post):
        post.return_value = type("R", (), {"ok": False, "status_code": 400})()
        self.assertFalse(google_form.submit("FORMID", {}))

    @patch("leaderboard.google_form.requests.post",
           side_effect=google_form.requests.ConnectionError("down"))
    def test_a_network_failure_reports_failure(self, _post):
        self.assertFalse(google_form.submit("FORMID", {}))


# Native rendering is off in production (see settings.GOOGLE_FORM_NATIVE); this
# class is what still proves the parser and the submit path work, so that
# turning the flag back on is a decision rather than a gamble.
@override_settings(GOOGLE_FORM_NATIVE=True)
class SignupFormEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = AuthUser.objects.create_user("tester", password="pw12345678")
        self.event = Event.objects.create(
            name="Kokosy", place="Kouty", points=50, date=timezone.now(),
            survey_url=SURVEY_URL,
        )
        self.url = reverse("api-event-signup-form", args=[self.event.slug])
        self.submit_url = reverse("api-event-signup-form-submit", args=[self.event.slug])

    def _schema(self):
        schema = google_form.parse_schema(FORM_HTML)
        schema["form_id"] = "FORMID"
        return schema

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_404_when_the_event_has_no_form(self):
        self.client.force_login(self.user)
        bare = Event.objects.create(name="Bez", place="Brno", points=10, date=timezone.now())
        resp = self.client.get(reverse("api-event-signup-form", args=[bare.slug]))
        self.assertEqual(resp.status_code, 404)

    @patch("leaderboard.api.views.fetch_schema")
    def test_returns_the_question_list(self, fetch):
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        body = self.client.get(self.url).json()
        self.assertFalse(body["embed_only"])
        self.assertEqual(len(body["fields"]), 5)

    @patch("leaderboard.api.views.fetch_schema", return_value=None)
    def test_falls_back_to_embed_when_unreadable(self, _fetch):
        self.client.force_login(self.user)
        body = self.client.get(self.url).json()
        self.assertTrue(body["embed_only"])
        self.assertEqual(body["url"], SURVEY_URL)

    @patch("leaderboard.api.views.submit_form", return_value=True)
    @patch("leaderboard.api.views.fetch_schema")
    def test_forwards_a_valid_submission(self, fetch, submit):
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        resp = self.client.post(self.submit_url, {
            "entry.1329707069": "777123456",
            "entry.1092879836": "Michael",
            "entry.126014420": "Ano",
            "entry.1076937767": "8",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        form_id, payload = submit.call_args.args
        self.assertEqual(form_id, "FORMID")
        self.assertEqual(payload["entry.126014420"], ["Ano"])
        # The optional comment was left out, so it must not be posted at all.
        self.assertNotIn("entry.547229304", payload)

    @patch("leaderboard.api.views.submit_form")
    @patch("leaderboard.api.views.fetch_schema")
    def test_missing_required_answers_are_rejected_before_google(self, fetch, submit):
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        resp = self.client.post(self.submit_url, {"entry.1092879836": "Michael"},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("entry.1329707069", resp.json()["errors"])
        submit.assert_not_called()

    @patch("leaderboard.api.views.submit_form")
    @patch("leaderboard.api.views.fetch_schema")
    def test_an_answer_outside_the_offered_options_is_rejected(self, fetch, submit):
        # Google accepts anything posted at it, so this check is ours to make.
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        resp = self.client.post(self.submit_url, {
            "entry.1329707069": "777123456",
            "entry.1092879836": "Michael",
            "entry.126014420": "Možná",
            "entry.1076937767": "8",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        submit.assert_not_called()

    @patch("leaderboard.api.views.submit_form")
    @patch("leaderboard.api.views.fetch_schema")
    def test_answers_to_questions_that_no_longer_exist_are_dropped(self, fetch, submit):
        submit.return_value = True
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        self.client.post(self.submit_url, {
            "entry.1329707069": "777123456",
            "entry.1092879836": "Michael",
            "entry.126014420": "Ano",
            "entry.1076937767": "8",
            "entry.999999": "stale question from a cached page",
        }, content_type="application/json")
        self.assertNotIn("entry.999999", submit.call_args.args[1])

    @patch("leaderboard.api.views.submit_form", return_value=False)
    @patch("leaderboard.api.views.fetch_schema")
    def test_a_google_rejection_is_reported_not_swallowed(self, fetch, _submit):
        fetch.return_value = self._schema()
        self.client.force_login(self.user)
        resp = self.client.post(self.submit_url, {
            "entry.1329707069": "777123456",
            "entry.1092879836": "Michael",
            "entry.126014420": "Ano",
            "entry.1076937767": "8",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 502)


@override_settings(GOOGLE_FORM_NATIVE=False)
class NativeRenderingDisabledTests(TestCase):
    """The shipped default: sign-up hands out a link, we render nothing.

    The parser rests on two undocumented Google endpoints. With the flag off,
    neither is touched — these tests assert we don't call Google at all, which
    is the actual reason the flag exists.
    """

    def setUp(self):
        cache.clear()
        self.user = AuthUser.objects.create_user("linkuser", password="pw12345678")
        self.event = Event.objects.create(
            name="Kokosy", place="Kouty", points=50, date=timezone.now(),
            survey_url=SURVEY_URL,
        )
        self.url = reverse("api-event-signup-form", args=[self.event.slug])
        self.submit_url = reverse("api-event-signup-form-submit", args=[self.event.slug])

    @patch("leaderboard.api.views.fetch_schema")
    def test_returns_embed_only_without_asking_google(self, fetch):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"embed_only": True, "url": SURVEY_URL})
        fetch.assert_not_called()

    @patch("leaderboard.api.views.submit_form")
    @patch("leaderboard.api.views.fetch_schema")
    def test_submitting_is_gone_not_silently_accepted(self, fetch, submit):
        # The one outcome worth ruling out: telling a member their sign-up
        # landed when nothing was forwarded anywhere.
        self.client.force_login(self.user)
        resp = self.client.post(self.submit_url, {
            "entry.1092879836": "Michael",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 410)
        submit.assert_not_called()
        fetch.assert_not_called()

    def test_an_event_without_a_form_still_404s(self):
        no_form = Event.objects.create(
            name="Bez dotazníku", place="Brno", points=10, date=timezone.now(),
        )
        self.client.force_login(self.user)
        resp = self.client.get(reverse("api-event-signup-form", args=[no_form.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_still_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
