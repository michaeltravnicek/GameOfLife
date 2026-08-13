"""Creating the event form's lookup options inline: categories and badges.

Both used to be admin-only Django-admin work, which meant abandoning a
half-filled event form to go make one. These are the endpoints the form's
"+ Nová kategorie" / "+ Nový odznak" panels post to.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from rest_framework.test import APITestCase

from accounts.models import Profile
from leaderboard.cache_config import CACHE_KEY_CATEGORIES
from leaderboard.models import Badge, Category

from .helpers import make_image_upload


def _make_user(username, role=None):
    user = get_user_model().objects.create_user(username=username, password="x")
    Profile.objects.create(user=user, **({"role": role} if role else {}))
    return user


class CategoryCreateTests(APITestCase):
    url = None

    def setUp(self):
        cache.clear()
        self.url = reverse("api-category-create")
        self.admin = _make_user("adm", Profile.ROLE_ADMIN)

    def test_admin_creates_a_category(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"name": "Sport"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["name"], "Sport")
        # The id comes back so the form can select it without re-fetching.
        self.assertEqual(resp.json()["id"], Category.objects.get(name="Sport").id)

    def test_name_is_trimmed_and_blank_is_rejected(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.post(self.url, {"name": "  Kolo  "}, format="json").status_code, 201)
        self.assertTrue(Category.objects.filter(name="Kolo").exists())
        self.assertEqual(self.client.post(self.url, {"name": "   "}, format="json").status_code, 400)

    def test_duplicate_name_is_a_400_regardless_of_case(self):
        Category.objects.create(name="Sport")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"name": "sport"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Category.objects.filter(name__iexact="sport").count(), 1)

    def test_new_category_shows_up_in_the_list_immediately(self):
        # The list is cached for an hour; without invalidation the category the
        # author just added would be missing from the very picker they added it for.
        self.client.get(reverse("api-categories"))
        self.assertIsNotNone(cache.get(CACHE_KEY_CATEGORIES))
        self.client.force_authenticate(user=self.admin)
        self.client.post(self.url, {"name": "Sport"}, format="json")
        names = [c["name"] for c in self.client.get(reverse("api-categories")).json()["categories"]]
        self.assertIn("Sport", names)

    def test_non_admin_and_anonymous_are_refused(self):
        resp = self.client.post(self.url, {"name": "Sport"}, format="json")
        self.assertIn(resp.status_code, (401, 403))
        self.client.force_authenticate(user=_make_user("plain"))
        self.assertEqual(self.client.post(self.url, {"name": "Sport"}, format="json").status_code, 403)
        self.assertFalse(Category.objects.filter(name="Sport").exists())


class BadgeCreateTests(APITestCase):
    def setUp(self):
        self.url = reverse("api-badge-create")
        self.admin = _make_user("adm", Profile.ROLE_ADMIN)

    def test_admin_creates_a_badge_with_artwork(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {
            "name": "Karaoke King",
            "image": make_image_upload("badge.png"),
            "image_scale": "1.4",
            "description": "Za odzpívání.",
        }, format="multipart")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["name"], "Karaoke King")
        self.assertEqual(body["image_scale"], 1.4)
        # The picker renders straight from the response, so it needs the URL.
        self.assertTrue(body["image"])
        self.assertTrue(Badge.objects.get(id=body["id"]).slug)

    def test_badge_without_artwork_is_allowed(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"name": "Bez obrázku"}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.json()["image"])

    def test_out_of_range_scale_is_rejected(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, {"name": "Moc velký", "image_scale": "9"}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Badge.objects.filter(name="Moc velký").exists())

    def test_non_admin_and_anonymous_are_refused(self):
        resp = self.client.post(self.url, {"name": "Karaoke"}, format="multipart")
        self.assertIn(resp.status_code, (401, 403))
        self.client.force_authenticate(user=_make_user("plain"))
        self.assertEqual(self.client.post(self.url, {"name": "Karaoke"}, format="multipart").status_code, 403)
        self.assertFalse(Badge.objects.filter(name="Karaoke").exists())
