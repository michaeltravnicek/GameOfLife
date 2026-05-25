import tempfile
from datetime import date, datetime

from django.contrib.auth.models import User as AuthUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, Season, User as LeaderboardUser, UserToEvent


class ProfileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lb_user = LeaderboardUser.objects.create(number=5, name="Pat")
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
        return SimpleUploadedFile("a.png", b"dummy", content_type="image/png")

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
