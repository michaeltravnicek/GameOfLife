"""Per-IP rate limits for the anonymous auth endpoints (brute-force guard).

Rates live in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]. AnonRateThrottle
keys on client IP and skips authenticated users, so normal logged-in traffic is
never throttled.

These bound one attacker, not one account: a run spread over many IPs passes every
per-IP limit. The account-wide failure counter in accounts/axes_handler.py covers
that case — this module is not the whole brute-force story.
"""
from rest_framework.throttling import AnonRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"
