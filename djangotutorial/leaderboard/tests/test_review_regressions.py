"""Regression tests for the bugs found in the 2026-09 code review.

One class per bug; each docstring names the failure it guards against.
"""
import os
import tempfile
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from rest_framework.test import APIClient

from accounts.models import Profile
from accounts.services import profile_payload
from leaderboard.admin import EventFeedbackAdmin
from leaderboard.image_utils import CAP_EVENT_IMAGE, needs_processing, process_upload
from leaderboard.models import (
    Event, EventFeedback, Season, User as LeaderboardUser, UserPhoto, UserToEvent,
)
from leaderboard.services import active_checkin_events, player_payload
from leaderboard.services.leaderboard import all_time_rank
from leaderboard.sheet_columns import header_map
from leaderboard.tasks import handle_attendance, insert_rec

from .helpers import BRNO_LAT, BRNO_LON, make_image_upload


class _FakeDate(date):
    """`date.today()` pinned to a chosen day."""
    fixed = date(2026, 1, 1)

    @classmethod
    def today(cls):
        return cls.fixed


class EnsureSeasonRolloverTests(TestCase):
    """`ensure_season` on the first deploy of a new year, with last year's
    season still active. Used to raise IntegrityError from the
    `season_single_active` constraint and fail the build."""

    def setUp(self):
        Season.objects.create(
            name="2025", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
            is_active=True,
        )

    def _run(self):
        out = StringIO()
        with mock.patch("leaderboard.management.commands.ensure_season.date", _FakeDate):
            call_command("ensure_season", stdout=out)
        return out.getvalue()

    def test_creates_and_activates_next_year(self):
        self.assertIn("Created season 2026", self._run())
        self.assertEqual(Season.objects.filter(is_active=True).count(), 1)
        self.assertTrue(Season.objects.get(name="2026").is_active)
        self.assertFalse(Season.objects.get(name="2025").is_active)

    def test_activates_an_existing_inactive_season(self):
        Season.objects.create(
            name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        self.assertIn("Activated season 2026", self._run())
        self.assertTrue(Season.objects.get(name="2026").is_active)

    def test_is_idempotent(self):
        self._run()
        self.assertIn("already active", self._run())


class FeedbackAdminSearchTests(TestCase):
    """`search_fields` referenced `user__number`, dropped in migration 0026;
    the admin search 500'd with FieldError."""

    def test_search_uses_only_live_fields(self):
        LeaderboardUser.objects.create(name="Hledaný", email="h@example.com")
        admin_obj = EventFeedbackAdmin(EventFeedback, AdminSite())
        request = RequestFactory().get("/", {"q": "hledan"})
        request.user = get_user_model().objects.create_superuser("a", "a@x.cz", "pw")
        qs, _ = admin_obj.get_search_results(
            request, EventFeedback.objects.all(), "h@example.com")
        list(qs)  # evaluates the query; FieldError would raise here


class BackfillEventDatesTests(TestCase):
    """`sheet_id__isnull=False` matched every event (the field is "" on
    manual ones), so `--apply` rewrote dates the form had set by hand."""

    def setUp(self):
        self.manual = Event.objects.create(
            name="Bowling 12.3.2025", place="Brno", points=10,
            date=timezone.make_aware(timezone.datetime(2025, 5, 5)),
        )
        self.synced = Event.objects.create(
            sheet_id="s", sheet_list_id="1", name="Bowling 12.3.2025",
            place="Brno", points=10,
            date=timezone.make_aware(timezone.datetime(2025, 5, 5)),
        )
        self.dateless = Event.objects.create(
            sheet_id="s", sheet_list_id="2", name="Karaoke 1.4.2025",
            place="Brno", points=10, date=None,
        )

    def test_only_sheet_events_are_rewritten(self):
        call_command("backfill_event_dates", "--apply", stdout=StringIO())
        self.manual.refresh_from_db()
        self.synced.refresh_from_db()
        self.assertEqual(self.manual.date.date(), date(2025, 5, 5))
        self.assertEqual(self.synced.date.date(), date(2025, 3, 12))

    def test_event_without_date_does_not_crash(self):
        call_command("backfill_event_dates", "--apply", stdout=StringIO())
        self.dateless.refresh_from_db()
        self.assertEqual(self.dateless.date.date(), date(2025, 4, 1))


class EventsListQueryCountTests(TestCase):
    """`time_tbd` was serialized but missing from `.only()`: one deferred-field
    query per event on every list page."""

    def test_list_is_constant_in_query_count(self):
        now = timezone.now()
        for i in range(12):
            Event.objects.create(
                sheet_id=f"q{i}", sheet_list_id="x", name=f"Event {i}", place="Brno",
                date=now + timedelta(days=i + 1), points=10,
            )
        client = APIClient()
        url = reverse("api-events-list")
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(url, {"limit": 12})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["events"]), 12)
        # session/user, count, page, cities, categories — nothing per row.
        self.assertLess(len(ctx.captured_queries), 10)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GalleryStorageCallTests(TestCase):
    """`variant_url` HEAD-checked the storage once per photo — a network
    round-trip per row on R2."""

    def test_gallery_does_not_probe_storage_per_photo(self):
        user = get_user_model().objects.create_user(username="g", password="x")
        for i in range(3):
            UserPhoto.objects.create(
                auth_user=user, image=make_image_upload(f"p{i}.png"))
        with mock.patch(
            "django.core.files.storage.FileSystemStorage.exists", autospec=True,
        ) as exists:
            resp = APIClient().get(reverse("api-gallery"), {"limit": 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["photos"]), 3)
        self.assertEqual(exists.call_count, 0)


