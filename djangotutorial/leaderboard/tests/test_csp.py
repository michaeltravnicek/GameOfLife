"""CSP ships in report-only, and the allowlist matches what the app really loads.

A CSP that is wrong in the strict direction breaks the site silently in the
user's browser, with nothing in the server logs — which is why it is report-only
by default and why the allowlist is asserted here against the real asset
inventory (Google Fonts, OpenStreetMap tiles) rather than left to drift.
"""
from django.test import TestCase, override_settings
from django.urls import reverse


class ContentSecurityPolicyTests(TestCase):
    def _policy(self, header="Content-Security-Policy-Report-Only"):
        return self.client.get(reverse("robots")).headers.get(header, "")

    def test_ships_in_report_only_by_default(self):
        resp = self.client.get(reverse("robots"))
        self.assertIn("Content-Security-Policy-Report-Only", resp.headers)
        self.assertNotIn(
            "Content-Security-Policy", resp.headers,
            "CSP must not be enforced until the report-only reports are quiet.",
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
