"""Per-IP rate limits for the auth endpoints (brute-force guard).

Rates live in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].

`login`, `register` and `password_reset` are AllowAny endpoints, so the caller
may or may not hold a session cookie. DRF's AnonRateThrottle returns a None cache
key — i.e. *no limit at all* — the moment `request.user` is authenticated, which
means an attacker can register once, keep the cookie, and loop these endpoints
unmetered (audit 2026-08-26, critical). `_IpRateThrottle` below keys on client IP
for every caller regardless of auth state, so the guard cannot be shrugged off by
logging in.

These bound one attacker, not one account: a run spread over many IPs passes every
per-IP limit. The account-wide failure counter in accounts/axes_handler.py covers
that case — this module is not the whole brute-force story.
"""
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class _IpRateThrottle(SimpleRateThrottle):
    """Rate-limit by client IP for authenticated and anonymous callers alike.

    Same IP resolution as AnonRateThrottle (`get_ident` honours NUM_PROXIES); the
    only difference is that it never short-circuits to "unlimited" for a signed-in
    user.
    """

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginThrottle(_IpRateThrottle):
    scope = "login"


class RegisterThrottle(_IpRateThrottle):
    scope = "register"


class PasswordResetThrottle(_IpRateThrottle):
    scope = "password_reset"


class PasswordChangeThrottle(UserRateThrottle):
    """Password change is authenticated, so it keys on the *user*.

    The endpoint checks the old password, so it is a guessing surface for anyone
    who gets hold of a logged-in browser.
    """
    scope = "password_change"
