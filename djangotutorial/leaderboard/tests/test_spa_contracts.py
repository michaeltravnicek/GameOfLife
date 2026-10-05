"""API contracts the SPA depends on.

- A lost session is distinguishable from a forbidden action: both are 403 under
  session auth, so the body carries `code: not_authenticated` for the former only
  (frontend/src/services/api.js redirects to login on it).
- The event edit form clears optional fields by sending them blank: capacity, the
  map pin and the category must all accept "" as "clear" on a partial update.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Category, Event


def _user(username, role=None):
    user = get_user_model().objects.create_user(username=username, password="x")
    if role:
        Profile.objects.create(user=user, role=role)
    return user


class SessionLossErrorCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_url = reverse("api-admin-feedbacks")

    def test_anonymous_on_protected_endpoint_is_flagged(self):
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "not_authenticated")
        self.assertIn("error", resp.json())

    def test_signed_in_without_role_is_plain_permission_denied(self):
        self.client.force_authenticate(user=_user("member"))
        resp = self.client.get(self.admin_url)
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("code", resp.json())
        self.assertIn("error", resp.json())

    def test_not_found_shape_unchanged(self):
        resp = self.client.get(reverse("api-event-detail", kwargs={"slug": "neexistuje"}))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(set(resp.json()), {"error"})


class EventClearFieldsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=_user("adm", Profile.ROLE_ADMIN))
        self.category = Category.objects.create(name="Sport")
        self.event = Event.objects.create(
            name="Akce", place="Brno", points=10,
            date=timezone.now() + timedelta(days=3),
            capacity=20, latitude=49.19, longitude=16.60, category=self.category,
        )

    def _patch(self, data):
        return self.client.patch(
            reverse("api-event-update", kwargs={"slug": self.event.slug}),
            data, format="multipart",
        )

    def test_blank_values_clear_capacity_pin_and_category(self):
        resp = self._patch({
            "name": "Akce", "capacity": "", "latitude": "", "longitude": "", "category": "",
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.capacity)
        self.assertIsNone(self.event.latitude)
        self.assertIsNone(self.event.longitude)
        self.assertIsNone(self.event.category)

    def test_absent_fields_stay_unchanged(self):
        resp = self._patch({"name": "Přejmenovaná"})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.event.refresh_from_db()
        self.assertEqual(self.event.capacity, 20)
        self.assertEqual(self.event.category, self.category)

    def test_create_accepts_blank_optional_fields(self):
        resp = self.client.post(reverse("api-event-create"), {
            "name": "Nová", "place": "Brno", "date": "2030-05-01T18:00", "points": "5",
            "end_date": "", "capacity": "", "latitude": "", "longitude": "",
            "category": "", "badge": "", "checkin_radius": "500",
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.content)
        event = Event.objects.get(name="Nová")
        self.assertIsNone(event.capacity)
        self.assertIsNone(event.latitude)
        self.assertIsNone(event.category)
