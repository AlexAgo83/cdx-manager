"""Reset times as ISO 8601 next to the display strings."""

import os
import time
import unittest

from src.session_status import reset_iso


@unittest.skipUnless(hasattr(time, "tzset"), "needs time.tzset to pin the local zone")
class ResetIsoTests(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Paris"
        time.tzset()

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def test_a_display_reset_gets_the_year_and_offset_of_the_reading(self):
        self.assertEqual(reset_iso("Oct 25 12:35", "2026-10-25T07:35:53+01:00"), "2026-10-25T12:35:00+01:00")

    def test_a_january_reset_read_in_december_is_next_year(self):
        self.assertEqual(reset_iso("Jan 2 09:00", "2026-12-30T10:00:00+01:00"), "2027-01-02T09:00:00+01:00")

    def test_a_reset_after_a_dst_change_carries_its_own_offset(self):
        self.assertEqual(reset_iso("Oct 26 09:00", "2026-10-24T10:00:00+02:00"), "2026-10-26T09:00:00+01:00")

    def test_a_reset_without_a_time_stays_a_date(self):
        self.assertEqual(reset_iso("Nov 1", "2026-10-25T07:35:53+01:00"), "2026-11-01")


class ResetIsoShapeTests(unittest.TestCase):
    def test_unknown_shapes_are_absent_rather_than_guessed(self):
        for value in (None, "", "soon", "Foo 3 10:00", "Oct x 10:00", "Feb 30 10:00", "Oct 3 25:00"):
            self.assertIsNone(reset_iso(value, "2026-10-25T07:35:53+01:00"), value)


if __name__ == "__main__":
    unittest.main()
