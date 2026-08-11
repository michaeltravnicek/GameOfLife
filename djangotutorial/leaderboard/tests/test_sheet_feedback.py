"""Google Form column recognition + the feedback it produces during sync."""
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from leaderboard import merging
from leaderboard.models import Event, EventFeedback, User, UserToEvent
from leaderboard.sheet_columns import (
    cell,
    header_map,
    is_negative_attendance,
    parse_rating,
)
from leaderboard.tasks import insert_rec, resolve_player

# The header of the older forms: they ask for a phone number, which the sync no
# longer reads (LeaderboardUser.number is gone), and carry no e-mail column.
HEADER = [
    "Timestamp",
    "Telefon (bez předvolby)",
    "Jméno a příjmení",
    "Zúčastnil/a ses této akce?",
    "Jak hodnotíš tuto akci?",
    "Pokud máš ještě něco na srdci, tady je prostor.",
]

# Newer forms have "Collect email addresses" on and drop the phone question.
HEADER_WITH_EMAIL = [
    "Timestamp",
    "Email Address",
    "Jméno a příjmení",
    "Zúčastnil/a ses této akce?",
    "Jak hodnotíš tuto akci?",
    "Pokud máš ještě něco na srdci, tady je prostor.",
]


class HeaderMapTests(SimpleTestCase):
    def test_recognises_the_real_form_header(self):
        self.assertEqual(
            header_map(HEADER),
            {"name": 2, "attended": 3, "rating": 4, "comment": 5},
        )

    def test_recognises_the_email_column(self):
        self.assertEqual(
            header_map(HEADER_WITH_EMAIL),
            {"email": 1, "name": 2, "attended": 3, "rating": 4, "comment": 5},
        )

    def test_tolerates_sheets_whitespace_and_case(self):
        noisy = ["Timestamp", " JAK  hodnotíš tuto   akci? "]
        self.assertEqual(header_map(noisy), {"rating": 1})

    def test_finds_points_column_by_name(self):
        self.assertEqual(header_map(["Jméno", "Body"]), {"name": 0, "points": 1})

    def test_unknown_headers_are_ignored(self):
        self.assertEqual(header_map(["Timestamp", "Něco jiného"]), {})

    def test_empty_header_row(self):
        self.assertEqual(header_map([]), {})
        self.assertEqual(header_map(None), {})


class CellTests(SimpleTestCase):
    def test_short_row_returns_empty(self):
        # Sheets truncates trailing empty cells, so rows run shorter than the header.
        self.assertEqual(cell(["a", "b"], 5), "")

    def test_absent_column_returns_empty(self):
        self.assertEqual(cell(["a"], None), "")

    def test_strips_whitespace(self):
        self.assertEqual(cell(["  ano  "], 0), "ano")


class ParseRatingTests(SimpleTestCase):
    def test_plain_number(self):
        self.assertEqual(parse_rating("8"), 8)

    def test_ten_is_in_range(self):
        self.assertEqual(parse_rating("10"), 10)

    def test_decorated_values(self):
        self.assertEqual(parse_rating("8/10"), 8)
        self.assertEqual(parse_rating("7 - super"), 7)

    def test_out_of_range_and_junk_rejected(self):
        for raw in ("0", "11", "", None, "skvělé", "-3"):
            self.assertIsNone(parse_rating(raw), f"{raw!r} should not parse")


class NegativeAttendanceTests(SimpleTestCase):
    def test_no_answers(self):
        for raw in ("Ne", "ne", " NE ", "Ne.", "Nezúčastnil/a"):
            self.assertTrue(is_negative_attendance(raw), f"{raw!r} should be negative")

    def test_yes_and_blank_are_not_negative(self):
        # Blank counts as attended: the column post-dates older sheets.
        for raw in ("Ano", "ano", "", None, "Ano, byl jsem"):
            self.assertFalse(is_negative_attendance(raw), f"{raw!r} should not be negative")


class SyncFeedbackTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            sheet_id="s", sheet_list_id="1",
            name="Testovací akce", place="Brno", points=50,
            date=timezone.now() - timedelta(days=2),
        )
        self.cols = header_map(HEADER)

    def row(self, phone="777123456", name="Jan Novák", attended="Ano", rating="", comment=""):
        """A row in the legacy layout. `phone` is still in the sheet, and ignored."""
        return ["2026-01-01", phone, name, attended, rating, comment]

    def test_stores_rating_and_comment(self):
        insert_rec(self.event, self.row(rating="9", comment="Bylo to super"), self.cols)

        fb = EventFeedback.objects.get(event=self.event)
        self.assertEqual(fb.rating, 9)
        self.assertEqual(fb.comment, "Bylo to super")
        self.assertEqual(fb.source, EventFeedback.SOURCE_FORM)

    def test_did_not_attend_awards_no_points_and_no_feedback(self):
        insert_rec(self.event, self.row(attended="Ne", rating="9", comment="mrzí mě to"), self.cols)

        self.assertFalse(UserToEvent.objects.filter(event=self.event).exists())
        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())

    def test_attendance_still_recorded_without_feedback(self):
        insert_rec(self.event, self.row(), self.cols)

        self.assertTrue(UserToEvent.objects.filter(event=self.event).exists())
        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())

    def test_comment_only_row_writes_nothing_when_no_rating_exists(self):
        # rating is required by the model and inventing one would skew averages.
        insert_rec(self.event, self.row(comment="jen komentář"), self.cols)

        self.assertTrue(UserToEvent.objects.filter(event=self.event).exists())
        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())

    def test_comment_only_row_keeps_existing_rating(self):
        insert_rec(self.event, self.row(rating="7"), self.cols)
        insert_rec(self.event, self.row(comment="dodatek"), self.cols)

        fb = EventFeedback.objects.get(event=self.event)
        self.assertEqual(fb.rating, 7)
        self.assertEqual(fb.comment, "dodatek")

    def test_resync_updates_in_place(self):
        insert_rec(self.event, self.row(rating="6", comment="fajn"), self.cols)
        insert_rec(self.event, self.row(rating="9", comment="po rozmyšlení lepší"), self.cols)

        rows = EventFeedback.objects.filter(event=self.event)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows[0].rating, 9)

    def test_form_sync_does_not_overwrite_web_feedback(self):
        user = User.objects.create(name="Jan Novák")
        EventFeedback.objects.create(
            user=user, event=self.event, rating=10, comment="na webu",
            source=EventFeedback.SOURCE_WEB,
        )

        insert_rec(self.event, self.row(rating="3", comment="ze sheetu"), self.cols)

        fb = EventFeedback.objects.get(event=self.event)
        self.assertEqual(fb.rating, 10)
        self.assertEqual(fb.comment, "na webu")

    def test_nameless_row_is_skipped(self):
        # Nothing identifies this response, so it belongs to nobody. Guessing
        # would attach someone else's rating to a real player.
        insert_rec(self.event, self.row(name="", rating="8"), self.cols)

        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())
        self.assertFalse(UserToEvent.objects.filter(event=self.event).exists())

    def test_sheet_without_feedback_columns_still_syncs_attendance(self):
        cols = header_map(["Timestamp", "Telefon (bez předvolby)", "Jméno a příjmení"])
        insert_rec(self.event, ["2026-01-01", "777123456", "Jan Novák"], cols)

        self.assertTrue(UserToEvent.objects.filter(event=self.event).exists())
        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())


