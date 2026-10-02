"""Security contract for the API — one place that asserts the invariants a
reviewer cares about, so a regression fails CI loudly.

Each class maps to a threat class from the two security audits (see
security/ and the git history). Some invariants are also covered by the
feature-specific suites (test_privacy_flags, test_auth, test_name_privacy,
test_checkin, test_event_logo); they are re-asserted here on purpose, because a
security guarantee that lives only inside a feature test is easy to delete by
accident when the feature changes.

Threat classes covered here (gaps not owned by another suite):
  * fail-closed default permission
  * role/staff privilege escalation via the self-service profile endpoint
  * object-level authorization (IDOR) on per-user writes
  * admin-only write endpoints rejecting ordinary users
  * public read surfaces never publishing an account e-mail
"""
import os
import subprocess
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, PhotoLike, UserPhoto

from mysite.test_utils import SPA_SHELL, SpaShellMixin

from .helpers import make_profile_for


def _user(username, **kwargs):
    return get_user_model().objects.create_user(username=username, password="x", **kwargs)


class FailClosedDefaultPermissionTests(TestCase):
    """A view that forgets `permission_classes` must be locked, not public."""

    def test_drf_default_is_authenticated(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
            ["rest_framework.permissions.IsAuthenticated"],
            "The DRF default must fail closed — an undecorated endpoint should 403, not leak.",
        )


class PrivilegeEscalationTests(TestCase):
    """The self-service profile update is a strict allowlist: a user cannot grant
    themselves a role or staff/superuser rights through it."""

    def setUp(self):
        self.client = APIClient()
        self.user = _user("climber")
        Profile.objects.create(user=self.user)  # role defaults to ROLE_NONE
        self.client.force_authenticate(user=self.user)

    def test_cannot_self_assign_role(self):
        resp = self.client.patch(
            reverse("api-profile-update"), {"role": Profile.ROLE_ADMIN}, format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.role, Profile.ROLE_NONE)

    def test_cannot_self_assign_staff_or_superuser(self):
        resp = self.client.patch(
            reverse("api-profile-update"),
            {"is_staff": "true", "is_superuser": "true"}, format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)


class ObjectLevelAuthTests(TestCase):
    """IDOR: a write must only ever touch the caller's own row, never another
    user's — even when both act on the same target object."""

    def setUp(self):
        self.now = timezone.now()
        self.event = Event.objects.create(
            sheet_id="s", sheet_list_id="l", name="Akce", place="Brno", points=10,
            date=self.now,
        )
        self.alice = _user("alice")
        self.bob = _user("bob")
        make_profile_for(self.alice)
        make_profile_for(self.bob)
        # A photo Bob liked.
        self.photo = UserPhoto.objects.create(
            auth_user=self.bob, event=self.event, image="user_photos/x.png",
        )
        PhotoLike.objects.create(photo=self.photo, auth_user=self.bob)

    def test_deleting_a_like_cannot_remove_someone_elses(self):
        client = APIClient()
        client.force_authenticate(user=self.alice)
        # Alice DELETEs her (non-existent) like on the same photo.
        resp = client.delete(reverse("api-photo-like", kwargs={"photo_id": self.photo.id}))
        self.assertEqual(resp.status_code, 200)
        # Bob's like must survive — the delete is keyed to request.user.
        self.assertTrue(
            PhotoLike.objects.filter(photo=self.photo, auth_user=self.bob).exists(),
            "Alice's delete removed Bob's like — object-level auth broken.",
        )

    def test_rsvp_delete_is_scoped_to_the_caller(self):
        from leaderboard.models import EventRSVP
        EventRSVP.objects.create(auth_user=self.bob, event=self.event)
        client = APIClient()
        client.force_authenticate(user=self.alice)
        client.delete(reverse("api-event-rsvp", kwargs={"slug": self.event.slug}))
        self.assertTrue(
            EventRSVP.objects.filter(auth_user=self.bob, event=self.event).exists(),
            "Alice's RSVP delete removed Bob's RSVP — object-level auth broken.",
        )


