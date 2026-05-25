import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import (
    Event,
    EventFeedback,
    ImageToEvent,
    User as LeaderboardUser,
    UserToEvent,
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EventImagesUploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.event = Event.objects.create(
            sheet_id="img", sheet_list_id="x", name="E", place="Brno", points=10,
            date=timezone.now(),
        )
        self.url = reverse("api-event-images", kwargs={"slug": self.event.slug})
        UserModel = get_user_model()
        self.photographer = UserModel.objects.create_user(username="ph", password="x")
        Profile.objects.create(user=self.photographer, role=Profile.ROLE_PHOTOGRAPHER)
        self.plain = UserModel.objects.create_user(username="plain", password="x")

    def _img(self, name="o.png"):
        return SimpleUploadedFile(name, b"dummy", content_type="image/png")

    def test_photographer_can_upload_multiple(self):
        self.client.force_authenticate(user=self.photographer)
        resp = self.client.post(
            self.url, {"images": [self._img(), self._img("b.png")]}, format="multipart"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["count"], 2)
        self.assertEqual(ImageToEvent.objects.filter(event_id=self.event).count(), 2)

    def test_regular_user_forbidden(self):
        self.client.force_authenticate(user=self.plain)
        resp = self.client.post(self.url, {"image": self._img()}, format="multipart")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_forbidden(self):
        resp = self.client.post(self.url, {"image": self._img()}, format="multipart")
        self.assertIn(resp.status_code, (401, 403))

    def test_missing_files_returns_400(self):
        self.client.force_authenticate(user=self.photographer)
        resp = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(resp.status_code, 400)


class AdminFeedbacksApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-admin-feedbacks")
        UserModel = get_user_model()
        self.admin = UserModel.objects.create_user(username="adm", password="x")
        Profile.objects.create(user=self.admin, role=Profile.ROLE_ADMIN)

        self.attendee = UserModel.objects.create_user(
            username="att", password="x", first_name="Jana", last_name="Nováková",
        )
        lb = LeaderboardUser.objects.create(number=11, name="Jana")
        Profile.objects.create(user=self.attendee, leaderboard_user=lb)

        self.event = Event.objects.create(
            sheet_id="f", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=timezone.now(),
        )
        other = Event.objects.create(
            sheet_id="f2", sheet_list_id="x", name="Akce2", place="Brno", points=10,
            date=timezone.now(),
        )
        UserToEvent.objects.create(user=lb, event=self.event, points=10)
        UserToEvent.objects.create(user=lb, event=other, points=10)
        EventFeedback.objects.create(
            auth_user=self.attendee, event=self.event, rating=5, comment="super",
        )

    def test_admin_gets_feedback_overview(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        feedbacks = resp.json()["feedbacks"]
        self.assertEqual(len(feedbacks), 1)
        entry = feedbacks[0]
        self.assertEqual(entry["rating"], 5)
        self.assertEqual(entry["user"]["name"], "Jana Nováková")
        self.assertEqual(entry["user"]["attended_events"], 2)
        self.assertEqual(entry["event"]["slug"], self.event.slug)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.attendee)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_forbidden(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
