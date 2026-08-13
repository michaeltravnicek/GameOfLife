"""The health check, and the JSON 404 for API paths.

Both exist for the same reason: a failure should look like a failure. `/`
answers 200 off a memoised file read even with the database down, and an HTML
404 on an /api/ path reaches the SPA as a JSON parse error rather than a 404.
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from mysite.test_utils import SpaShellMixin


class HealthzTests(TestCase):
    def test_reports_ok_when_both_dependencies_answer(self):
        resp = self.client.get(reverse("healthz"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True, "database": "ok", "cache": "ok"})

    def test_is_never_cached(self):
        # A cached health check is a health check of the cache layer.
        resp = self.client.get(reverse("healthz"))
        self.assertIn("no-cache", resp.headers.get("Cache-Control", ""))

    def test_needs_no_authentication(self):
        # Render's prober has no session; requiring one would fail every check.
        self.assertEqual(self.client.get(reverse("healthz")).status_code, 200)

    @patch("mysite.views.connection")
    def test_a_dead_database_is_a_503_not_a_500(self, connection):
        # The whole point: report the failure in a form a prober understands,
        # rather than raising and being indistinguishable from a code bug.
        connection.cursor.side_effect = Exception("could not connect")
        resp = self.client.get(reverse("healthz"))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["database"], "fail")
        self.assertFalse(resp.json()["ok"])

    @patch("mysite.views.cache")
    def test_a_cache_that_accepts_writes_but_returns_nothing_fails(self, cache):
        # The quiet failure mode: every set() succeeds, every get() misses, and
        # the site works but issues every query on every request.
        cache.set.return_value = None
        cache.get.return_value = None
        resp = self.client.get(reverse("healthz"))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["cache"], "fail")

    def test_the_spa_catch_all_does_not_swallow_it(self):
        # /healthz/ has to be reserved in urls.py alongside /api/ and /media/;
        # otherwise React's index.html is served with a cheerful 200.
        resp = self.client.get("/healthz/")
        self.assertEqual(resp["Content-Type"], "application/json")


class ApiNotFoundTests(SpaShellMixin, TestCase):
    def test_unknown_api_path_answers_json(self):
        resp = self.client.get("/api/v1/tohle-neexistuje/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assertIn("error", resp.json())

    def test_unknown_page_path_still_gets_the_spa(self):
        # Client-side routes are unknown to Django by design — the SPA renders
        # its own 404 page, so this must not become a JSON error.
        resp = self.client.get("/tahle-stranka-neexistuje")
        self.assertIn("text/html", resp["Content-Type"])