class AdminOnlyEndpointsRejectOrdinaryUsersTests(TestCase):
    """Every mutating admin endpoint must 403 a signed-in user with no role.

    Permission is checked before the view body, so a bare request is enough — a
    missing guard would return 200/201/400, never 403."""

    def setUp(self):
        self.client = APIClient()
        self.user = _user("nobody")
        Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.event = Event.objects.create(
            sheet_id="s", sheet_list_id="l", name="Akce", place="Brno", points=10,
            date=timezone.now(), slug="akce",
        )

    def _assert_forbidden(self, method, name, **kwargs):
        url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
        resp = getattr(self.client, method)(url)
        self.assertEqual(resp.status_code, 403, f"{method.upper()} {name} was not admin-gated")

    def test_admin_write_endpoints_are_forbidden(self):
        self._assert_forbidden("post", "api-event-create")
        self._assert_forbidden("post", "api-badge-create")
        self._assert_forbidden("post", "api-photo-upload")
        self._assert_forbidden("get", "api-admin-feedbacks")
        self._assert_forbidden("get", "api-event-attendees", slug=self.event.slug)
        self._assert_forbidden("get", "api-event-rsvps", slug=self.event.slug)
        self._assert_forbidden("delete", "api-event-delete", slug=self.event.slug)
        self._assert_forbidden("post", "api-event-images", slug=self.event.slug)


