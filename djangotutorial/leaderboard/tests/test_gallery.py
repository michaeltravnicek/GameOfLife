import tempfile
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, ImageToEvent, PhotoLike, Season, UserPhoto
from leaderboard.tests.helpers import make_image_upload


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
class GalleryLikeStateTests(TestCase):
    """Drawing a heart takes two endpoints, and that split is the point.

    The gallery carries what is true for everyone (`id`, `like_count`) and the
    caller's own likes come from `/photos/liked/`. It used to carry a
    `liked_by_me` flag as well, which made the response vary by viewer while
    still being edge-cacheable — and Cloudflare was in fact caching it, so one
    visitor's likes could be served to the next.

    So the two assertions that matter here are: the gallery has enough to render
    a heart, and it contains nothing that identifies who asked.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api-gallery")
        UserModel = get_user_model()
        self.owner = UserModel.objects.create_user(username="owner", password="x")
        self.other = UserModel.objects.create_user(username="other", password="x")
        now = timezone.now()
        self.event = Event.objects.create(
            sheet_id="lk", sheet_list_id="x", name="Likeable", place="Brno",
            points=10, date=now,
        )
        self.photo = UserPhoto.objects.create(
            auth_user=self.owner, event=self.event,
            image=SimpleUploadedFile("l.png", b"dummy", content_type="image/png"),
        )
        # An official event photo — no id, never likeable.
        self.official = ImageToEvent.objects.create(
            event=self.event,
            image=SimpleUploadedFile("o.png", b"dummy", content_type="image/png"),
        )

    def _photo_of(self, data, user_photo):
        return next(p for p in data["photos"] if p["is_user_photo"] is user_photo)

    def test_user_photo_carries_id_and_zero_count(self):
        row = self._photo_of(self.client.get(self.url).json(), True)
        self.assertEqual(row["id"], self.photo.id)
        self.assertEqual(row["like_count"], 0)

    def test_official_photo_is_not_likeable(self):
        # `None` rather than 0: the client uses it to hide the control entirely,
        # which it could not do if "no likes" and "cannot be liked" looked alike.
        row = self._photo_of(self.client.get(self.url).json(), False)
        self.assertIsNone(row["id"])
        self.assertIsNone(row["like_count"])

    def test_gallery_is_byte_identical_for_everyone(self):
        """The property that makes it safe to cache — asserted, not assumed."""
        PhotoLike.objects.create(photo=self.photo, auth_user=self.other)

        anonymous = self.client.get(self.url).json()
        self.client.force_authenticate(user=self.other)   # the one who liked it
        liker = self.client.get(self.url).json()
        self.client.force_authenticate(user=self.owner)   # someone who didn't
        other = self.client.get(self.url).json()

        self.assertEqual(anonymous, liker)
        self.assertEqual(anonymous, other)
        self.assertNotIn("liked_by_me", str(anonymous))

    def test_like_count_is_everyones(self):
        PhotoLike.objects.create(photo=self.photo, auth_user=self.other)
        row = self._photo_of(self.client.get(self.url).json(), True)
        self.assertEqual(row["like_count"], 1)

    def test_my_likes_come_from_the_personal_endpoint(self):
        PhotoLike.objects.create(photo=self.photo, auth_user=self.other)
        url = reverse("api-photos-liked")

        # Anonymous has no likes to report and no business asking.
        self.assertEqual(self.client.get(url).status_code, 403)

        # The owner hasn't liked it — someone else did.
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.get(url).json()["liked"], [])

        # The person who liked it sees their own like.
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get(url).json()["liked"], [self.photo.id])

    def test_my_likes_are_one_query_however_many_there_are(self):
        # The list is sent whole so paging the gallery needs no further round
        # trips; that is only affordable while it stays a single query.
        for i in range(5):
            photo = UserPhoto.objects.create(
                auth_user=self.owner, event=self.event,
                image=SimpleUploadedFile(f"q{i}.png", b"dummy", content_type="image/png"),
            )
            PhotoLike.objects.create(photo=photo, auth_user=self.other)
        self.client.force_authenticate(user=self.other)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(reverse("api-photos-liked"))
        self.assertEqual(len(resp.json()["liked"]), 5)
        # Session + user lookup ride along; the point is that the like list
        # itself does not scale with the number of likes.
        self.assertLessEqual(len(ctx), 3, "liked-photo lookup is not a single query")

    def test_like_state_costs_the_same_whatever_the_page_size(self):
        # `like_count` is annotated in the same query as the photos. If this
        # regresses, a 60-photo page quietly becomes 60 extra COUNT(*)s and only
        # ever shows up as "the gallery got slow".
        for i in range(9):
            UserPhoto.objects.create(
                auth_user=self.owner, event=self.event,
                image=SimpleUploadedFile(f"n{i}.png", b"dummy", content_type="image/png"),
            )
        self.client.force_authenticate(user=self.owner)

        two = self._query_count(limit=2)
        ten = self._query_count(limit=10)
        self.assertEqual(two, ten, "gallery query count grows with the page size")

    def _query_count(self, *, limit):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(self.url, {"limit": limit, "offset": 0})
        self.assertEqual(resp.status_code, 200)
        return len(ctx)


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
        return make_image_upload(name)

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
