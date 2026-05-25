from django.test import TestCase

from leaderboard.utils import parse_int_param, parse_phone_number


class ParseIntParamTests(TestCase):
    def test_parses_valid_int(self):
        self.assertEqual(parse_int_param("5", 10), 5)

    def test_falls_back_on_garbage(self):
        self.assertEqual(parse_int_param("xxx", 10), 10)
        self.assertEqual(parse_int_param(None, 10), 10)

    def test_clamps_max(self):
        self.assertEqual(parse_int_param("999", 10, max_val=100), 100)

    def test_clamps_min(self):
        self.assertEqual(parse_int_param("-5", 10, min_val=0), 0)

    def test_no_clamp_without_bounds(self):
        self.assertEqual(parse_int_param("999", 10), 999)


class ParsePhoneNumberTests(TestCase):
    def test_valid_9_digits(self):
        self.assertEqual(parse_phone_number("731005976"), 731005976)

    def test_strips_formatting(self):
        self.assertEqual(parse_phone_number("731 005 976"), 731005976)

    def test_drops_420_prefix(self):
        self.assertEqual(parse_phone_number("+420 731 005 976"), 731005976)

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_phone_number("12345"))
        self.assertIsNone(parse_phone_number(""))
        self.assertIsNone(parse_phone_number(None))
