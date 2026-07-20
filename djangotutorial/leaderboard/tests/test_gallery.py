import tempfile
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, PhotoLike, Season, UserPhoto


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoLikeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="liker", password="x")
        self.photo = UserPhoto.objects.create(
            auth_user=self.user,
            image=SimpleUploadedFile("p.png", b"dummy", content_type="image/png"),
        )
        self.url = reverse("api-photo-like", kwargs={"photo_id": self.photo.id})

    def test_like_then_unlike(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()["liked"])
        self.assertEqual(resp.json()["count"], 1)
        resp2 = self.client.delete(self.url)
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["liked"])
        self.assertEqual(resp2.json()["count"], 0)
        self.assertFalse(PhotoLike.objects.filter(photo=self.photo, auth_user=self.user).exists())

    def test_like_is_idempotent(self):
        # A retried PUT (mobile timeout) must confirm the like, not invert it.
        self.client.force_authenticate(user=self.user)
        self.client.put(self.url)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["liked"])
        self.assertEqual(resp.json()["count"], 1)

    def test_requires_auth(self):
        resp = self.client.put(self.url)
        self.assertIn(resp.status_code, (401, 403))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GalleryPaginationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-gallery")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="shooter", password="x")
        now = timezone.now()
        for i in range(4):
            ev = Event.objects.create(
                sheet_id=f"g{i}", sheet_list_id="x", name=f"E{i}", place="Brno",
                points=10, date=now - timedelta(days=i),
            )
            UserPhoto.objects.create(
                auth_user=self.user, event=ev,
                image=SimpleUploadedFile(f"p{i}.png", b"dummy", content_type="image/png"),
            )

    def test_count_and_first_page(self):
        resp = self.client.get(self.url, {"limit": 2, "offset": 0})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 4)
        self.assertEqual(len(data["photos"]), 2)
        self.assertTrue(data["has_more"])

    def test_last_page_has_no_more(self):
        resp = self.client.get(self.url, {"limit": 2, "offset": 2})
        data = resp.json()
        self.assertEqual(len(data["photos"]), 2)
        self.assertFalse(data["has_more"])

    def test_ordering_newest_first(self):
        resp = self.client.get(self.url, {"limit": 4, "offset": 0})
        names = [p["event_name"] for p in resp.json()["photos"]]
        self.assertEqual(names, ["E0", "E1", "E2", "E3"])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GallerySeasonFilterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-gallery")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="shooter2", password="x")
        self.season = Season.objects.create(
            name="2025/26", start_date=date(2025, 9, 1), end_date=date(2026, 6, 30),
            is_active=True,
        )
        in_ev = Event.objects.create(
            sheet_id="gin", sheet_list_id="x", name="In", place="Brno", points=10,
            date=timezone.make_aware(datetime(2025, 10, 1, 12, 0)),
        )
        out_ev = Event.objects.create(
            sheet_id="gout", sheet_list_id="x", name="Out", place="Brno", points=10,
            date=timezone.make_aware(datetime(2025, 1, 1, 12, 0)),
        )
        for ev in (in_ev, out_ev):
            UserPhoto.objects.create(
                auth_user=self.user, event=ev,
                image=SimpleUploadedFile(f"{ev.sheet_id}.png", b"dummy", content_type="image/png"),
            )

    def test_season_id_filters_to_window(self):
        resp = self.client.get(self.url, {"season_id": self.season.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual([p["event_name"] for p in data["photos"]], ["In"])

    def test_no_season_id_returns_all(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.json()["count"], 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoUploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-photo-upload")
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="uploader", password="x")
        Profile.objects.create(user=self.user, role=Profile.ROLE_PHOTOGRAPHER)
        self.event = Event.objects.create(
            sheet_id="up", sheet_list_id="x", name="E", place="Brno", points=10,
            date=timezone.now() - timedelta(days=1),
        )

    def _img(self, name="p.png"):
        return SimpleUploadedFile(name, b"dummy", content_type="image/png")

    def test_requires_auth(self):
        resp = self.client.post(self.url, {"image": self._img()}, format="multipart")
        self.assertIn(resp.status_code, (401, 403))

    def test_regular_user_forbidden(self):
        plain = get_user_model().objects.create_user(username="plain", password="x")
        self.client.force_authenticate(user=plain)
        resp = self.client.post(self.url, {"image": self._img()}, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_upload_creates_photo(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url,
            {"image": self._img(), "event": self.event.slug, "caption": "ahoj"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["event_slug"], self.event.slug)
        self.assertEqual(resp.json()["caption"], "ahoj")
        self.assertTrue(UserPhoto.objects.filter(auth_user=self.user).exists())

    def test_missing_image_returns_400(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_unknown_event_returns_404(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            self.url, {"image": self._img(), "event": "nope"}, format="multipart"
        )
        self.assertEqual(resp.status_code, 404)

    def test_non_image_returns_400(self):
        self.client.force_authenticate(user=self.user)
        bad = SimpleUploadedFile("x.txt", b"nope", content_type="text/plain")
        resp = self.client.post(self.url, {"image": bad}, format="multipart")
        self.assertEqual(resp.status_code, 400)
