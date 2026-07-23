import tempfile
from datetime import date, datetime

from django.conf import settings
from django.contrib.auth.models import User as AuthUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, Season, User as LeaderboardUser, UserToEvent
from leaderboard.tests.helpers import make_image_upload


class ProfileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lb_user = LeaderboardUser.objects.create(number=700000005, name="Pat")
        self.auth = AuthUser.objects.create_user(username="pat", password="x", first_name="Pat")
        Profile.objects.create(user=self.auth, leaderboard_user=self.lb_user)
        self.season = Season.objects.create(
            name="2025/26", start_date=date(2025, 9, 1), end_date=date(2026, 6, 30),
            is_active=True,
        )
        self.in_ev = Event.objects.create(
            sheet_id="pin", sheet_list_id="x", name="In", place="Brno", points=40,
            date=timezone.make_aware(datetime(2025, 10, 1, 12, 0)),
        )
        UserToEvent.objects.create(user=self.lb_user, event=self.in_ev, points=40)

    def test_core_has_summaries_without_events(self):
        resp = self.client.get(reverse("api-profile", kwargs={"username": "pat"}))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "pat")
        self.assertGreaterEqual(len(data["seasons"]), 1)
        for s in data["seasons"]:
            self.assertIn("id", s)
            self.assertIn("season_pts", s)
            self.assertNotIn("events", s)  # heavy data is lazy-loaded separately

    def test_core_unknown_user_returns_error_shape(self):
        resp = self.client.get(reverse("api-profile", kwargs={"username": "ghost"}))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.json())  # framework 404 normalized to {error}

    def test_season_detail_returns_events(self):
        url = reverse("api-profile-season", kwargs={"username": "pat", "season_id": self.season.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], self.season.id)
        self.assertEqual(data["season_pts"], 40)
        self.assertEqual([e["name"] for e in data["events"]], ["In"])

    def test_season_detail_unknown_season_404(self):
        url = reverse("api-profile-season", kwargs={"username": "pat", "season_id": 999999})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_season_detail_unknown_user_404(self):
        url = reverse("api-profile-season", kwargs={"username": "ghost", "season_id": self.season.id})
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfilePhotoUploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-profile-photo")
        self.user = AuthUser.objects.create_user(username="avatar", password="x")
        Profile.objects.create(user=self.user)

    def _img(self):
        return make_image_upload("a.png")

    def test_requires_auth(self):
        resp = self.client.post(self.url, {"photo": self._img()}, format="multipart")
        self.assertIn(resp.status_code, (401, 403))

    def test_upload_sets_photo(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {"photo": self._img()}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.photo)

    def test_missing_file_returns_400(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_non_image_returns_400(self):
        self.client.force_authenticate(user=self.user)
        bad = SimpleUploadedFile("x.txt", b"nope", content_type="text/plain")
        resp = self.client.post(self.url, {"photo": bad}, format="multipart")
        self.assertEqual(resp.status_code, 400)


class RegisterApiTests(TestCase):
    """POST /api/auth/register/ — account creation (no phone, starts unlinked)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-register")
        self.payload = {
            "username": "novacek",
            "first_name": "Nova",
            "email": "novacek@example.com",
            "password1": "bezpecneheslo1",
            "password2": "bezpecneheslo1",
            # Required since the privacy policy shipped; see GdprConsentTests
            # for the cases that assert it cannot be omitted.
            "gdpr_consent": True,
        }

    def test_register_creates_user_and_logs_in(self):
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["user"]["username"], "novacek")
        # Session cookie should already be authenticated (auto-login).
        me = self.client.get(reverse("api-me"))
        self.assertEqual(me.json()["user"]["username"], "novacek")

    def test_new_account_starts_unlinked(self):
        # No phone means no automatic link and no placeholder LeaderboardUser —
        # linking is an admin action (accounts.matching + admin).
        before = LeaderboardUser.objects.count()
        self.client.post(self.url, self.payload, format="json")
        profile = Profile.objects.get(user__username="novacek")
        self.assertIsNone(profile.leaderboard_user)
        self.assertEqual(LeaderboardUser.objects.count(), before)

    def test_possible_link_flagged_when_name_matches_unclaimed_player(self):
        LeaderboardUser.objects.create(number=700000301, name="Nova Nováková")
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertTrue(resp.json()["possible_link"])

    def test_possible_link_false_when_no_similar_player(self):
        LeaderboardUser.objects.create(number=700000302, name="Úplně Jiný")
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertFalse(resp.json()["possible_link"])

    def test_possible_link_ignores_already_claimed_players(self):
        # A namesake whose row is already taken must not be offered again.
        lb = LeaderboardUser.objects.create(number=700000303, name="Nova Nováková")
        taken = AuthUser.objects.create_user(username="drzitel", password="x")
        Profile.objects.create(user=taken, leaderboard_user=lb)
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertFalse(resp.json()["possible_link"])

    def test_duplicate_username_case_insensitive_rejected(self):
        AuthUser.objects.create_user(username="NOVACEK", password="x")
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("username", resp.json()["errors"])

    def test_duplicate_email_rejected(self):
        AuthUser.objects.create_user(username="jiny", password="x", email="novacek@example.com")
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.json()["errors"])

    def test_password_mismatch_rejected(self):
        self.payload["password2"] = "jineheslo"
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password2", resp.json()["errors"])


class GdprConsentTests(TestCase):
    """Registration must record consent, and must refuse without it."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-register")
        self.payload = {
            "username": "souhlas",
            "first_name": "Souhlas",
            "email": "souhlas@example.com",
            "password1": "bezpecneheslo1",
            "password2": "bezpecneheslo1",
            "gdpr_consent": True,
        }

    def test_registration_records_consent(self):
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 201)
        profile = Profile.objects.get(user__username="souhlas")
        self.assertIsNotNone(profile.gdpr_consent_at)
        self.assertEqual(profile.gdpr_consent_version, settings.PRIVACY_POLICY_VERSION)
        self.assertTrue(profile.has_current_gdpr_consent)

    def test_registration_rejected_without_consent(self):
        self.payload["gdpr_consent"] = False
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("gdpr_consent", resp.json()["errors"])
        self.assertFalse(AuthUser.objects.filter(username="souhlas").exists())

    def test_registration_rejected_when_field_missing(self):
        # A client posting straight to the API must not bypass the checkbox.
        del self.payload["gdpr_consent"]
        resp = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("gdpr_consent", resp.json()["errors"])
        self.assertFalse(AuthUser.objects.filter(username="souhlas").exists())

    def test_stale_consent_version_is_not_current(self):
        # A policy change must be detectable, so users can be asked again.
        self.client.post(self.url, self.payload, format="json")
        profile = Profile.objects.get(user__username="souhlas")
        profile.gdpr_consent_version = "2020-01-01"
        profile.save()
        self.assertFalse(profile.has_current_gdpr_consent)
