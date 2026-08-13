"""Account-wide lockout (accounts/axes_handler.py).

The pair lockout in test_axes_lockout.py only bounds one host. These cover the
distributed case: many IPs, few guesses each, all against one account.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt, AccessLog
from rest_framework.test import APIClient


@override_settings(
    AXES_ENABLED=True,
    AXES_FAILURE_LIMIT=3,
    AXES_HANDLER="accounts.axes_handler.AccountAwareAxesHandler",
    AXES_IPWARE_PROXY_COUNT=None,  # tests talk to Django directly, no proxy
    ACCOUNT_FAILURE_LIMIT=6,
    ACCOUNT_TRUSTED_IP_DAYS=30,
)
class AccountLockoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-login")
        self.password = "spravneheslo123"
        self.user = get_user_model().objects.create_user(
            username="terc", password=self.password,
        )
        AccessAttempt.objects.all().delete()
        AccessLog.objects.all().delete()
        # AXES_HANDLER is memoized on the proxy, so an override_settings alone
        # would keep using whichever handler was built first.
        AxesProxyHandler.get_implementation(force=True)

    def tearDown(self):
        AxesProxyHandler.get_implementation(force=True)

    def _login(self, password, ip, username="terc"):
        return self.client.post(
            self.url, {"identifier": username, "password": password},
            format="json", REMOTE_ADDR=ip,
        )

    def _spray(self, count, start=1, username="terc"):
        """`count` failures from `count` distinct IPs — under the pair limit each."""
        for i in range(count):
            self._login("spatne", f"10.0.0.{start + i}", username=username)

    def test_distributed_failures_lock_the_account(self):
        self._spray(6)
        # No single IP hit the pair limit of 3, but the account absorbed 6 guesses.
        resp = self._login(self.password, "10.0.0.99")
        self.assertNotEqual(resp.status_code, 200)

    def test_below_the_account_limit_login_still_works(self):
        self._spray(5)
        self.assertEqual(self._login(self.password, "10.0.0.99").status_code, 200)

    def test_trusted_ip_gets_through_the_flood(self):
        # The real user logs in from their own IP first…
        self.assertEqual(self._login(self.password, "203.0.113.7").status_code, 200)
        self.client.post(reverse("api-logout"), REMOTE_ADDR="203.0.113.7")
        # …then the flood arrives from elsewhere and locks the account.
        self._spray(6)
        self.assertNotEqual(self._login(self.password, "10.0.0.99").status_code, 200)
        # Their own network is exempt, so the lockout is not a DoS on them.
        self.assertEqual(self._login(self.password, "203.0.113.7").status_code, 200)

    def test_flood_does_not_leak_to_other_accounts(self):
        other = get_user_model().objects.create_user(
            username="jiny", password=self.password,
        )
        self._spray(6)
        resp = self._login(self.password, "10.0.0.99", username=other.username)
        self.assertEqual(resp.status_code, 200)

    def test_disabled_when_limit_is_unset(self):
        with override_settings(ACCOUNT_FAILURE_LIMIT=0):
            self._spray(6)
            self.assertEqual(self._login(self.password, "10.0.0.99").status_code, 200)