class PublicSurfacesHideEmailTests(TestCase):
    """No public read surface may publish an account's e-mail. Social-login
    usernames default to the e-mail, so the guard is `privacy.public_handle`."""

    def setUp(self):
        self.client = APIClient()
        self.email = "gal.author@icloud.com"
        self.author = _user(self.email)  # username IS the e-mail
        self.event = Event.objects.create(
            sheet_id="s", sheet_list_id="l", name="Akce", place="Brno", points=10,
            date=timezone.now(),
        )
        # A gallery photo with no display name to fall back on.
        UserPhoto.objects.create(auth_user=self.author, event=self.event, image="user_photos/x.png")

    def test_gallery_uploaded_by_is_never_an_email(self):
        resp = self.client.get(reverse("api-gallery"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.email, resp.content.decode())


class LoginCsrfTests(TestCase):
    """Login CSRF: DRF's SessionAuthentication checks the CSRF token only once
    a session is already authenticated, so a guest POST to login/register was
    unchecked. A cross-site form could sign the victim's browser into an account
    the attacker controls, after which the victim's check-ins, photos and profile
    edits land in that account."""

    def setUp(self):
        _user("csrf_target")  # password "x"
        # enforce_csrf_checks: the test client otherwise waves every request
        # through, which is exactly the thing under test here.
        self.client = APIClient(enforce_csrf_checks=True)
        self.creds = {"identifier": "csrf_target", "password": "x"}

    def test_login_without_csrf_token_is_refused(self):
        resp = self.client.post(reverse("api-login"), self.creds, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("sessionid", resp.cookies, "a CSRF-less login must not open a session")

    def test_register_without_csrf_token_is_refused(self):
        resp = self.client.post(reverse("api-register"), {
            "first_name": "Eva", "username": "eva_csrf", "email": "eva@example.com",
            "password1": "Str0ngPass!23", "password2": "Str0ngPass!23", "gdpr_consent": "true",
        }, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username="eva_csrf").exists())

    def test_login_with_the_token_the_spa_sends_succeeds(self):
        # The SPA reads the csrftoken cookie and echoes it in X-CSRFToken. The
        # cookie has to come from somewhere before the first POST: /me is the
        # request every page load starts with, so it must set the cookie.
        self.client.get(reverse("api-me"))
        token = self.client.cookies["csrftoken"].value
        resp = self.client.post(reverse("api-login"), self.creds, format="json",
                                HTTP_X_CSRFTOKEN=token)
        self.assertEqual(resp.status_code, 200)


class HiddenEventSignupFormTests(TestCase):
    """Every per-event endpoint goes through visible_event_or_404 so a draft
    stays invisible; the sign-up form pair looked the event up directly and
    handed out a hidden event's survey URL (and confirmed its slug) to any
    signed-in user."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=_user("member"))
        self.event = Event.objects.create(
            sheet_id="h", sheet_list_id="l", name="Tajná akce", place="Brno", points=10,
            date=timezone.now(), visible_to_users=False,
            survey_url="https://docs.google.com/forms/d/e/SECRETFORMID/viewform",
        )

    @override_settings(GOOGLE_FORM_NATIVE=False)
    def test_hidden_event_form_link_is_404_for_ordinary_users(self):
        resp = self.client.get(reverse("api-event-signup-form", kwargs={"slug": self.event.slug}))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("SECRETFORMID", resp.content.decode())

    @override_settings(GOOGLE_FORM_NATIVE=False)
    def test_hidden_event_form_submit_is_404_for_ordinary_users(self):
        resp = self.client.post(
            reverse("api-event-signup-form-submit", kwargs={"slug": self.event.slug}), {})
        self.assertEqual(resp.status_code, 404)


class EmailShapedProfileLookupTests(SpaShellMixin, TestCase):
    """Google accounts carry the e-mail address as their username. The profile
    routes are keyed on the username, so looking one up by an address answered
    200 for a registered e-mail and 404 for anything else -- an enumeration
    oracle that undoes the deliberately generic login / password-reset replies.
    public_handle never publishes such usernames, so nothing links here except
    the owner's own "my profile" navigation, which must keep working."""

    def setUp(self):
        super().setUp()
        self.email = "someone@gmail.com"
        self.owner = _user(self.email)  # username IS the e-mail, as with Google login
        Profile.objects.create(user=self.owner)
        self.unknown = "nobody-here@gmail.com"

    def _api_status(self, username, as_user=None):
        client = APIClient()
        if as_user is not None:
            client.force_authenticate(user=as_user)
        return client.get(reverse("api-profile", kwargs={"username": username})).status_code

    def test_anonymous_lookup_answers_alike_for_known_and_unknown_addresses(self):
        self.assertEqual(self._api_status(self.email), 404)
        self.assertEqual(self._api_status(self.email), self._api_status(self.unknown))

    def test_signed_in_strangers_get_no_oracle_either(self):
        stranger = _user("stranger")
        self.assertEqual(self._api_status(self.email, as_user=stranger), 404)

    def test_owner_still_opens_their_own_profile(self):
        self.assertEqual(self._api_status(self.email, as_user=self.owner), 200)

    def test_admin_still_opens_it(self):
        admin = _user("admin_ada")
        Profile.objects.create(user=admin, role=Profile.ROLE_ADMIN)
        self.assertEqual(self._api_status(self.email, as_user=admin), 200)

    def test_season_sub_resource_is_gated_the_same_way(self):
        from leaderboard.models import Season
        season = Season.objects.create(
            name="2026", start_date="2026-01-01", end_date="2026-12-31", is_active=True)
        url = reverse("api-profile-season",
                      kwargs={"username": self.email, "season_id": season.id})
        self.assertEqual(APIClient().get(url).status_code, 404)

    def test_spa_shell_status_does_not_reveal_the_account(self):
        # The OG resolver behind react_index answers 404 for a username nobody
        # owns; for an e-mail-shaped one it must not differ between known and
        # unknown, or the HTML route is the oracle instead of the API.
        known = self.client.get(f"/profil/{self.email}").status_code
        unknown = self.client.get(f"/profil/{self.unknown}").status_code
        self.assertEqual(known, unknown)
        self.assertNotIn(self.email.split("@")[0], self.client.get(f"/profil/{self.email}")
                         .content.decode().split("<title>")[1].split("</title>")[0])


class OgInjectRobustnessTests(TestCase):
    """The rendered tags are the replacement string of a regex substitution, and
    a player can put backslashes in their own name. `\\1` there raised
    re.error, which the view swallows into "serve the shell with no tags at
    all" -- so one oddly named player silently had no link preview."""

    def test_backslashes_in_a_name_do_not_break_tag_injection(self):
        from mysite import og
        title = r"Jan \1 Novák"
        meta = og.PageMeta(title=title, description="x", url="https://example.com/x")
        html = og.inject(SPA_SHELL, meta)
        self.assertIn(f"<title>{title}</title>", html)
        self.assertEqual(html.count("<title>"), 1)


class ProxyChainAgreementTests(TestCase):
    """DRF's throttles and django-axes resolve the client IP through different
    libraries with different conventions. Both are fed from PROXY_COUNT, and the
    translation for axes has to be right: if ipware rejects X-Forwarded-For it
    falls back to REMOTE_ADDR (the load balancer), every visitor shares one
    lockout key, and eight bad passwords from anywhere lock any account for
    everyone."""

    # Cloudflare -> Render: the header the origin actually sees.
    XFF = "203.0.113.7, 172.68.1.1"
    HOPS = 2

    def _request(self, **extra):
        return RequestFactory().get(
            "/", HTTP_X_FORWARDED_FOR=self.XFF, REMOTE_ADDR="10.0.0.9", **extra)

    def test_axes_and_drf_agree_on_the_client_ip(self):
        from axes.helpers import get_client_ip_address
        from rest_framework.throttling import BaseThrottle
        from mysite.settings import _axes_ipware_proxy_count

        with override_settings(
            AXES_IPWARE_PROXY_COUNT=_axes_ipware_proxy_count(self.HOPS),
            AXES_IPWARE_META_PRECEDENCE_ORDER=["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"],
            REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": self.HOPS},
        ):
            axes_ip = get_client_ip_address(self._request())
            drf_ip = BaseThrottle().get_ident(self._request())
        self.assertEqual(drf_ip, "203.0.113.7")
        self.assertEqual(axes_ip, drf_ip, "axes keys the lockout on a different address than DRF")

    def test_whoami_reports_the_axes_view_as_well(self):
        # Operators verify PROXY_COUNT at /whoami/; it has to show what axes
        # computes too, or a wrong lockout key stays invisible.
        superuser = get_user_model().objects.create_superuser("root", "r@x.cz", "pw-12345")
        self.client.force_login(superuser)
        resp = self.client.get("/whoami/", HTTP_X_FORWARDED_FOR=self.XFF, REMOTE_ADDR="10.0.0.9")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("axes_client_ip", resp.json())

    def test_whoami_survives_a_non_ascii_origin_header(self):
        # The header is attacker-supplied; a byte outside ASCII must be a
        # mismatch, not a 500 (hmac.compare_digest refuses non-ASCII str).
        superuser = get_user_model().objects.create_superuser("root2", "r2@x.cz", "pw-12345")
        self.client.force_login(superuser)
        # Load the middleware chain while the origin lock is still inert: it
        # reads the secret once, in __init__, and the point here is the view's
        # own comparison, not the middleware's (test_origin_lock covers that).
        self.assertEqual(self.client.get("/whoami/").status_code, 200)
        with override_settings(ORIGIN_SHARED_SECRET="s3cret"):
            resp = self.client.get("/whoami/", HTTP_X_ORIGIN_VERIFY="tajn\xe9")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["origin_verify"], "MISMATCH")


class ProductionCsrfOriginsTests(SimpleTestCase):
    """Settings are module-level, so the production branch is checked by
    importing them in a subprocess with a production environment."""

    def test_loopback_origins_are_not_trusted_on_an_https_deployment(self):
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "mysite.settings",
            "MODE": "PRODUCTION", "HTTPS": "1",
            "DJANGO_SECRET_KEY": "k" * 64,
            "ALLOWED_HOSTS": "www.gameofyolo.com",
            "ADMIN_URL": "sprava-test/",
            "CSRF_TRUSTED_ORIGIN": "https://www.gameofyolo.com",
            "DATABASE_URL": "sqlite://:memory:",
            "SENTRY_DSN": "",
        }
        out = subprocess.run(
            [sys.executable, "-c",
             "from django.conf import settings; print('\\n'.join(settings.CSRF_TRUSTED_ORIGINS))"],
            cwd=str(settings.BASE_DIR), env=env, capture_output=True, text=True, check=True,
        ).stdout
        origins = out.strip().splitlines()
        self.assertIn("https://www.gameofyolo.com", origins)
        loopback = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
        self.assertEqual(loopback, [], "a page on the visitor's own machine must not be a trusted origin")
