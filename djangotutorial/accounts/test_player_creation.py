"""Every account gets a leaderboard player at signup.

Before this, a fresh account had no player, and `leaderboard/checkin.py` refuses
an account without one -- so somebody could register, show up at an event, hit
check-in and get nothing, with no record that they were there. The player is now
created during registration.

The e-mail is what makes it more than a `create()`: an archive player carrying
the same address is adopted rather than duplicated. That is deliberately trusting
an unverified e-mail on the local signup path (see ensure_leaderboard_user), so
the tests below pin down exactly how far the trust goes -- in particular that it
never takes a player another account already owns.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.services import ensure_leaderboard_user
from leaderboard import merging
from leaderboard.models import Event, User as LeaderboardUser, UserToEvent

AuthUser = get_user_model()

BRNO_LAT, BRNO_LON = 49.1951, 16.6068


def register_payload(**overrides):
    return {
        "username": "novacek",
        "first_name": "Jan",
        "email": "jan.novak@example.com",
        "password1": "bezpecneheslo1",
        "password2": "bezpecneheslo1",
        "gdpr_consent": True,
        **overrides,
    }


class RegistrationCreatesPlayerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("api-register")

    def test_registration_creates_a_player(self):
        self.client.post(self.url, register_payload(), format="json")
        profile = Profile.objects.get(user__username="novacek")
        self.assertIsNotNone(profile.leaderboard_user)
        self.assertEqual(profile.leaderboard_user.name, "Jan")

    def test_the_player_carries_the_account_email(self):
        self.client.post(self.url, register_payload(), format="json")
        player = Profile.objects.get(user__username="novacek").leaderboard_user
        self.assertEqual(player.email, "jan.novak@example.com")

    def test_registration_adopts_an_archive_player_with_the_same_email(self):
        """The decided-on trade-off: an exact e-mail match links straight away."""
        archive = LeaderboardUser.objects.create(
            name="Jan Novák", email="jan.novak@example.com")
        event = Event.objects.create(name="Stará akce", points=25,
                                     date=timezone.now() - timedelta(days=40))
        UserToEvent.objects.create(user=archive, event=event, points=25)

        self.client.post(self.url, register_payload(), format="json")

        profile = Profile.objects.get(user__username="novacek")
        self.assertEqual(profile.leaderboard_user, archive)
        # …and the history is there immediately, which is the whole point.
        self.assertEqual(
            UserToEvent.objects.filter(user=profile.leaderboard_user).count(), 1)

    def test_adoption_is_case_insensitive(self):
        archive = LeaderboardUser.objects.create(
            name="Jan Novák", email="jan.novak@example.com")
        self.client.post(
            self.url, register_payload(email="Jan.Novak@Example.com"), format="json")
        self.assertEqual(
            Profile.objects.get(user__username="novacek").leaderboard_user, archive)

    def test_a_player_owned_by_another_account_is_never_adopted(self):
        """The one outcome worth writing code to prevent: inheriting a stranger."""
        owned = LeaderboardUser.objects.create(
            name="Jan Novák", email="jan.novak@example.com")
        other = AuthUser.objects.create_user("jiny", "jiny@example.com", "pw12345!")
        Profile.objects.create(user=other, leaderboard_user=owned)

        self.client.post(self.url, register_payload(), format="json")

        profile = Profile.objects.get(user__username="novacek")
        self.assertIsNotNone(profile.leaderboard_user)
        self.assertNotEqual(profile.leaderboard_user, owned)

    def test_a_colliding_email_does_not_break_registration(self):
        """LeaderboardUser.email is unique — a naive create() would 500 here."""
        owned = LeaderboardUser.objects.create(
            name="Jan Novák", email="jan.novak@example.com")
        other = AuthUser.objects.create_user("jiny", "jiny@example.com", "pw12345!")
        Profile.objects.create(user=other, leaderboard_user=owned)

        resp = self.client.post(self.url, register_payload(), format="json")

        self.assertEqual(resp.status_code, 201)
        player = Profile.objects.get(user__username="novacek").leaderboard_user
        self.assertIsNone(player.email)

    def test_registration_adopts_the_merge_target_not_the_merged_row(self):
        archive = LeaderboardUser.objects.create(
            name="Jan Novák", email="jan.novak@example.com")
        target = LeaderboardUser.objects.create(name="Jan Novak")
        merging.merge_players(archive, target)

        self.client.post(self.url, register_payload(), format="json")

        profile = Profile.objects.get(user__username="novacek")
        self.assertEqual(profile.leaderboard_user, target)


class EnsureLeaderboardUserTests(TestCase):
    def setUp(self):
        self.account = AuthUser.objects.create_user(
            "kdo", "kdo@example.com", "pw12345!", first_name="Jan", last_name="Novák")

    def test_creates_a_player_named_after_the_account(self):
        player = ensure_leaderboard_user(self.account)
        self.assertEqual(player.name, "Jan Novák")

    def test_falls_back_to_the_username_when_no_name_is_set(self):
        anon = AuthUser.objects.create_user("anonym", "a@example.com", "pw12345!")
        self.assertEqual(ensure_leaderboard_user(anon).name, "anonym")

    def test_is_idempotent(self):
        first = ensure_leaderboard_user(self.account)
        second = ensure_leaderboard_user(self.account)
        self.assertEqual(first, second)
        self.assertEqual(LeaderboardUser.objects.count(), 1)

    def test_repoints_a_profile_whose_player_was_merged_away(self):
        """Otherwise the account sits on a row that is off the leaderboard."""
        old = ensure_leaderboard_user(self.account)
        target = LeaderboardUser.objects.create(name="Jan Novak")
        Profile.objects.filter(user=self.account).update(leaderboard_user=None)
        merging.merge_players(old, target)
        Profile.objects.filter(user=self.account).update(leaderboard_user=old)

        resolved = ensure_leaderboard_user(self.account)

        self.assertEqual(resolved, target)
        self.assertEqual(
            Profile.objects.get(user=self.account).leaderboard_user, target)

    def test_creates_a_profile_when_the_account_has_none(self):
        self.assertFalse(Profile.objects.filter(user=self.account).exists())
        ensure_leaderboard_user(self.account)
        self.assertTrue(Profile.objects.filter(user=self.account).exists())


class CheckinAfterRegistrationTests(TestCase):
    """The hole this change closes: a brand-new account can check in."""

    def setUp(self):
        self.client = APIClient()
        self.client.post(reverse("api-register"), register_payload(), format="json")
        self.event = Event.objects.create(
            name="Dnešní akce", points=10, date=timezone.now(),
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )

    def test_a_fresh_account_can_check_in(self):
        resp = self.client.post(
            reverse("api-event-checkin", kwargs={"slug": self.event.slug}),
            {"latitude": BRNO_LAT, "longitude": BRNO_LON}, format="json")
        self.assertEqual(resp.status_code, 200)
        player = Profile.objects.get(user__username="novacek").leaderboard_user
        self.assertTrue(
            UserToEvent.objects.filter(user=player, event=self.event).exists())


class BackfillCommandTests(TestCase):
    """`backfill_player_accounts` for accounts that predate the signup hook."""

    def setUp(self):
        self.account = AuthUser.objects.create_user(
            "stary", "stary@example.com", "pw12345!", first_name="Starý", last_name="Účet")
        Profile.objects.create(user=self.account)

    def test_creates_a_player(self):
        call_command("backfill_player_accounts")
        self.assertIsNotNone(
            Profile.objects.get(user=self.account).leaderboard_user)

    def test_adopts_an_archive_player_on_an_email_match(self):
        archive = LeaderboardUser.objects.create(
            name="Starý Účet", email="stary@example.com")
        call_command("backfill_player_accounts")
        self.assertEqual(
            Profile.objects.get(user=self.account).leaderboard_user, archive)

    def test_dry_run_writes_nothing(self):
        call_command("backfill_player_accounts", "--dry-run")
        self.assertIsNone(Profile.objects.get(user=self.account).leaderboard_user)
        self.assertEqual(LeaderboardUser.objects.count(), 0)

    def test_running_twice_creates_nothing_extra(self):
        call_command("backfill_player_accounts")
        call_command("backfill_player_accounts")
        self.assertEqual(LeaderboardUser.objects.count(), 1)
