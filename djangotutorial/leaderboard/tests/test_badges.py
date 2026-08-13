"""Badge awarding (signals) and exposure on the player/profile APIs."""
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import (
    Badge, Event, Season, User as LeaderboardUser, UserBadge, UserToEvent,
)


class BadgeAwardingTests(TestCase):
    """The post_save signal on UserToEvent grants the event's badge."""

    def setUp(self):
        self.badge = Badge.objects.create(name="Karaoke King")
        self.event = Event.objects.create(
            sheet_id="k", sheet_list_id="x", name="Karaoke", place="Brno",
            points=10, date=timezone.now(), badge=self.badge,
        )
        self.player = LeaderboardUser.objects.create(name="Zpěvák")

    def test_attendance_awards_the_events_badge(self):
        UserToEvent.objects.create(user=self.player, event=self.event, points=10)
        self.assertTrue(
            UserBadge.objects.filter(user=self.player, badge=self.badge).exists()
        )

    def test_badge_is_collected_only_once(self):
        other = Event.objects.create(
            sheet_id="k2", sheet_list_id="x", name="Karaoke 2", place="Brno",
            points=10, date=timezone.now(), badge=self.badge,
        )
        UserToEvent.objects.create(user=self.player, event=self.event, points=10)
        UserToEvent.objects.create(user=self.player, event=other, points=10)
        self.assertEqual(
            UserBadge.objects.filter(user=self.player, badge=self.badge).count(), 1
        )

    def test_event_without_badge_awards_nothing(self):
        plain = Event.objects.create(
            sheet_id="p", sheet_list_id="x", name="Bez odznaku", place="Brno",
            points=10, date=timezone.now(),
        )
        UserToEvent.objects.create(user=self.player, event=plain, points=10)
        self.assertEqual(UserBadge.objects.filter(user=self.player).count(), 0)

    def test_badge_survives_removed_attendance(self):
        # UserBadge.event is SET_NULL — losing the source attendance must not
        # revoke the collected badge.
        u2e = UserToEvent.objects.create(user=self.player, event=self.event, points=10)
        u2e.delete()
        self.assertTrue(
            UserBadge.objects.filter(user=self.player, badge=self.badge).exists()
        )


class BadgeApiExposureTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.badge = Badge.objects.create(name="Nahá míle", description="Za odvahu")
        self.event = Event.objects.create(
            sheet_id="nm", sheet_list_id="x", name="Nahá míle", place="Brno",
            points=10, date=timezone.now(), badge=self.badge,
        )
        self.player = LeaderboardUser.objects.create(name="Běžec Odvážný")
        UserToEvent.objects.create(user=self.player, event=self.event, points=10)

    def test_player_detail_lists_badges(self):
        resp = self.client.get(reverse("api-player", kwargs={"user_id": self.player.id}))
        self.assertEqual(resp.status_code, 200)
        badges = resp.json()["badges"]
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]["name"], "Nahá míle")
        self.assertEqual(badges[0]["description"], "Za odvahu")

    def test_player_without_badges_gets_empty_list(self):
        loner = LeaderboardUser.objects.create(name="Nikdo")
        resp = self.client.get(reverse("api-player", kwargs={"user_id": loner.id}))
        self.assertEqual(resp.json()["badges"], [])

    def test_profile_lists_badges_for_linked_account(self):
        auth = get_user_model().objects.create_user(username="odvazny", password="x")
        Profile.objects.create(
            user=auth, leaderboard_user=self.player,
            gdpr_consent_at=timezone.now(),
            gdpr_consent_version=settings.PRIVACY_POLICY_VERSION,
        )
        resp = self.client.get(reverse("api-profile", kwargs={"username": "odvazny"}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([b["name"] for b in resp.json()["badges"]], ["Nahá míle"])

    def test_unlinked_account_has_no_badges(self):
        auth = get_user_model().objects.create_user(username="samotar", password="x")
        Profile.objects.create(user=auth)  # no leaderboard_user
        resp = self.client.get(reverse("api-profile", kwargs={"username": "samotar"}))
        self.assertEqual(resp.json()["badges"], [])
