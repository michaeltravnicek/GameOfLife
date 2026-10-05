"""Hidden content: what a viewer who may not see it can still do or learn.

Two surfaces the visibility gates have to agree on: leaving an event an admin
has since hidden (the member's own RSVP must still be removable), and the SPA
shell's status code, which must not confirm what the API's 404 hides.
"""
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, EventRSVP, User as LeaderboardUser

_SHELL = (
    "<!doctype html>\n<html lang=\"cs\">\n  <head>\n"
    "    <title>Game of Life</title>\n"
    "  </head>\n  <body><div id=\"root\"></div></body>\n</html>\n"
)


def _event(**overrides):
    fields = {
        "sheet_id": "hca", "sheet_list_id": "x",
        "name": "Tajná akce", "place": "Brno", "points": 10,
        "date": timezone.now() + timedelta(days=7),
    }
    fields.update(overrides)
    return Event.objects.create(**fields)


class RsvpOnHiddenEventTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.member = UserModel.objects.create_user(username="clen", password="x")
        self.other = UserModel.objects.create_user(username="cizi", password="x")
        self.event = _event()
        self.url = reverse("api-event-rsvp", kwargs={"slug": self.event.slug})
        self.client = APIClient()

    def _hide(self):
        Event.objects.filter(pk=self.event.pk).update(visible_to_users=False)

    def test_member_can_leave_after_the_event_is_hidden(self):
        EventRSVP.objects.create(auth_user=self.member, event=self.event)
        self._hide()
        self.client.force_authenticate(user=self.member)
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"rsvp": False, "rsvp_count": 0})
        self.assertFalse(EventRSVP.objects.filter(event=self.event).exists())

    def test_leaving_removes_only_the_requesters_rsvp(self):
        EventRSVP.objects.create(auth_user=self.member, event=self.event)
        EventRSVP.objects.create(auth_user=self.other, event=self.event)
        self._hide()
        self.client.force_authenticate(user=self.member)
        self.client.delete(self.url)
        self.assertEqual(
            list(EventRSVP.objects.filter(event=self.event)
                 .values_list("auth_user__username", flat=True)),
            ["cizi"],
        )

    def test_delete_without_an_rsvp_does_not_confirm_a_hidden_event(self):
        self._hide()
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self.client.delete(self.url).status_code, 404)

    def test_joining_a_hidden_event_is_still_refused(self):
        self._hide()
        self.client.force_authenticate(user=self.member)
        self.assertEqual(self.client.put(self.url).status_code, 404)
        self.assertFalse(EventRSVP.objects.filter(event=self.event).exists())

    def test_delete_of_an_unknown_slug_is_404(self):
        self.client.force_authenticate(user=self.member)
        url = reverse("api-event-rsvp", kwargs={"slug": "neexistuje"})
        self.assertEqual(self.client.delete(url).status_code, 404)


class ShellStatusTests(TestCase):
    """`react_index` answers 404 exactly where the API would for this viewer."""

    @classmethod
    def setUpTestData(cls):
        UserModel = get_user_model()
        cls.admin_user = UserModel.objects.create_user(username="spravce", password="x")
        Profile.objects.update_or_create(
            user=cls.admin_user, defaults={"role": Profile.ROLE_ADMIN},
        )
        cls.member = UserModel.objects.create_user(username="clenka", password="x")

        cls.hidden_lb = LeaderboardUser.objects.create(name="Skrytá Hráčka")
        cls.hidden_account = UserModel.objects.create_user(username="skryta", password="x")
        Profile.objects.update_or_create(
            user=cls.hidden_account,
            defaults={"leaderboard_user": cls.hidden_lb, "members_only": True},
        )

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        index_path = os.path.join(tmp.name, "index.html")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(_SHELL)
        patcher = patch("mysite.views._resolve_index_path", return_value=index_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- profiles --------------------------------------------------------

    def test_members_only_profile_is_404_for_anonymous(self):
        self.assertEqual(self.client.get("/profil/skryta").status_code, 404)

    def test_members_only_profile_is_200_when_signed_in(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/profil/skryta").status_code, 200)

    def test_unknown_profile_is_404(self):
        self.assertEqual(self.client.get("/profil/nikdo").status_code, 404)

    def test_members_only_profile_card_never_names_them(self):
        self.client.force_login(self.member)
        self.assertNotIn("Skrytá", self.client.get("/profil/skryta").content.decode())

    # --- events ----------------------------------------------------------

    def test_hidden_event_is_404_for_anonymous_and_unnamed(self):
        event = _event(visible_to_users=False)
        resp = self.client.get(f"/events/{event.slug}")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Tajná akce", resp.content.decode())

    def test_hidden_event_is_404_for_a_plain_member(self):
        event = _event(visible_to_users=False)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f"/events/{event.slug}").status_code, 404)

    def test_hidden_event_is_200_for_admin(self):
        event = _event(visible_to_users=False)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(f"/events/{event.slug}").status_code, 200)

    def test_close_preview_is_200_for_close_role(self):
        event = _event(visible_to_users=False, visible_to_close=True)
        Profile.objects.update_or_create(
            user=self.member, defaults={"role": Profile.ROLE_CLOSE})
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f"/events/{event.slug}").status_code, 200)

    def test_unknown_event_is_404(self):
        self.assertEqual(self.client.get("/events/neexistuje").status_code, 404)

    # --- players ---------------------------------------------------------

    def test_members_only_player_page_is_200_like_its_api(self):
        # The board links the row here, and the API serves that row.
        self.assertEqual(self.client.get(f"/hrac/{self.hidden_lb.id}").status_code, 200)

    def test_members_only_player_off_every_board_is_404(self):
        Profile.objects.filter(user=self.hidden_account).update(hide_pts=True)
        self.assertEqual(self.client.get(f"/hrac/{self.hidden_lb.id}").status_code, 404)

    # --- caching ---------------------------------------------------------

    def test_shell_is_never_stored_by_a_shared_cache(self):
        """The status above varies by viewer; Cloudflare ignores Vary: Cookie."""
        cache_control = self.client.get("/").headers.get("Cache-Control", "")
        self.assertIn("private", cache_control)
        self.assertIn("no-cache", cache_control)
        self.assertNotIn("public", cache_control)
