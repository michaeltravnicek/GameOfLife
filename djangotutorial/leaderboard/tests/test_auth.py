from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from rest_framework.test import APIClient

from accounts.api.throttles import LoginThrottle


class PasswordResetApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-password-reset")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="reset_me", email="me@example.com", password="x",
        )

    def test_valid_email_sends_reset_email(self):
        resp = self.client.post(self.url, data={"email": "me@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("me@example.com", mail.outbox[0].to)

    def test_nonexistent_email_still_returns_200(self):
        # Anti-enumeration: response must look identical for unknown emails.
        resp = self.client.post(self.url, data={"email": "nobody@example.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(len(mail.outbox), 0)  # but no email actually sent

    def test_empty_email_returns_400(self):
        resp = self.client.post(self.url, data={"email": ""}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_response_message_does_not_leak_existence(self):
        ok_msg = self.client.post(self.url, data={"email": "me@example.com"}, format="json").json()
        miss_msg = self.client.post(self.url, data={"email": "nobody@example.com"}, format="json").json()
        self.assertEqual(ok_msg.get("message"), miss_msg.get("message"))


class PasswordResetConfirmApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-password-reset-confirm")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="confirm_me", email="c@example.com", password="oldpass123",
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def _post(self, **data):
        return self.client.post(self.url, data=data, format="json")

    def test_valid_token_sets_password(self):
        resp = self._post(uid=self.uid, token=self.token, new_password="brandNew456")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brandNew456"))

    def test_bad_token_returns_400(self):
        resp = self._post(uid=self.uid, token="bogus-token", new_password="brandNew456")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("oldpass123"))

    def test_malformed_uid_returns_400(self):
        resp = self._post(uid="!!!!", token=self.token, new_password="brandNew456")
        self.assertEqual(resp.status_code, 400)

    def test_missing_fields_returns_400(self):
        resp = self._post(uid=self.uid, token=self.token)
        self.assertEqual(resp.status_code, 400)

    def test_token_is_single_use(self):
        first = self._post(uid=self.uid, token=self.token, new_password="brandNew456")
        self.assertEqual(first.status_code, 200)
        # Changing the password hash invalidates the original token.
        second = self._post(uid=self.uid, token=self.token, new_password="another789")
        self.assertEqual(second.status_code, 400)


class LoginRememberTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-login")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="remember_me", password="topsecret",
        )

    def _login(self, **extra):
        return self.client.post(
            self.url,
            data={"identifier": "remember_me", "password": "topsecret", **extra},
            format="json",
        )

    def test_remember_true_persists_session(self):
        resp = self._login(remember=True)
        self.assertEqual(resp.status_code, 200)
        # The Django session is stored under the session cookie; its
        # get_expiry_age() must be > 0 (i.e. NOT expire on browser close).
        session = self.client.session
        self.assertGreater(session.get_expiry_age(), 24 * 60 * 60)

    def test_remember_false_expires_on_browser_close(self):
        resp = self._login(remember=False)
        self.assertEqual(resp.status_code, 200)
        session = self.client.session
        # set_expiry(0) means expire on browser close — get_expire_at_browser_close() True.
        self.assertTrue(session.get_expire_at_browser_close())

    def test_default_no_remember_expires_on_browser_close(self):
        resp = self._login()  # no `remember` key at all
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.client.session.get_expire_at_browser_close())


class LoginFailureTests(TestCase):
    """Bad credentials → 401 with one generic message (no account enumeration)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-login")
        get_user_model().objects.create_user(username="realuser", password="rightpass")

    def _login(self, identifier, password):
        return self.client.post(
            self.url, data={"identifier": identifier, "password": password}, format="json",
        )

    def test_unknown_identifier_returns_401(self):
        resp = self._login("ghost", "whatever")
        self.assertEqual(resp.status_code, 401)

    def test_wrong_password_returns_401(self):
        resp = self._login("realuser", "wrongpass")
        self.assertEqual(resp.status_code, 401)

    def test_unknown_and_wrong_are_indistinguishable(self):
        # The whole point of the anti-enumeration change: an attacker must not
        # be able to tell "no such user" from "wrong password".
        unknown = self._login("ghost", "whatever")
        wrong = self._login("realuser", "wrongpass")
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.json(), wrong.json())

    def test_missing_fields_returns_400(self):
        # Empty input is a client error (400), distinct from bad creds (401).
        resp = self._login("", "")
        self.assertEqual(resp.status_code, 400)


class AuthThrottleTests(TestCase):
    """Throttling is disabled suite-wide; this opts one scope back in to prove it works."""

    def setUp(self):
        cache.clear()  # throttle counters live in the cache — start clean
        self.client = APIClient()
        self.url = reverse("api-login")

    def test_login_throttled_after_limit(self):
        # DRF binds THROTTLE_RATES to the settings dict at class-definition time,
        # so override_settings won't reach it — patch the shared rate dict directly.
        creds = {"identifier": "whoever", "password": "nope"}
        with mock.patch.dict(LoginThrottle.THROTTLE_RATES, {"login": "3/min"}):
            for _ in range(3):
                resp = self.client.post(self.url, data=creds, format="json")
                self.assertEqual(resp.status_code, 401)  # under the limit: normal auth failure
            blocked = self.client.post(self.url, data=creds, format="json")
            self.assertEqual(blocked.status_code, 429)  # 4th request in the window is throttled
