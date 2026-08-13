"""django-axes brute-force lockout.

AXES_ENABLED is off for the suite at large (see settings), so these tests turn
it back on explicitly and clear the attempt table between cases.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from axes.models import AccessAttempt
from rest_framework.test import APIClient


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3, AXES_RESET_ON_SUCCESS=True)
class AxesLockoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-login")
        self.password = "spravneheslo123"
        self.user = get_user_model().objects.create_user(
            username="terc", password=self.password,
        )
        AccessAttempt.objects.all().delete()

    def _login(self, password):
        return self.client.post(
            self.url, {"identifier": "terc", "password": password}, format="json",
        )

    def test_locks_out_after_failure_limit(self):
        for _ in range(3):
            self.assertEqual(self._login("spatne").status_code, 401)
        # Locked: even the *correct* password is now refused. That's the point —
        # otherwise the attacker just keeps guessing.
        self.assertNotEqual(self._login(self.password).status_code, 200)

    def test_correct_password_works_below_the_limit(self):
        self._login("spatne")
        self._login("spatne")
        self.assertEqual(self._login(self.password).status_code, 200)

    def test_success_resets_the_failure_count(self):
        self._login("spatne")
        self._login("spatne")
        self.assertEqual(self._login(self.password).status_code, 200)
        self.client.post(reverse("api-logout"))
        # Counter was cleared, so two more failures must not trip the limit.
        self._login("spatne")
        self._login("spatne")
        self.assertEqual(self._login(self.password).status_code, 200)

    def test_lockout_does_not_leak_to_a_different_user(self):
        # Lockout keys on (ip, username). A locked account must not take down
        # everyone else sharing that IP — that would be a free DoS.
        other = get_user_model().objects.create_user(
            username="jiny", password=self.password,
        )
        for _ in range(3):
            self._login("spatne")
        resp = self.client.post(
            self.url, {"identifier": other.username, "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
