"""The admin path is configurable, and three things must move together.

Relocating the admin is only worth doing if nothing else quietly keeps pointing
at the old place. The failure modes are all silent: the SPA catch-all swallowing
the new path and serving a blank page, or robots.txt cheerfully publishing the
secret URL it was meant to keep quiet.
"""
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

import mysite.urls


def _reload_urlconf():
    """Re-import the URLconf so a patched ADMIN_URL takes effect.

    The catch-all regex is built at import time from settings, so overriding the
    setting alone would not rebuild it.
    """
    import importlib
    clear_url_caches()
    importlib.reload(mysite.urls)


class AdminUrlTests(TestCase):
    def tearDown(self):
        _reload_urlconf()

    # Force the default path rather than trusting the ambient environment: a
    # local .env (or CI) that sets ADMIN_URL would otherwise make these assert
    # against a moved admin and fail spuriously.
    @override_settings(ADMIN_URL="admin/")
    def test_default_admin_path_serves_the_admin(self):
        _reload_urlconf()
        with self.settings(ROOT_URLCONF="mysite.urls"):
            resp = self.client.get("/admin/", follow=False)
            # Redirect to the admin login, not the SPA shell.
            self.assertIn(resp.status_code, (200, 302))
            if resp.status_code == 302:
                self.assertIn("login", resp["Location"])

    @override_settings(ADMIN_URL="admin/")
    def test_robots_lists_admin_while_it_is_default(self):
        body = self.client.get(reverse("robots")).content.decode()
        self.assertIn("Disallow: /admin/", body)

    @override_settings(ADMIN_URL="sprava-x7k2/")
    def test_custom_admin_path_is_reachable(self):
        _reload_urlconf()
        with self.settings(ROOT_URLCONF="mysite.urls"):
            resp = self.client.get("/sprava-x7k2/", follow=False)
            self.assertIn(resp.status_code, (200, 302))

    @override_settings(ADMIN_URL="sprava-x7k2/")
    def test_catch_all_does_not_swallow_the_custom_admin_path(self):
        # The regression this guards: a hardcoded "admin" in the catch-all would
        # let the SPA answer /sprava-x7k2/ with its shell, so the admin would
        # look like a blank page rather than a login form.
        _reload_urlconf()
        with self.settings(ROOT_URLCONF="mysite.urls"):
            resp = self.client.get("/sprava-x7k2/", follow=False)
            self.assertNotIn(b'id="root"', resp.content)

    @override_settings(ADMIN_URL="sprava-x7k2/")
    def test_robots_does_not_publish_a_custom_admin_path(self):
        _reload_urlconf()
        with self.settings(ROOT_URLCONF="mysite.urls"):
            body = self.client.get(reverse("robots")).content.decode()
            self.assertNotIn("sprava-x7k2", body)
            self.assertNotIn("Disallow: /admin/", body)

    @override_settings(ADMIN_URL="sprava-x7k2/")
    def test_moved_admin_leaves_nothing_behind_at_the_default_path(self):
        """/admin/ must stop being the admin -- but not announce that it moved.

        It falls through to the SPA catch-all, so a scanner gets the same shell
        as any mistyped URL. That is the desired outcome: a Django 404 here would
        still confirm a Django app with a relocated admin, which is a hint worth
        not giving.
        """
        _reload_urlconf()
        with self.settings(ROOT_URLCONF="mysite.urls"):
            resp = self.client.get("/admin/", follow=False)
            self.assertNotIn(resp.status_code, (301, 302))  # no redirect to a login
            self.assertIn(b'id="root"', resp.content)       # plain SPA shell
