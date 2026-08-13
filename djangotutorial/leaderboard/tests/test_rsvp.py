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
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_put_creates_rsvp(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json(), {"rsvp": True, "rsvp_count": 1})
        self.assertTrue(EventRSVP.objects.filter(auth_user=self.user, event=self.event).exists())

    def test_put_is_idempotent(self):
        # A retried PUT (mobile timeout) must confirm the RSVP, not invert it.
        EventRSVP.objects.create(auth_user=self.user, event=self.event)
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"rsvp": True, "rsvp_count": 1})
        self.assertEqual(EventRSVP.objects.filter(auth_user=self.user, event=self.event).count(), 1)

    def test_delete_removes_rsvp(self):
        EventRSVP.objects.create(auth_user=self.user, event=self.event)
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"rsvp": False, "rsvp_count": 0})
        self.assertFalse(EventRSVP.objects.filter(auth_user=self.user, event=self.event).exists())

    def test_delete_is_idempotent(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"rsvp": False, "rsvp_count": 0})

    def test_full_event_rejects_new_rsvp(self):
        self.event.capacity = 1
        self.event.save()
        other = get_user_model().objects.create_user(username="taken_spot", password="x")
        EventRSVP.objects.create(auth_user=other, event=self.event)

        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("obsazena", resp.json()["error"])

    def test_full_event_put_confirms_existing_rsvp(self):
        # The holder of the last spot re-PUTs: 200, still attending.
        self.event.capacity = 1
        self.event.save()
        EventRSVP.objects.create(auth_user=self.user, event=self.event)

        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rsvp"], True)

    def test_full_event_still_allows_delete(self):
        self.event.capacity = 1
        self.event.save()
        EventRSVP.objects.create(auth_user=self.user, event=self.event)

        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rsvp"], False)

    def test_unknown_slug_returns_404(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(reverse("api-event-rsvp", kwargs={"slug": "neexistuje"}))
        self.assertEqual(resp.status_code, 404)

    def _past_event(self):
        return Event.objects.create(
            sheet_id="past", sheet_list_id="x",
            name="Past Event", place="Brno", points=10,
            date=timezone.now() - timedelta(days=7),
        )

    def test_past_event_refuses_new_rsvp(self):
        # The frontend has always hidden the button on is_past; the endpoint
        # used to accept it anyway, and the public "X účastníků" on a finished
        # event is built from this count.
        past = self._past_event()
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(reverse("api-event-rsvp", kwargs={"slug": past.slug}))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(EventRSVP.objects.filter(event=past).exists())

    def test_past_event_still_allows_leaving(self):
        # Joined while it was upcoming, wants out afterwards. Removing an RSVP
        # can only make the public count more accurate.
        past = self._past_event()
        EventRSVP.objects.create(auth_user=self.user, event=past)
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(reverse("api-event-rsvp", kwargs={"slug": past.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EventRSVP.objects.filter(event=past).exists())

    def test_event_without_a_date_can_still_be_joined(self):
        # `date` is nullable (an event announced before its time is fixed).
        # No date means nothing to compare against, so it is not "past".
        undated = Event.objects.create(
            sheet_id="tbd", sheet_list_id="x",
            name="Kdysi", place="Brno", points=10, date=None,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(reverse("api-event-rsvp", kwargs={"slug": undated.slug}))
        self.assertEqual(resp.status_code, 201)