class HiddenEventWriteGateTests(TestCase):
    """RSVP, feedback and check-in fetched the event with a plain
    `get_object_or_404`, so a draft (`visible_to_users=False`) collected
    RSVPs and ratings before it was published."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="u", password="x")
        lb = LeaderboardUser.objects.create(name="U")
        Profile.objects.create(user=self.user, leaderboard_user=lb)
        self.client.force_authenticate(user=self.user)
        self.event = Event.objects.create(
            name="Draft", place="Brno", points=10, visible_to_users=False,
            date=timezone.now() + timedelta(hours=1),
            latitude=BRNO_LAT, longitude=BRNO_LON, checkin_radius=500,
        )

    def test_rsvp_on_hidden_event_is_404(self):
        url = reverse("api-event-rsvp", kwargs={"slug": self.event.slug})
        self.assertEqual(self.client.put(url).status_code, 404)

    def test_feedback_on_hidden_event_is_404(self):
        url = reverse("api-event-feedback", kwargs={"slug": self.event.slug})
        resp = self.client.post(url, {"rating": 5}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_checkin_on_hidden_event_is_404(self):
        url = reverse("api-event-checkin", kwargs={"slug": self.event.slug})
        resp = self.client.post(
            url, {"latitude": BRNO_LAT, "longitude": BRNO_LON}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_admin_still_reaches_hidden_event(self):
        profile = Profile.objects.get(user=self.user)
        profile.role = Profile.ROLE_ADMIN
        profile.save()
        admin = get_user_model().objects.get(pk=self.user.pk)  # fresh profile cache
        self.client.force_authenticate(user=admin)
        url = reverse("api-event-rsvp", kwargs={"slug": self.event.slug})
        self.assertEqual(self.client.put(url).status_code, 201)


class SheetSyncPointsTests(TestCase):
    """The points column was read raw: a short row raised IndexError, an
    empty cell ValueError, and `int != "50"` re-saved every row each sync."""

    def setUp(self):
        self.event = Event.objects.create(
            sheet_id="pts", sheet_list_id="1", name="Body", place="Brno", points=50,
            date=timezone.now(),
        )
        self.cols = header_map(["Jméno", "Body"])

    def test_string_points_are_stored_as_int_once(self):
        insert_rec(self.event, ["Jan Novák", "70"], self.cols)
        row = UserToEvent.objects.get(event=self.event)
        self.assertEqual(row.points, 70)
        with mock.patch.object(UserToEvent, "save", autospec=True) as save:
            insert_rec(self.event, ["Jan Novák", "70"], self.cols)
        self.assertEqual(save.call_count, 0)

    def test_short_or_empty_points_cell_falls_back_to_event_points(self):
        insert_rec(self.event, ["Krátký Řádek"], self.cols)
        insert_rec(self.event, ["Prázdná Buňka", ""], self.cols)
        self.assertEqual(
            set(UserToEvent.objects.filter(event=self.event).values_list("points", flat=True)),
            {50},
        )

    def test_full_pass_imports_rows_after_a_web_checkin(self):
        """Positional slicing by attendance count skipped sheet rows once a
        web check-in had added a row that never came from the sheet."""
        web_only = LeaderboardUser.objects.create(name="Web Checkin")
        UserToEvent.objects.create(user=web_only, event=self.event, points=50)
        records = [["Jméno", "Body"], ["A A", "10"], ["B B", "20"]]
        handle_attendance("pts", "1", records)
        self.assertEqual(
            set(LeaderboardUser.objects.values_list("name", flat=True)),
            {"Web Checkin", "A A", "B B"},
        )

    def test_daily_run_keeps_an_admin_points_correction(self):
        records = [["Jméno", "Body"], ["A A", "10"]]
        handle_attendance("pts", "1", records)
        row = UserToEvent.objects.get(event=self.event)
        row.points = 35
        row.save()

        handle_attendance("pts", "1", records + [["B B", "20"]], overwrite_points=False)
        self.assertEqual(UserToEvent.objects.get(pk=row.pk).points, 35)
        self.assertEqual(UserToEvent.objects.filter(event=self.event).count(), 2)

        handle_attendance("pts", "1", records, overwrite_points=True)
        self.assertEqual(UserToEvent.objects.get(pk=row.pk).points, 10)


class AspectPredicateTests(TestCase):
    """`needs_processing` said "yes" for an in-bounds WebP on the wrong ratio
    while `process_upload` returned None for it, so the backfill re-reported
    the same files forever and never cropped them."""

    def test_wrong_ratio_webp_is_processed_and_then_final(self):
        from django.core.files.storage import FileSystemStorage

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "square.webp")
        Image.new("RGB", (800, 800), (10, 20, 30)).save(path, "WEBP", quality=80)

        class Field:
            storage = FileSystemStorage(location=tmp.name)
            name = "square.webp"

        limits = (2400, 2400, CAP_EVENT_IMAGE)
        self.assertTrue(needs_processing(Field, *limits, aspect=(4, 3)))
        process_upload(Field, *limits, aspect=(4, 3))
        with Image.open(path) as img:
            self.assertAlmostEqual(img.width / img.height, 4 / 3, places=2)
        self.assertFalse(needs_processing(Field, *limits, aspect=(4, 3)))


class AllTimeRankConsistencyTests(TestCase):
    """The profile computed rank over every player, the player page over
    `ranked_players()` (hide_pts excluded) — two ranks for one person."""

    def setUp(self):
        self.event = Event.objects.create(
            name="E", place="Brno", points=10, date=timezone.now() - timedelta(days=1))
        UserModel = get_user_model()

        def player(name, points, hide_pts=False):
            lb = LeaderboardUser.objects.create(name=name)
            UserToEvent.objects.create(user=lb, event=self.event, points=points)
            auth = UserModel.objects.create_user(username=name, password="x")
            Profile.objects.create(user=auth, leaderboard_user=lb, hide_pts=hide_pts)
            return lb, auth

        player("hidden_top", 100, hide_pts=True)
        self.lb, self.auth = player("visible", 50)

    def test_profile_and_player_agree(self):
        request = RequestFactory().get("/")
        request.user = self.auth
        self.assertEqual(profile_payload(self.auth, request)["rank"], 1)
        self.assertEqual(player_payload(self.lb, request)["rank"], 1)
        self.assertEqual(all_time_rank(50), 1)


class ActiveCheckinLowerBoundTests(TestCase):
    """The active-check-in feed loaded every past geo-located event and
    filtered in Python; it now stops at the check-in window."""

    def _event(self, name, **kw):
        return Event.objects.create(
            name=name, place="Brno", points=10, latitude=BRNO_LAT, longitude=BRNO_LON,
            checkin_radius=500, **kw)

    def test_long_finished_events_are_not_loaded(self):
        now = timezone.now()
        self._event("Old", date=now - timedelta(days=30))
        self._event("Live", date=now - timedelta(minutes=10))
        self._event("Long with end_date", date=now - timedelta(days=2),
                    end_date=now + timedelta(hours=1))
        names = [e["name"] for e in active_checkin_events(None)]
        self.assertEqual(sorted(names), ["Live", "Long with end_date"])


class SpaNotFoundStatusTests(TestCase):
    """`PageMeta.exists` was computed and ignored: an unknown event slug
    answered 200 with the shell, which search engines file as a soft 404."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        index = os.path.join(tmp.name, "index.html")
        with open(index, "w", encoding="utf-8") as fh:
            fh.write("<html><head><title>x</title></head><body><div id='root'></div></body></html>")
        patcher = mock.patch("mysite.views._resolve_index_path", return_value=index)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_unknown_event_is_404_with_the_shell(self):
        resp = self.client.get("/events/neexistuje")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("root", resp.content.decode())

    def test_home_is_200(self):
        self.assertEqual(self.client.get("/").status_code, 200)
