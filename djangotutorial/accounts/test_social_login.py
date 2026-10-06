"""Google login: the guards, not the OAuth plumbing.

The redirect dance with Google cannot be exercised without real credentials, and
testing it would mostly test allauth. What is worth pinning down is the handful
of decisions this project makes on top of allauth's defaults — each of which
turns into a full account compromise if it silently regresses.
"""
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.providers.oauth2.client import OAuth2Error

from accounts.adapters import AccountAdapter, SocialAccountAdapter
from accounts.models import Profile
from mysite.test_utils import SpaShellMixin


class SocialLoginSettingsTests(TestCase):
    """These are settings, but they are load-bearing enough to assert."""

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


class GoogleEmailMatchingTests(TestCase):
    """A Google sign-in on an address that already has a password account.

    Runs allauth's real completion step from the point where Google has handed
    over the profile, so the callback itself is the only part not exercised.
    """

    def setUp(self):
        self.member = get_user_model().objects.create_user(
            username="jana", email="jana@example.com", password="heslo-123-abc")
        Profile.objects.create(user=self.member)

    def _complete(self, email, verified=True):
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        with context.request_context(request):
            provider = get_social_adapter().get_provider(request, "google")
            # The userinfo shape Google returns; the provider turns it into
            # the SocialLogin exactly as the callback does.
            sociallogin = provider.sociallogin_from_response(request, {
                "sub": "google-uid-1", "email": email,
                "email_verified": verified, "name": "Jana Nová",
            })
            sociallogin.state = {"process": "login"}
            response = complete_social_login(request, sociallogin)
        return request, response

    def test_logs_in_to_the_existing_account(self):
        # Regression: with e-mail matching off, allauth could neither log in nor
        # sign up on a taken address and stranded the member on its signup form.
        request, response = self._complete("Jana@Example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(request.user, self.member)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_links_the_google_identity(self):
        # So the next sign-in finds the account by its Google uid, not by e-mail.
        self._complete("jana@example.com")
        self.assertTrue(SocialAccount.objects.filter(
            user=self.member, provider="google", uid="google-uid-1").exists())

    def test_unverified_password_is_made_unusable(self):
        # allauth's guard against an account registered on someone else's
        # address in advance: whoever chose that password is locked out. No
        # address is verified on this site, so every member is in this case.
        self._complete("jana@example.com")
        self.member.refresh_from_db()
        self.assertFalse(self.member.has_usable_password())

    def test_address_google_did_not_verify_does_not_match(self):
        # The match rests on Google's verified flag; without it this would be a
        # takeover by anyone who types the victim's address into a Google account.
        request, response = self._complete("jana@example.com", verified=False)
        self.assertNotEqual(request.user, self.member)
        self.assertFalse(SocialAccount.objects.filter(user=self.member).exists())
        self.assertEqual(response["Location"], "/accounts/3rdparty/signup/")


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

    def test_authentication_error_is_logged(self):
        # allauth's hook is a no-op, so without the override the only flow that
        # cannot be tested end-to-end is also the only one leaving no trace.
        # The reason has to reach the log (and through it Sentry), not just the
        # generic error page the visitor sees.
        provider = SimpleNamespace(id="google")
        with self.assertLogs("accounts.adapters", level="ERROR") as captured:
            self.adapter.on_authentication_error(
                self._request(), provider,
                error="invalid_client",
                exception=OAuth2Error("unauthorized_client"),
            )
        logged = "\n".join(captured.output)
        self.assertIn("google", logged)
        self.assertIn("invalid_client", logged)
        self.assertIn("unauthorized_client", logged)


class AccountAdapterTests(TestCase):
    def test_allauth_signup_is_closed(self):
        # Registration goes through register_api, which records GDPR consent and
        # enforces the username/e-mail rules. A second signup path would bypass both.
        self.assertFalse(AccountAdapter().is_open_for_signup(None))


class SocialLoginRoutingTests(SpaShellMixin, TestCase):
    def test_google_login_url_is_served_by_django_not_the_spa(self):
        # The catch-all reserves /accounts/, so this must not return the SPA
        # shell. SpaShellMixin is what gives that assertion teeth: without a
        # shell to serve, every page route 404s and the assertion passes no
        # matter how the catch-all behaves.
        resp = self.client.get("/accounts/google/login/", follow=False)
        self.assertNotIn(b'id="root"', resp.content)

    def test_login_route_exists(self):
        self.assertTrue(reverse("google_login").startswith("/accounts/"))

    def test_social_signup_form_returns_to_login(self):
        # allauth's own form is unstyled and creates accounts outside
        # register_api; the visitor goes back to the login page instead.
        resp = self.client.get("/accounts/3rdparty/signup/")
        self.assertRedirects(resp, "/prihlasit?google=nedokonceno",
                             fetch_redirect_response=False)
