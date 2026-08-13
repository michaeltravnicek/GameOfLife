"""The env override on the generic throttle rates.

It exists so a load test can lift the ceiling without a code change, which means
the knob has to be trustworthy in both directions: it must raise the limit when
asked, and — more importantly — leave the documented default in force when
nobody sets anything.

Testing the parsed value rather than settings.REST_FRAMEWORK is deliberate:
settings.py nulls every throttle rate under `manage.py test` (see the
`if "test" in sys.argv` block), so the wired-up rates are always None here and
asserting on them would prove nothing.
"""
from rest_framework.throttling import SimpleRateThrottle

from django.test import SimpleTestCase

from mysite.settings import _throttle_rate


class ThrottleRateEnvTests(SimpleTestCase):
    def test_default_applies_when_the_variable_is_unset(self):
        self.assertEqual(_throttle_rate("GOL_NOT_SET_ANYWHERE", "120/min"), "120/min")

    def test_env_value_wins(self):
        with self.settings():  # no-op; keeps the env patch local and readable
            import os
            from unittest import mock
            with mock.patch.dict(os.environ, {"ANON_THROTTLE_RATE": "600/min"}):
                self.assertEqual(_throttle_rate("ANON_THROTTLE_RATE", "120/min"), "600/min")

    def test_off_switches_the_scope_off(self):
        import os
        from unittest import mock
        for value in ("off", "OFF", "none", "0", "  "):
            with mock.patch.dict(os.environ, {"ANON_THROTTLE_RATE": value}):
                self.assertIsNone(
                    _throttle_rate("ANON_THROTTLE_RATE", "120/min"),
                    f"{value!r} should disable the scope",
                )

    def test_empty_variable_falls_back_to_the_default(self):
        # Render writes an empty string when a variable is cleared rather than
        # deleted; that must mean "default", never "no limit at all".
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"ANON_THROTTLE_RATE": ""}):
            self.assertEqual(_throttle_rate("ANON_THROTTLE_RATE", "120/min"), "120/min")


class NoneRateMeansNoLimitTests(SimpleTestCase):
    """Pins the DRF behaviour the "off" value relies on."""

    def test_parse_rate_of_none_is_unlimited(self):
        throttle = SimpleRateThrottle.__new__(SimpleRateThrottle)
        self.assertEqual(throttle.parse_rate(None), (None, None))

    def test_allow_request_short_circuits_on_a_none_rate(self):
        throttle = SimpleRateThrottle.__new__(SimpleRateThrottle)
        throttle.rate = None
        throttle.num_requests, throttle.duration = None, None
        # get_cache_key would raise NotImplementedError — reaching it at all
        # would mean the None short-circuit is gone.
        self.assertTrue(throttle.allow_request(request=None, view=None))
