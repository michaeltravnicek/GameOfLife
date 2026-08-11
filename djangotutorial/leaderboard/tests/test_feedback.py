from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, EventFeedback
from leaderboard.models import User as LeaderboardUser


class EventFeedbackApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="fb_tester", password="x")
        # Feedback is keyed on the leaderboard user, so the account needs a link.
        self.lb_user = LeaderboardUser.objects.create(name="FB Tester")
        Profile.objects.create(user=self.user, leaderboard_user=self.lb_user)
        self.event = Event.objects.create(
            sheet_id="fb", sheet_list_id="x",
            name="Past Event", place="Brno", points=10,
            date=timezone.now() - timedelta(days=1),
        )
        self.url = reverse("api-event-feedback", kwargs={"slug": self.event.slug})

    def test_unauthenticated_returns_403(self):
        resp = self.client.post(self.url, {"rating": 5}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_creates_feedback_with_comment(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {"rating": 5, "comment": "  Super akce  "}, format="json")
        self.assertEqual(resp.status_code, 201)  # first submission creates
        fb = EventFeedback.objects.get(user=self.lb_user, event=self.event)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comment, "Super akce")  # whitespace stripped

    def test_resubmit_updates_in_place(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.post(self.url, {"rating": 5, "comment": "prvni"}, format="json")
        again = self.client.post(self.url, {"rating": 2, "comment": "po rozmysleni"}, format="json")
        self.assertEqual(first.status_code, 201)   # created
        self.assertEqual(again.status_code, 200)   # updated in place

        rows = EventFeedback.objects.filter(user=self.lb_user, event=self.event)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows[0].rating, 2)
        self.assertEqual(rows[0].comment, "po rozmysleni")

    def test_rating_out_of_range_rejected(self):
        self.client.force_authenticate(user=self.user)
        for bad in (0, 11, -1, "abc", None):
            resp = self.client.post(self.url, {"rating": bad, "comment": ""}, format="json")
            self.assertEqual(resp.status_code, 400, f"rating={bad!r} should be rejected")
        self.assertFalse(EventFeedback.objects.filter(user=self.lb_user).exists())

    def test_missing_comment_defaults_to_empty(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {"rating": 4}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(EventFeedback.objects.get(user=self.lb_user).comment, "")

    def test_unknown_slug_returns_404(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            reverse("api-event-feedback", kwargs={"slug": "neexistuje"}),
            {"rating": 5}, format="json",
        )
        self.assertEqual(resp.status_code, 404)
