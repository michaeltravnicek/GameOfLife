"""`dedupe_players` folds one human stored twice, and nobody else."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from leaderboard.models import Event, User as Player, UserToEvent

AuthUser = get_user_model()


def _event(name, days_ago):
    return Event.objects.create(name=name, points=50, date=timezone.now() - timedelta(days=days_ago))


def _player(name, events, email=None):
    p = Player.objects.create(name=name, email=email)
    for e in events:
        UserToEvent.objects.create(user=p, event=e, points=e.points)
    return p


def _run(*args):
    out = StringIO()
    call_command("dedupe_players", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


class DedupePlayersTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = _event("A", 30), _event("B", 20), _event("C", 10)

    def _alive(self, *players):
        return [Player.objects.filter(pk=p.pk).exists() for p in players]

    def test_sync_duplicate_with_accent_difference_is_merged_into_the_email_row(self):
        archive = _player("Klara Prochazkova", [self.a, self.b])
        synced = _player("Klára Procházková", [self.a, self.b], email="k@example.com")
        _run("--apply")
        self.assertEqual(self._alive(archive, synced), [False, True])
        self.assertEqual(Player.all_objects.get(pk=archive.pk).merged_into_id, synced.pk)
        self.assertEqual(UserToEvent.objects.filter(user=synced).count(), 2)

    def test_word_order_and_subset_history_still_match(self):
        archive = _player("Novák Jan", [self.a])
        synced = _player("jan  novák", [self.a, self.b, self.c], email="j@example.com")
        _run("--apply")
        self.assertEqual(self._alive(archive, synced), [False, True])

    def test_differently_spelled_surname_needs_identical_two_event_history(self):
        archive = _player("Daniel Pospisil", [self.a, self.b])
        synced = _player("Daniel Pospsil", [self.a, self.b], email="d@example.com")
        _run("--apply")
        self.assertEqual(self._alive(archive, synced), [False, True])

    def test_namesakes_at_one_event_are_left_alone(self):
        one = _player("Nikola Kotová", [self.a])
        two = _player("Nikola Krupicová", [self.a])
        out = _run("--apply")
        self.assertEqual(self._alive(one, two), [True, True])
        self.assertIn("candidate", out)

    def test_two_emails_are_two_people(self):
        one = _player("Tereza Svobodová", [self.a], email="t1@example.com")
        two = _player("Tereza Svobodová", [self.a], email="t2@example.com")
        _run("--apply")
        self.assertEqual(self._alive(one, two), [True, True])

    def test_account_players_are_left_to_the_admin(self):
        account_player = _player("Hana Tichá", [self.a, self.b])
        Profile.objects.create(user=AuthUser.objects.create_user("hana"), leaderboard_user=account_player)
        archive = _player("Hana Tichá", [self.a, self.b])
        _run("--apply")
        self.assertEqual(self._alive(account_player, archive), [True, True])

    def test_dry_run_writes_nothing_and_apply_is_idempotent(self):
        archive = _player("Monika Kralova", [self.a, self.b])
        synced = _player("Monika Králová", [self.a, self.b], email="m@example.com")
        self.assertIn("would merge", _run())
        self.assertEqual(self._alive(archive, synced), [True, True])
        _run("--apply")
        self.assertIn("Merged 0", _run("--apply"))
