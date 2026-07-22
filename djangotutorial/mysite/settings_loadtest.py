"""Settings for load testing — capacity measurement, not production.

A separate module rather than an env-var switch inside settings.py on purpose:
this turns off the rate limiter and the brute-force lockout, and that must not
be reachable in production by setting a variable.

Use with:  DJANGO_SETTINGS_MODULE=mysite.settings_loadtest

Run the load test both ways:
  * with these settings  -> raw server capacity, throttles out of the picture
  * with mysite.settings -> whether the configured limits are sane for real use
"""
from .settings import *  # noqa: F401,F403
from .settings import REST_FRAMEWORK

# Measure how much the server can actually serve. With the normal limits, a
# load test mostly measures the rate limiter — every result would be a 429 and
# tell us nothing about capacity.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        scope: None for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    },
}

# Repeated logins from one IP would otherwise trip the lockout immediately.
AXES_ENABLED = False

# Never report load-test traffic as production errors — a failing run would
# otherwise file thousands of issues and burn the quota.
#
# Blanking the setting is not enough: `from .settings import *` above has
# already executed sentry_sdk.init(), so the client exists. Re-initialising
# without a DSN replaces it with an inert one.
SENTRY_DSN = ""
import sentry_sdk  # noqa: E402

# dsn="" and not dsn=None: None means "fall back to the SENTRY_DSN environment
# variable", which is precisely the value we are trying to get rid of.
sentry_sdk.init(dsn="")

# Keep logging quiet; per-request log lines are themselves a measurable cost.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
