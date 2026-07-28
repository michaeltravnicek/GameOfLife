"""CSP is enforced, strict on scripts, and its allowlist matches what the app loads.

A CSP that is wrong in the strict direction breaks the site silently in the
user's browser, with nothing in the server logs — which is why the allowlist is
asserted here against the real asset inventory (Google Fonts, OpenStreetMap
tiles) rather than left to drift.

The policy is *enforced* in production (report-only ships the header but blocks
nothing, so it stops no XSS). In the test/dev environment it ships report-only,
so these tests read the report-only header — the directive *values* are what
matter and they are identical either way.
"""
from django.test import TestCase, override_settings
from django.urls import reverse


class ContentSecurityPolicyTests(TestCase):
    def _policy(self, header="Content-Security-Policy-Report-Only"):
        return self.client.get(reverse("robots")).headers.get(header, "")

    def test_a_csp_header_is_always_present(self):
        resp = self.client.get(reverse("robots"))
        self.assertTrue(
            "Content-Security-Policy" in resp.headers
            or "Content-Security-Policy-Report-Only" in resp.headers,
            "Every response must carry a CSP header.",
        )

    def test_scripts_are_restricted_to_self(self):
        # The directive that actually stops an injected <script> from running.
        policy = self._policy()
        self.assertIn("script-src 'self'", policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", policy)

    def test_clickjacking_is_blocked(self):
        self.assertIn("frame-ancestors 'none'", self._policy())

    def test_google_fonts_are_allowed(self):
        # index.html links the stylesheet from googleapis and the files from gstatic.
        policy = self._policy()
        self.assertIn("https://fonts.googleapis.com", policy)
        self.assertIn("https://fonts.gstatic.com", policy)

    def test_map_tiles_are_allowed(self):
        # Leaflet on the event detail page; without this the map renders blank.
        self.assertIn("https://*.tile.openstreetmap.org", self._policy())

    @override_settings(X_FRAME_OPTIONS="DENY")
    def test_base_uri_and_object_src_are_locked_down(self):
        policy = self._policy()
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("object-src 'none'", policy)


class AdminCSPExemptionTests(TestCase):
    """The Django admin ships inline <script> that a strict script-src would break,
    so the admin path — and only the admin path — gets 'unsafe-inline'."""

    def _csp(self, resp):
        return (
            resp.headers.get("Content-Security-Policy")
            or resp.headers.get("Content-Security-Policy-Report-Only", "")
        )

    def test_admin_path_allows_inline_scripts(self):
        # Unauthenticated GET redirects to the admin login, but the response still
        # goes through the middleware stack and carries the relaxed policy.
        resp = self.client.get("/admin/", follow=False)
        self.assertIn("'unsafe-inline'", self._csp(resp))

    def test_non_admin_path_keeps_strict_script_src(self):
        resp = self.client.get(reverse("robots"))
        policy = self._csp(resp)
        self.assertIn("script-src 'self'", policy)
        self.assertNotIn("'unsafe-inline'", policy.split("script-src")[1].split(";")[0])
