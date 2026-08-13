from django.test import TestCase

from leaderboard.utils import parse_int_param


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
