"""Google login: the guards, not the OAuth plumbing.

The redirect dance with Google cannot be exercised without real credentials, and
testing it would mostly test allauth. What is worth pinning down is the handful
of decisions this project makes on top of allauth's defaults — each of which
turns into a full account compromise if it silently regresses.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from allauth.socialaccount.models import SocialAccount, SocialLogin

from accounts.adapters import AccountAdapter, SocialAccountAdapter
from accounts.models import Profile


class SocialLoginSettingsTests(TestCase):
    """These are settings, but they are load-bearing enough to assert."""

    def test_email_authentication_is_off(self):
        # If this is ever True, anyone who can create a Google account with a
        # victim's e-mail address owns the victim's account. No password needed.
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION)

    def test_auto_connect_is_off(self):
        # Same attack, different door: auto-connect would attach the attacker's
        # Google identity to the matching local account on first sign-in.
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT)

    def test_credentials_come_from_the_environment(self):
        # Not from a SocialApp row: a client secret in the database is readable
        # by anyone who reaches the admin.
        app = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]
        self.assertIn("client_id", app)
        self.assertIn("secret", app)

    def test_allauth_backend_is_registered_after_axes(self):
        backends = settings.AUTHENTICATION_BACKENDS
        self.assertIn("allauth.account.auth_backends.AuthenticationBackend", backends)
        self.assertLess(
            backends.index("axes.backends.AxesStandaloneBackend"),
            backends.index("allauth.account.auth_backends.AuthenticationBackend"),
            "axes must stay ahead of allauth or password lockout stops applying.",
        )


class SocialAccountAdapterTests(TestCase):
    def setUp(self):
        self.adapter = SocialAccountAdapter()
        UserModel = get_user_model()
        self.user = UserModel(username="google_gustav", email="g@example.com")

    def _request(self):
        """A request with a real session — allauth stashes state on it."""
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def _save(self, user):
        """Run the adapter's save_user against a prepared SocialLogin."""
        sociallogin = SocialLogin(
            user=user,
            account=SocialAccount(provider="google", uid="1234567890"),
        )
        return self.adapter.save_user(self._request(), sociallogin, form=None)

    def test_social_user_is_never_staff(self):
        # The catastrophic case: is_staff on this path means every Google account
        # on the internet is an admin login.
        self.user.is_staff = True
        self.user.is_superuser = True
        saved = self._save(self.user)
        saved.refresh_from_db()
        self.assertFalse(saved.is_staff)
        self.assertFalse(saved.is_superuser)

    def test_social_user_gets_a_profile(self):
        saved = self._save(self.user)
        self.assertTrue(Profile.objects.filter(user=saved).exists())

    def test_social_user_gets_a_gdpr_consent_record(self):
        # Without this the user is treated as never having agreed to anything,
        # so leaderboard.privacy reduces them to initials with no explanation.
        saved = self._save(self.user)
        profile = Profile.objects.get(user=saved)
        self.assertIsNotNone(profile.gdpr_consent_at)
        self.assertEqual(profile.gdpr_consent_version, settings.PRIVACY_POLICY_VERSION)
        self.assertTrue(profile.has_current_gdpr_consent)

    def test_social_user_gets_a_leaderboard_player(self):
        # Same as the password path: without a player the account cannot check
        # in at all, so it gets one at signup.
        saved = self._save(self.user)
        self.assertIsNotNone(Profile.objects.get(user=saved).leaderboard_user)

    def test_social_user_is_not_linked_to_a_namesake(self):
        # Claiming a player on a *name* must stay an admin merge -- otherwise
        # social signup becomes a way to inherit a namesake's history. Only an
        # exact e-mail match links automatically, and Google verified this one.
        from leaderboard.models import User as LeaderboardUser
        namesake = LeaderboardUser.objects.create(name=self.user.get_full_name())
        saved = self._save(self.user)
        self.assertNotEqual(
            Profile.objects.get(user=saved).leaderboard_user, namesake)

    def test_role_is_not_granted(self):
        saved = self._save(self.user)
        self.assertEqual(Profile.objects.get(user=saved).role, Profile.ROLE_NONE)

    def test_google_signup_is_open(self):
        # Regression: this used to be inherited, and allauth's default delegates
        # to the *account* adapter — which closes signup for the password path.
        # The result was that no new user could ever sign in with Google: they
        # got as far as the callback and were shown allauth's unstyled
        # signup_closed.html. Only pre-existing accounts worked, which is why it
        # looked fine in testing.
        self.assertTrue(self.adapter.is_open_for_signup(self._request(), None))

    def test_google_signup_does_not_follow_the_account_adapter(self):
        # Pins the trap itself rather than the symptom: dropping the override
        # would make this equal AccountAdapter's False again.
        self.assertNotEqual(
            self.adapter.is_open_for_signup(self._request(), None),
            AccountAdapter().is_open_for_signup(None),
        )


class AccountAdapterTests(TestCase):
    def test_allauth_signup_is_closed(self):
        # Registration goes through register_api, which records GDPR consent and
        # enforces the username/e-mail rules. A second signup path would bypass both.
        self.assertFalse(AccountAdapter().is_open_for_signup(None))


class SocialLoginRoutingTests(TestCase):
    def test_google_login_url_is_served_by_django_not_the_spa(self):
        # The catch-all reserves /accounts/, so this must not return the SPA shell.
        resp = self.client.get("/accounts/google/login/", follow=False)
        self.assertNotIn(b'id="root"', resp.content)

    def test_login_route_exists(self):
        self.assertTrue(reverse("google_login").startswith("/accounts/"))
