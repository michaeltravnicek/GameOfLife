"""Merging two leaderboard players into one.

The merge is the operation that moves somebody's points, so these tests are
written around the ways it can silently lose or duplicate them: unique
constraints on both sides, merge chains, and the soft-merge flag that has to
keep the merged row out of every ranking without deleting it.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from leaderboard import merging
from leaderboard.cache_config import season_leaderboard_key
from leaderboard.models import (
    Badge, Event, EventFeedback, User as LeaderboardUser, UserBadge, UserToEvent,
)
from leaderboard.services.leaderboard import leaderboard_total, top_players

AuthUser = get_user_model()


def make_event(name, points=10, badge=None, days_ago=1):
    return Event.objects.create(
        name=name, points=points, badge=badge,
        date=timezone.now() - timedelta(days=days_ago),
    )


def make_player(name, email=None):
    return LeaderboardUser.objects.create(name=name, email=email)


def attend(player, event, points=None):
    return UserToEvent.objects.create(
        user=player, event=event,
        points=event.points if points is None else points,
    )


class MergeMovesHistoryTests(TestCase):
    def setUp(self):
        self.archive = make_player("Jan Novák")
        self.target = make_player("Jan Novak")

    def test_attendance_moves_to_the_target(self):
        event = make_event("Běh")
        attend(self.archive, event)
        merging.merge_players(self.archive, self.target)
        self.assertEqual(UserToEvent.objects.filter(user=self.target).count(), 1)
        self.assertEqual(UserToEvent.objects.filter(user=self.archive).count(), 0)

    def test_points_add_up_across_different_events(self):
        attend(self.archive, make_event("A", points=10))
        attend(self.target, make_event("B", points=5))
        merging.merge_players(self.archive, self.target)
        total = sum(UserToEvent.objects.filter(user=self.target)
                    .values_list("points", flat=True))
        self.assertEqual(total, 15)

    def test_same_event_on_both_sides_keeps_the_higher_score(self):
        """The person filled the form *and* checked in. One attendance, best points."""
        event = make_event("Dvakrát", points=10)
        attend(self.archive, event, points=30)
        attend(self.target, event, points=10)
        moved = merging.merge_players(self.archive, self.target)
        rows = UserToEvent.objects.filter(user=self.target, event=event)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().points, 30)
        self.assertEqual(moved["attendance_points_kept"], 1)

    def test_same_event_does_not_lower_an_existing_score(self):
        event = make_event("Dvakrát", points=10)
        attend(self.archive, event, points=5)
        attend(self.target, event, points=25)
        merging.merge_players(self.archive, self.target)
        row = UserToEvent.objects.get(user=self.target, event=event)
        self.assertEqual(row.points, 25)

    def test_badges_move_and_duplicates_collapse(self):
        shared = Badge.objects.create(name="Shared")
        only_archive = Badge.objects.create(name="Archive")
        UserBadge.objects.create(user=self.archive, badge=shared)
        UserBadge.objects.create(user=self.archive, badge=only_archive)
        UserBadge.objects.create(user=self.target, badge=shared)

        moved = merging.merge_players(self.archive, self.target)

        badges = set(UserBadge.objects.filter(user=self.target)
                     .values_list("badge__name", flat=True))
        self.assertEqual(badges, {"Shared", "Archive"})
        self.assertEqual(moved["badges"], 1)
        self.assertEqual(UserBadge.objects.filter(user=self.archive).count(), 0)

    def test_feedback_moves_when_the_target_has_none_for_that_event(self):
        event = make_event("Akce")
        EventFeedback.objects.create(user=self.archive, event=event, rating=8)
        moved = merging.merge_players(self.archive, self.target)
        self.assertEqual(moved["feedback"], 1)
        self.assertEqual(EventFeedback.objects.get(user=self.target).rating, 8)

    def test_the_newer_rating_wins_a_collision(self):
        """Form rating first, web rating later — the later opinion stands."""
        event = make_event("Akce")
        old = EventFeedback.objects.create(user=self.archive, event=event, rating=8)
        new = EventFeedback.objects.create(user=self.target, event=event, rating=3)
        EventFeedback.objects.filter(pk=old.pk).update(
            created_at=new.created_at - timedelta(days=30))

        merging.merge_players(self.archive, self.target)

        rows = EventFeedback.objects.filter(user=self.target, event=event)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().rating, 3)

    def test_an_older_target_rating_is_replaced_by_the_newer_archive_one(self):
        event = make_event("Akce")
        newer = EventFeedback.objects.create(user=self.archive, event=event, rating=9)
        older = EventFeedback.objects.create(user=self.target, event=event, rating=2)
        EventFeedback.objects.filter(pk=older.pk).update(
            created_at=newer.created_at - timedelta(days=30))

        merging.merge_players(self.archive, self.target)

        rows = EventFeedback.objects.filter(user=self.target, event=event)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().rating, 9)

    def test_email_moves_when_the_target_has_none(self):
        archive = make_player("Jan Novák", email="jan@example.com")
        target = make_player("Jan Novak")
        merging.merge_players(archive, target)
        archive.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(target.email, "jan@example.com")
        self.assertIsNone(archive.email)

    def test_target_keeps_its_own_email(self):
        archive = make_player("Jan Novák", email="stary@example.com")
        target = make_player("Jan Novak", email="ucet@example.com")
        merging.merge_players(archive, target)
        target.refresh_from_db()
        self.assertEqual(target.email, "ucet@example.com")

    def test_merge_evicts_the_leaderboard_cache(self):
        # The all-time board is the "all" member of the per-season key family --
        # which is what /api/v1/leaderboard/ actually reads. This assertion used
        # to name a standalone `leaderboard_data` key that nothing had written
        # since the HTML pages were removed, so it held whether or not the real
        # board was ever evicted.
        key = season_leaderboard_key("all")
        cache.set(key, "SENTINEL", 60)
        merging.merge_players(self.archive, self.target)
        self.assertIsNone(cache.get(key))


class MergedPlayerVisibilityTests(TestCase):
    """A merged row must be gone from every ranking, but still in the database."""

    def setUp(self):
        self.archive = make_player("Jan Novák")
        self.target = make_player("Jan Novak")
        attend(self.archive, make_event("A", points=10))

    def test_merged_player_is_not_in_the_default_manager(self):
        merging.merge_players(self.archive, self.target)
        self.assertNotIn(self.archive, LeaderboardUser.objects.all())

    def test_merged_player_still_exists_for_all_objects(self):
        merging.merge_players(self.archive, self.target)
        self.assertTrue(LeaderboardUser.all_objects.filter(pk=self.archive.pk).exists())

    def test_merged_player_is_off_the_leaderboard(self):
        merging.merge_players(self.archive, self.target)
        names = [p.name for p in leaderboard_total()]
        self.assertNotIn("Jan Novák", names)
        self.assertIn("Jan Novak", names)

    def test_the_points_show_up_under_the_target(self):
        merging.merge_players(self.archive, self.target)
        board = {p.name: p.total_points for p in top_players()}
        self.assertEqual(board.get("Jan Novak"), 10)

    def test_no_double_counting_after_the_merge(self):
        """Ten points before, ten points after — the merge must not duplicate."""
        before = sum(p.total_points for p in leaderboard_total())
        merging.merge_players(self.archive, self.target)
        after = sum(p.total_points for p in leaderboard_total())
        self.assertEqual(before, after)

    def test_profile_of_a_merged_player_still_resolves(self):
        """base_manager_name: a filtered base manager would raise DoesNotExist."""
        account = AuthUser.objects.create_user("kdo", "k@x.cz", "pw12345!")
        profile = Profile.objects.create(user=account, leaderboard_user=self.target)
        merging.merge_players(self.archive, self.target)
        profile.refresh_from_db()
        self.assertEqual(profile.leaderboard_user, self.target)


class MergeRefusalTests(TestCase):
    def setUp(self):
        self.archive = make_player("Jan Novák")
        self.target = make_player("Jan Novak")

    def test_cannot_merge_a_player_into_itself(self):
        with self.assertRaises(merging.MergeError):
            merging.merge_players(self.archive, self.archive)

    def test_cannot_merge_a_player_that_owns_an_account(self):
        account = AuthUser.objects.create_user("kdo", "k@x.cz", "pw12345!")
        Profile.objects.create(user=account, leaderboard_user=self.archive)
        with self.assertRaises(merging.MergeError):
            merging.merge_players(self.archive, self.target)

    def test_cannot_merge_an_already_merged_player(self):
        merging.merge_players(self.archive, self.target)
        third = make_player("Někdo Jiný")
        with self.assertRaises(merging.MergeError):
            merging.merge_players(self.archive, third)

    def test_cannot_merge_into_a_merged_player(self):
        final = make_player("Konečný")
        merging.merge_players(self.target, final)
        with self.assertRaises(merging.MergeError):
            merging.merge_players(self.archive, self.target)

    def test_a_refused_merge_writes_nothing(self):
        event = make_event("A")
        attend(self.archive, event)
        account = AuthUser.objects.create_user("kdo", "k@x.cz", "pw12345!")
        Profile.objects.create(user=account, leaderboard_user=self.archive)
        with self.assertRaises(merging.MergeError):
            merging.merge_players(self.archive, self.target)
        self.assertEqual(UserToEvent.objects.filter(user=self.archive).count(), 1)
        self.assertEqual(UserToEvent.objects.filter(user=self.target).count(), 0)


class MergeChainTests(TestCase):
    """A→B→C: everything that takes a player id has to land on C."""

    def setUp(self):
        self.a = make_player("A")
        self.b = make_player("B")
        self.c = make_player("C")

    def test_resolve_follows_the_whole_chain(self):
        merging.merge_players(self.a, self.b)
        merging.merge_players(self.b, self.c)
        self.assertEqual(merging.resolve_player_id(self.a.pk), self.c)

    def test_resolve_returns_a_live_player_unchanged(self):
        self.assertEqual(merging.resolve_player_id(self.c.pk), self.c)

    def test_resolve_of_an_unknown_id_is_none(self):
        self.assertIsNone(merging.resolve_player_id(999999))

    def test_a_cycle_raises_instead_of_looping_forever(self):
        """Only reachable through hand-edited data — but it must not hang."""
        merging.merge_players(self.a, self.b)
        LeaderboardUser.all_objects.filter(pk=self.b.pk).update(merged_into=self.a)
        with self.assertRaises(merging.MergeError):
            merging.resolve_player_id(self.a.pk)


class UnmergeTests(TestCase):
    def setUp(self):
        self.archive = make_player("Jan Novák")
        self.target = make_player("Jan Novak")
        attend(self.archive, make_event("A", points=10))

    def test_unmerge_returns_the_player_to_the_leaderboard(self):
        merging.merge_players(self.archive, self.target)
        merging.unmerge_players(self.archive)
        self.archive.refresh_from_db()
        self.assertIsNone(self.archive.merged_into)
        self.assertIsNone(self.archive.merged_at)
        self.assertIn(self.archive, LeaderboardUser.objects.all())

    def test_unmerge_does_not_move_the_history_back(self):
        """Documented limit: the row returns, its points stay with the target."""
        merging.merge_players(self.archive, self.target)
        merging.unmerge_players(self.archive)
        self.assertEqual(UserToEvent.objects.filter(user=self.archive).count(), 0)
        self.assertEqual(UserToEvent.objects.filter(user=self.target).count(), 1)

    def test_unmerging_a_live_player_is_refused(self):
        with self.assertRaises(merging.MergeError):
            merging.unmerge_players(self.archive)

    def test_unmerge_evicts_the_leaderboard_cache(self):
        merging.merge_players(self.archive, self.target)
        key = season_leaderboard_key("all")
        cache.set(key, "SENTINEL", 60)
        merging.unmerge_players(self.archive)
        self.assertIsNone(cache.get(key))


class BadgeSignalDuringMergeTests(TestCase):
    """Attendance saves fire award_badge_on_attendance — including ours."""

    def test_moving_attendance_awards_the_badge_to_the_target(self):
        badge = Badge.objects.create(name="Odznak")
        event = make_event("S odznakem", badge=badge)
        archive = make_player("Jan Novák")
        target = make_player("Jan Novak")
        attend(archive, event)
        UserBadge.objects.filter(user=archive).delete()  # simulate a pre-badge row

        merging.merge_players(archive, target)

        self.assertTrue(UserBadge.objects.filter(user=target, badge=badge).exists())
