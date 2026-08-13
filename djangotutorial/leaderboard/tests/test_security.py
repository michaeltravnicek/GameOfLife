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
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, PhotoLike, User as LeaderboardUser, UserPhoto, UserToEvent

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
