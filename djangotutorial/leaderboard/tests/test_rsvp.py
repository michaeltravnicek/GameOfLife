from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from leaderboard.models import Event, EventRSVP


class EventRsvpApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(username="rsvp_tester", password="x")
        self.event = Event.objects.create(
            sheet_id="rsvp", sheet_list_id="x",
            name="Upcoming Event", place="Brno", points=10,
            date=timezone.now() + timedelta(days=7),
        )
        self.url = reverse("api-event-rsvp", kwargs={"slug": self.event.slug})

    def test_unauthenticated_returns_403(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_toggle_on_creates_rsvp(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json(), {"rsvp": True, "rsvp_count": 1})
        self.assertTrue(EventRSVP.objects.filter(auth_user=self.user, event=self.event).exists())

    def test_toggle_off_deletes_rsvp(self):
        EventRSVP.objects.create(auth_user=self.user, event=self.event)
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"rsvp": False, "rsvp_count": 0})
        self.assertFalse(EventRSVP.objects.filter(auth_user=self.user, event=self.event).exists())

    def test_full_event_rejects_new_rsvp(self):
        self.event.capacity = 1
        self.event.save()
        other = get_user_model().objects.create_user(username="taken_spot", password="x")
        EventRSVP.objects.create(auth_user=other, event=self.event)

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("obsazena", resp.json()["error"])

    def test_full_event_still_allows_toggle_off(self):
        self.event.capacity = 1
        self.event.save()
        EventRSVP.objects.create(auth_user=self.user, event=self.event)

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rsvp"], False)

    def test_unknown_slug_returns_404(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(reverse("api-event-rsvp", kwargs={"slug": "neexistuje"}))
        self.assertEqual(resp.status_code, 404)

    def test_past_event_currently_accepts_rsvp(self):
        # Documents current behavior: the API has no date gate, only the
        # frontend hides the button. RSVPing a past event inflates the public
        # participant count — see TESTING_REPORT.md before relying on this.
        past = Event.objects.create(
            sheet_id="past", sheet_list_id="x",
            name="Past Event", place="Brno", points=10,
            date=timezone.now() - timedelta(days=7),
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(reverse("api-event-rsvp", kwargs={"slug": past.slug}))
        self.assertEqual(resp.status_code, 201)
