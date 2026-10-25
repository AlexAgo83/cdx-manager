"""When an account empties at the pace it used since its window opened."""

import unittest
from datetime import timedelta

from src.session_status import runs_out_at

FIVE_HOURS = timedelta(hours=5)


class RunsOutTests(unittest.TestCase):
    def test_a_fast_pace_runs_out_before_the_reset(self):
        # Opened 07:00, read 09:00 with 50% used: the other 50% lasts 2h more, so 11:00, before the 12:00 reset.
        self.assertEqual(runs_out_at(50, "2026-10-25T12:00:00+01:00", FIVE_HOURS, "2026-10-25T09:00:00+01:00"),
                         "2026-10-25T11:00:00+01:00")

    def test_a_pace_that_lasts_until_the_reset_has_no_forecast(self):
        self.assertIsNone(runs_out_at(80, "2026-10-25T12:00:00+01:00", FIVE_HOURS, "2026-10-25T09:00:00+01:00"))

    def test_missing_or_meaningless_figures_have_no_forecast(self):
        for args in ((100, "2026-10-25T12:00:00+01:00"), (0, "2026-10-25T12:00:00+01:00"),
                     (None, "2026-10-25T12:00:00+01:00"), (50, None), (50, "2026-10-25")):
            self.assertIsNone(runs_out_at(args[0], args[1], FIVE_HOURS, "2026-10-25T09:00:00+01:00"), args)


if __name__ == "__main__":
    unittest.main()
