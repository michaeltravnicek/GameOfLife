"""The Cloudflare-only origin lock.

Render has no inbound IP firewall, so the guarantee that traffic reached the app
through the Cloudflare edge rests entirely on this header check. Two properties
matter and neither is obvious from reading the middleware:

  * it must be *inert* until ORIGIN_SHARED_SECRET is set, because the deploy
    order is "ship code, verify the header arrives, then enforce" — enforcing
    first takes the whole site down;
  * /healthz/ must stay reachable without the header, because Render's health
    check reaches the service on its internal network and never carries it.
"""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from mysite.middleware import RequireCloudflareOriginMiddleware

SECRET = "s3cret-from-the-transform-rule"


def _ok(request):
    return HttpResponse("reached the view")


class OriginLockTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _response(self, path="/", header=None):
        # Built inside the test so it picks up the overridden setting: the
        # middleware reads ORIGIN_SHARED_SECRET once, in __init__.
        middleware = RequireCloudflareOriginMiddleware(_ok)
        extra = {"HTTP_X_ORIGIN_VERIFY": header} if header is not None else {}
        return middleware(self.factory.get(path, **extra))

    @override_settings(ORIGIN_SHARED_SECRET="")
    def test_unset_secret_lets_everything_through(self):
        # The default, and the state the code ships in.
        self.assertEqual(self._response().status_code, 200)

    @override_settings(ORIGIN_SHARED_SECRET=SECRET)
    def test_correct_header_passes(self):
        self.assertEqual(self._response(header=SECRET).status_code, 200)

    @override_settings(ORIGIN_SHARED_SECRET=SECRET)
    def test_missing_header_is_forbidden(self):
        # A request straight at Render's ingress: no Transform Rule ran.
        self.assertEqual(self._response().status_code, 403)

    @override_settings(ORIGIN_SHARED_SECRET=SECRET)
    def test_wrong_header_is_forbidden(self):
        self.assertEqual(self._response(header="guessed").status_code, 403)

    @override_settings(ORIGIN_SHARED_SECRET=SECRET)
    def test_healthz_is_exempt(self):
        # Render's health check cannot carry the header; a 403 here would mark
        # the service unhealthy and the deploy would roll back.
        self.assertEqual(self._response(path="/healthz/").status_code, 200)

    @override_settings(ORIGIN_SHARED_SECRET=SECRET)
    def test_healthz_without_trailing_slash_is_exempt(self):
        # The route is "healthz/" and APPEND_SLASH would redirect — but this
        # middleware runs before CommonMiddleware, so a health check configured
        # as "/healthz" must be let through here or the service is killed.
        self.assertEqual(self._response(path="/healthz").status_code, 200)
