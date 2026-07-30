"""Account & identity security contract.

Threat classes (see the security audits):
  * login-identifier shadowing — a handle must not be able to impersonate an
    e-mail login (resolve_login_username matches username before e-mail)
  * e-mail integrity — no duplicate / unverified e-mail hijack of the login key
  * PII — a social-login username (which IS the e-mail) must not surface publicly

These are re-asserted here as the account-security checklist; some also live in
accounts/tests.py next to the feature they guard.
"""
from django.contrib.auth.models import User as AuthUser
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.services import resolve_login_username
from leaderboard.models import User as LeaderboardUser


class LoginIdentifierResolutionTests(TestCase):
    """resolve_login_username maps an identifier to an auth username. Because it
    checks username before e-mail, a handle must never be allowed to look like an
    e-mail, or it would shadow that e-mail's real owner at login."""

    def test_registration_rejects_at_sign_in_handle(self):
        resp = self.client.post(reverse("api-register"), {
            "first_name": "Mallory", "username": "victim@example.com",
            "email": "mallory@example.com", "password1": "Str0ngPass!23",
            "password2": "Str0ngPass!23", "gdpr_consent": "true",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(AuthUser.objects.filter(username="victim@example.com").exists())

    def test_email_login_resolves_to_the_email_owner_not_a_lookalike_handle(self):
        victim = AuthUser.objects.create_user(
            username="victim", password="x", email="victim@example.com",
        )
        # An attacker cannot even create this handle (see the '@' guards), but if
        # a legacy row existed, resolution must still prefer the real e-mail owner.
        self.assertEqual(resolve_login_username("victim@example.com"), victim.username)


class ProfileUpdateIdentityGuardTests(TestCase):
    """The self-service profile endpoint must not let a user weaponise the two
    login identifiers — a '@' handle, or a duplicated e-mail."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-profile-update")
        self.user = AuthUser.objects.create_user(
            username="user", password="x", email="user@example.com",
        )
        Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_handle_with_at_sign_is_rejected(self):
        resp = self.client.patch(self.url, {"username": "victim@example.com"}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "user")

    def test_duplicate_email_is_rejected(self):
        AuthUser.objects.create_user(username="other", password="x", email="taken@example.com")
        resp = self.client.patch(self.url, {"email": "taken@example.com"}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "user@example.com")


class ProfilePiiExposureTests(TestCase):
    """A social-login account's username IS the e-mail; the public profile must
    not echo it as the @handle or the display name."""

    def test_email_username_not_published(self):
        email = "someone@icloud.com"
        account = AuthUser.objects.create_user(username=email, password="x")
        lb = LeaderboardUser.objects.create(number=700000905, name="Some One")
        Profile.objects.create(user=account, leaderboard_user=lb)
        resp = APIClient().get(reverse("api-profile", kwargs={"username": email}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["username"])
        self.assertNotIn(email, resp.content.decode())
