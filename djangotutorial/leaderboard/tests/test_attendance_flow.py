"""End-to-end sequence tests: attendance writes propagating across the API.

These drive whole workflows through the real endpoints and assert that a change
in one place shows up everywhere it should — attendance → leaderboard order/rank
→ player detail → event attendee_count → attendees/RSVP lists.

Cache note: the per-season leaderboard cache is invalidated via django-redis
`delete_pattern`, which only exists on Redis — under the test cache it's a no-op,
so a write-then-read would otherwise see stale data. We run these with DummyCache
(every read recomputes from the DB) so the tests exercise data flow through the
endpoints, not the Redis-specific eviction (which production trusts separately).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Event, EventRSVP, Season, User as LeaderboardUser, UserToEvent

DUMMY_CACHE = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}


@override_settings(CACHES=DUMMY_CACHE)
class AttendanceLeaderboardFlowTests(TestCase):
    """Admin awards/edits/removes points; leaderboard + detail track it live."""

    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.admin = UserModel.objects.create_user(username="boss", password="x")
        Profile.objects.create(user=self.admin, role=Profile.ROLE_ADMIN)

        now = timezone.now()
        year = now.year
        self.season = Season.objects.create(
            name=str(year), start_date=date(year, 1, 1), end_date=date(year, 12, 31),
            is_active=True,
        )
        self.event = Event.objects.create(
            sheet_id="e", sheet_list_id="x", name="Turnaj", place="Brno", points=10,
            date=now,
        )
        self.alice = LeaderboardUser.objects.create(name="Alice")
        self.bob = LeaderboardUser.objects.create(name="Bob")
        self.cora = LeaderboardUser.objects.create(name="Cora")
        self.client.force_authenticate(user=self.admin)

    # helpers -----------------------------------------------------------------

    def _attend(self, lb_user, points):
        return self.client.put(
            reverse("api-event-attendee",
                    kwargs={"slug": self.event.slug, "user_id": lb_user.id}),
            {"points": points}, format="json",
        )

    def _remove(self, lb_user):
        return self.client.delete(reverse(
            "api-event-attendee", kwargs={"slug": self.event.slug, "user_id": lb_user.id}))

    def _board(self):
        resp = self.client.get(reverse("api-leaderboard"))
        return [(e["name"], e["total_points"], e["rank"]) for e in resp.json()["entries"]]

    def _detail(self):
        return self.client.get(
            reverse("api-event-detail", kwargs={"slug": self.event.slug})).json()

    # the flow ----------------------------------------------------------------

    def test_award_reorder_and_remove_sequence(self):
        # 0. Nothing awarded yet: empty board, zero attendees.
        self.assertEqual(self._board(), [])
        self.assertEqual(self._detail()["attendee_count"], 0)

        # 1. Award three players — all creates (201).
        self.assertEqual(self._attend(self.alice, 10).status_code, 201)
        self.assertEqual(self._attend(self.bob, 30).status_code, 201)
        self.assertEqual(self._attend(self.cora, 20).status_code, 201)

        # 2. Board reflects points, ordered desc with 1-based ranks.
        self.assertEqual(
            self._board(),
            # Public board shortens unconsented players to "Jméno P." — these
            # fixtures are single-token names, so there is no surname to drop.
            [("Bob", 30, 1), ("Cora", 20, 2), ("Alice", 10, 3)],
        )
        # 3. Event detail + attendees list agree.
        self.assertEqual(self._detail()["attendee_count"], 3)
        attendees = self.client.get(reverse(
            "api-event-attendees", kwargs={"slug": self.event.slug})).json()["attendees"]
        self.assertEqual([(a["name"], a["points"]) for a in attendees],
                         [("Bob", 30), ("Cora", 20), ("Alice", 10)])

        # 4. Editing Alice's points is an update (200), and reorders the board.
        self.assertEqual(self._attend(self.alice, 50).status_code, 200)
        self.assertEqual(
            self._board(),
            [("Alice", 50, 1), ("Bob", 30, 2), ("Cora", 20, 3)],
        )
        # 5. Player detail for Alice reflects the new total.
        pd = self.client.get(
            reverse("api-player", kwargs={"user_id": self.alice.id})).json()
        self.assertEqual((pd["total_points"], pd["events_count"], pd["rank"]), (50, 1, 1))

        # 6. Removing Bob drops him off the (season) board and the count.
        self.assertEqual(self._remove(self.bob).status_code, 200)
        self.assertEqual(self._board(), [("Alice", 50, 1), ("Cora", 20, 2)])
        self.assertEqual(self._detail()["attendee_count"], 2)

        # 7. Re-adding Bob is a fresh create again (201), back on the board.
        self.assertEqual(self._attend(self.bob, 5).status_code, 201)
        self.assertEqual(self._detail()["attendee_count"], 3)
        self.assertIn(("Bob", 5, 3), self._board())

    def test_tied_points_share_rank(self):
        self._attend(self.alice, 20)
        self._attend(self.bob, 20)
        self._attend(self.cora, 10)
        board = self._board()
        # Alice + Bob tie at 20 → same rank; Cora is rank 3 (ties consume slots).
        ranks = {name: rank for name, _pts, rank in board}
        self.assertEqual(ranks["Alice"], ranks["Bob"])
        self.assertEqual(ranks["Cora"], 3)


@override_settings(CACHES=DUMMY_CACHE)
class SeasonScopedAttendanceFlowTests(TestCase):
    """Attendance shows up only in the season whose window contains the event."""

    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.admin = UserModel.objects.create_user(username="boss", password="x")
        Profile.objects.create(user=self.admin, role=Profile.ROLE_ADMIN)
        self.client.force_authenticate(user=self.admin)

        now = timezone.now()
        self.this_year = now.year
        self.last_year = now.year - 1
        self.s_last = Season.objects.create(
            name=str(self.last_year), start_date=date(self.last_year, 1, 1),
            end_date=date(self.last_year, 12, 31), is_active=False,
        )
        self.s_this = Season.objects.create(
            name=str(self.this_year), start_date=date(self.this_year, 1, 1),
            end_date=date(self.this_year, 12, 31), is_active=True,
        )
        self.event = Event.objects.create(
            sheet_id="e", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=now,  # falls inside this year's season only
        )
        self.player = LeaderboardUser.objects.create(name="Alice")

    def _board(self, season_id):
        resp = self.client.get(reverse("api-leaderboard"), {"season_id": season_id})
        return [e["name"] for e in resp.json()["entries"]]

    def test_points_are_scoped_to_the_event_season(self):
        self.client.put(
            reverse("api-event-attendee",
                    kwargs={"slug": self.event.slug, "user_id": self.player.id}),
            {"points": 15}, format="json",
        )
        # Current season + all-time include Alice; last year's season does not.
        self.assertEqual(self._board(self.s_this.id), ["Alice"])
        self.assertEqual(self._board("all"), ["Alice"])
        self.assertEqual(self._board(self.s_last.id), [])


class RsvpAttendanceIndependenceFlowTests(TestCase):
    """RSVP (intention) and attendance (points) are separate and coexist."""

    def setUp(self):
        self.client = APIClient()
        UserModel = get_user_model()
        self.admin = UserModel.objects.create_user(username="boss", password="x")
        Profile.objects.create(user=self.admin, role=Profile.ROLE_ADMIN)

        # A runner with a linked leaderboard account.
        self.runner = UserModel.objects.create_user(
            username="runner", password="x", first_name="Runner", last_name="One")
        self.runner_lb = LeaderboardUser.objects.create(name="Runner One")
        Profile.objects.create(user=self.runner, leaderboard_user=self.runner_lb)

        self.event = Event.objects.create(
            sheet_id="e", sheet_list_id="x", name="Akce", place="Brno", points=10,
            date=timezone.now() + timedelta(days=1),
        )

    def _detail(self):
        return self.client.get(
            reverse("api-event-detail", kwargs={"slug": self.event.slug})).json()

    def test_rsvp_then_attendance_are_independent(self):
        # 1. Runner RSVPs as themselves.
        self.client.force_authenticate(user=self.runner)
        self.assertEqual(
            self.client.put(reverse("api-event-rsvp",
                                    kwargs={"slug": self.event.slug})).status_code, 201)
        d = self._detail()
        self.assertEqual((d["rsvp_count"], d["attendee_count"]), (1, 0))

        # 2. Admin awards attendance points to the runner's leaderboard user.
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(
            self.client.put(
                reverse("api-event-attendee",
                        kwargs={"slug": self.event.slug, "user_id": self.runner_lb.id}),
                {"points": 15}, format="json").status_code, 201)
        d = self._detail()
        self.assertEqual((d["rsvp_count"], d["attendee_count"]), (1, 1))

        # 3. Both admin lists show the runner, from their respective sources.
        rsvps = self.client.get(
            reverse("api-event-rsvps", kwargs={"slug": self.event.slug})).json()["rsvps"]
        self.assertEqual([r["username"] for r in rsvps], ["runner"])

        attendees = self.client.get(reverse(
            "api-event-attendees", kwargs={"slug": self.event.slug})).json()["attendees"]
        self.assertEqual(len(attendees), 1)
        self.assertEqual(attendees[0]["profile_username"], "runner")
        self.assertEqual(attendees[0]["points"], 15)

        # 4. Removing attendance leaves the RSVP intact.
        self.assertEqual(
            self.client.delete(
                reverse("api-event-attendee",
                        kwargs={"slug": self.event.slug, "user_id": self.runner_lb.id})
            ).status_code, 200)
        d = self._detail()
        self.assertEqual((d["rsvp_count"], d["attendee_count"]), (1, 0))
