"""Google Form column recognition + the feedback it produces during sync."""
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from leaderboard.models import Event, EventFeedback, User, UserToEvent
from leaderboard.sheet_columns import (
    cell,
    header_map,
    is_negative_attendance,
    parse_rating,
)
from leaderboard.tasks import insert_rec

# The real form export header.
HEADER = [
    "Timestamp",
    "Telefon (bez předvolby)",
    "Jméno a příjmení",
    "Zúčastnil/a ses této akce?",
    "Jak hodnotíš tuto akci?",
    "Pokud máš ještě něco na srdci, tady je prostor.",
]


class HeaderMapTests(SimpleTestCase):
    def test_recognises_the_real_form_header(self):
        self.assertEqual(
            header_map(HEADER),
            {"attended": 3, "rating": 4, "comment": 5},
        )

    def test_tolerates_sheets_whitespace_and_case(self):
        noisy = ["Timestamp", " JAK  hodnotíš tuto   akci? "]
        self.assertEqual(header_map(noisy), {"rating": 1})

    def test_finds_points_column_by_name(self):
        self.assertEqual(header_map(["Jméno", "Body"]), {"points": 1})

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
        user = User.objects.create(number=777123456, name="Jan Novák")
        EventFeedback.objects.create(
            user=user, event=self.event, rating=10, comment="na webu",
            source=EventFeedback.SOURCE_WEB,
        )

        insert_rec(self.event, self.row(rating="3", comment="ze sheetu"), self.cols)

        fb = EventFeedback.objects.get(event=self.event)
        self.assertEqual(fb.rating, 10)
        self.assertEqual(fb.comment, "na webu")

    def test_invalid_phone_row_is_skipped(self):
        insert_rec(self.event, self.row(phone="123", rating="8"), self.cols)

        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())

    def test_sheet_without_feedback_columns_still_syncs_attendance(self):
        cols = header_map(["Timestamp", "Telefon (bez předvolby)", "Jméno a příjmení"])
        insert_rec(self.event, ["2026-01-01", "777123456", "Jan Novák"], cols)

        self.assertTrue(UserToEvent.objects.filter(event=self.event).exists())
        self.assertFalse(EventFeedback.objects.filter(event=self.event).exists())