class ResolvePlayerTests(TestCase):
    """Who a form response belongs to, now that the phone number is gone.

    Order matters: e-mail is exact, name is a guess. See tasks.resolve_player.
    """

    LEGACY = header_map(HEADER)
    WITH_EMAIL = header_map(HEADER_WITH_EMAIL)

    def legacy_row(self, name="Jan Novák"):
        return ["2026-01-01", "777123456", name, "Ano", "", ""]

    def email_row(self, email="jan@example.com", name="Jan Novák"):
        return ["2026-01-01", email, name, "Ano", "", ""]

    def test_email_row_creates_a_player_with_that_email(self):
        user = resolve_player(self.email_row(), self.WITH_EMAIL)
        self.assertEqual(user.email, "jan@example.com")
        self.assertEqual(user.name, "Jan Novák")

    def test_same_email_returns_the_same_player(self):
        first = resolve_player(self.email_row(), self.WITH_EMAIL)
        second = resolve_player(self.email_row(name="Jan Novak"), self.WITH_EMAIL)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_email_is_matched_case_insensitively(self):
        first = resolve_player(self.email_row(), self.WITH_EMAIL)
        second = resolve_player(self.email_row(email="JAN@Example.com"), self.WITH_EMAIL)
        self.assertEqual(first.pk, second.pk)

    def test_email_row_adopts_the_player_created_from_an_older_sheet(self):
        # The whole point: a person who attended before the form collected
        # e-mails must not end up with two rows and split points.
        old = resolve_player(self.legacy_row(), self.LEGACY)
        new = resolve_player(self.email_row(), self.WITH_EMAIL)
        self.assertEqual(old.pk, new.pk)
        old.refresh_from_db()
        self.assertEqual(old.email, "jan@example.com")

    def test_adoption_does_not_steal_a_player_who_already_has_an_email(self):
        taken = User.objects.create(name="Jan Novák", email="jiny@example.com")
        fresh = resolve_player(self.email_row(), self.WITH_EMAIL)
        self.assertNotEqual(taken.pk, fresh.pk)
        taken.refresh_from_db()
        self.assertEqual(taken.email, "jiny@example.com")

    def test_name_matching_tolerates_case_and_spacing(self):
        first = resolve_player(self.legacy_row(), self.LEGACY)
        second = resolve_player(self.legacy_row(name="  jan   novák "), self.LEGACY)
        self.assertEqual(first.pk, second.pk)

    def test_namesakes_collapse_into_one_player(self):
        # Documented limitation, not an accident: without e-mail the sheet gives
        # us nothing that separates two people called the same thing. This is why
        # "Collect email addresses" is worth switching on for new forms.
        first = resolve_player(self.legacy_row(), self.LEGACY)
        second = resolve_player(self.legacy_row(), self.LEGACY)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_row_with_neither_email_nor_name_is_skipped(self):
        self.assertIsNone(resolve_player(self.legacy_row(name="   "), self.LEGACY))
        self.assertEqual(User.objects.count(), 0)

    def test_email_only_row_falls_back_to_the_email_as_a_name(self):
        user = resolve_player(self.email_row(name=""), self.WITH_EMAIL)
        self.assertEqual(user.name, "jan@example.com")


class ResolvePlayerAfterMergeTests(TestCase):
    """A sheet re-synced after a merge must not undo the merge.

    Sheets stay readable for the archive, so an old form can be synced again at
    any time. If it recreated the row an admin just merged away, the queue would
    refill with the same duplicates and the points would land off the
    leaderboard, on a row nobody can see.
    """

    LEGACY = header_map(HEADER)
    WITH_EMAIL = header_map(HEADER_WITH_EMAIL)

    def setUp(self):
        self.archive = User.objects.create(name="Jan Novák", email="jan@example.com")
        self.target = User.objects.create(name="Honza N")
        merging.merge_players(self.archive, self.target)

    def test_an_email_row_resolves_to_the_merge_target(self):
        row = ["2026-01-01", "jan@example.com", "Jan Novák", "Ano", "", ""]
        # merge_players moved the address across with the history.
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, "jan@example.com")
        self.assertEqual(resolve_player(row, self.WITH_EMAIL), self.target)

    def test_a_name_row_resolves_to_the_merge_target(self):
        row = ["2026-01-01", "777123456", "Jan Novák", "Ano", "", ""]
        self.assertEqual(resolve_player(row, self.LEGACY), self.target)

    def test_the_merged_row_is_not_recreated(self):
        row = ["2026-01-01", "777123456", "Jan Novák", "Ano", "", ""]
        resolve_player(row, self.LEGACY)
        self.assertEqual(User.objects.filter(name="Jan Novák").count(), 0)
        self.assertEqual(User.all_objects.count(), 2)

    def test_points_land_on_the_target(self):
        event = Event.objects.create(
            name="Stará akce", points=15, date=timezone.now() - timedelta(days=10))
        insert_rec(event, ["2026-01-01", "777123456", "Jan Novák", "Ano", "", ""],
                   self.LEGACY)
        self.assertTrue(UserToEvent.objects.filter(user=self.target, event=event).exists())
