"""Per-IP rate limits for the anonymous auth endpoints (brute-force guard).

Rates live in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]. AnonRateThrottle
keys on client IP and skips authenticated users, so normal logged-in traffic is
never throttled.

These bound one attacker, not one account: a run spread over many IPs passes every
per-IP limit. The account-wide failure counter in accounts/axes_handler.py covers
that case — this module is not the whole brute-force story.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"


class PasswordChangeThrottle(UserRateThrottle):
    """Password change is authenticated, so it needs a *user* throttle.

    AnonRateThrottle returns early for signed-in users — reusing one of the
    classes above here would have applied no limit at all. The endpoint checks
    the old password, so it is a guessing surface for anyone who gets hold of a
    logged-in browser.
    """
    scope = "password_change"
