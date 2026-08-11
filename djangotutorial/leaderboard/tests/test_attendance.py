from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, EventRSVP, User as LeaderboardUser, UserToEvent


class AttendanceAdminApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        UserModel = get_user_model()

        # Admin caller.
        self.admin_user = UserModel.objects.create_user(username="boss", password="x")
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        # A plain (non-admin) user for permission checks.
        self.plain = UserModel.objects.create_user(username="plain", password="x")

        self.event = Event.objects.create(
            sheet_id="a", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=timezone.now() - timedelta(days=1),
        )
        # Two leaderboard players; one attended.
        self.lb1 = LeaderboardUser.objects.create(name="Alice")
        self.lb2 = LeaderboardUser.objects.create(name="Bob")
        UserToEvent.objects.create(user=self.lb1, event=self.event, points=10)

    # --- attendee_count on the public detail ---

    def test_detail_exposes_attendee_count(self):
        resp = self.client.get(reverse("api-event-detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["attendee_count"], 1)

    # --- GET attendees (admin) ---

    def test_attendees_list_requires_admin(self):
        url = reverse("api-event-attendees", kwargs={"slug": self.event.slug})
        self.assertEqual(self.client.get(url).status_code, 403)  # anon
        self.client.force_authenticate(user=self.plain)
        self.assertEqual(self.client.get(url).status_code, 403)  # non-admin

    def test_attendees_list_returns_points(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendees", kwargs={"slug": self.event.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["attendees"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_id"], self.lb1.id)
        self.assertEqual(rows[0]["points"], 10)

    # --- PUT attendee (add / change points) ---

    def test_put_adds_attendance(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb2.id})
        resp = self.client.put(url, {"points": 7}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["points"], 7)
        self.assertTrue(UserToEvent.objects.filter(user=self.lb2, event=self.event).exists())

    def test_put_updates_existing_points(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb1.id})
        resp = self.client.put(url, {"points": 25}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(UserToEvent.objects.get(user=self.lb1, event=self.event).points, 25)

    def test_put_negative_points_rejected(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb2.id})
        self.assertEqual(self.client.put(url, {"points": -1}, format="json").status_code, 400)

    def test_put_unknown_leaderboard_user_404(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": 99999})
        self.assertEqual(self.client.put(url, {"points": 5}, format="json").status_code, 404)

    def test_put_requires_admin(self):
        self.client.force_authenticate(user=self.plain)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb2.id})
        self.assertEqual(self.client.put(url, {"points": 5}, format="json").status_code, 403)

    # --- DELETE attendee ---

    def test_delete_removes_attendance(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb1.id})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(UserToEvent.objects.filter(user=self.lb1, event=self.event).exists())

    def test_delete_is_idempotent(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-attendee",
                      kwargs={"slug": self.event.slug, "user_id": self.lb2.id})
        self.assertEqual(self.client.delete(url).status_code, 200)  # never attended

    # --- GET rsvps (admin) ---

    def test_rsvps_list(self):
        EventRSVP.objects.create(auth_user=self.plain, event=self.event)
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("api-event-rsvps", kwargs={"slug": self.event.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["rsvps"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "plain")

    def test_rsvps_requires_admin(self):
        url = reverse("api-event-rsvps", kwargs={"slug": self.event.slug})
        self.client.force_authenticate(user=self.plain)
        self.assertEqual(self.client.get(url).status_code, 403)
