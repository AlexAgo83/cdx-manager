"""Rank sessions by what they cost, not by how many tokens they moved."""

import unittest

from src.commands.status import _summarize_stats
from src.run_usage import USAGE_WEIGHTS, normalize_usage, weighted_usage


def _entry(session, **parts):
    return {"session_name": session, "provider": "claude", "status": "success",
            "usage": normalize_usage(**parts)}


class WeightedUsageTests(unittest.TestCase):
    def test_the_four_classes_are_weighted_by_their_published_ratios(self):
        usage = normalize_usage(input_tokens=100, cache_creation_tokens=100,
                                cache_read_tokens=100, output_tokens=100)
        self.assertEqual(weighted_usage(usage), 100 + 125 + 10 + 500)

    def test_reasoning_is_excluded_because_it_is_a_subset_of_output(self):
        without = weighted_usage(normalize_usage(output_tokens=10))
        with_reasoning = weighted_usage(normalize_usage(output_tokens=10, reasoning_tokens=4))
        self.assertEqual(without, with_reasoning)

    def test_absence_weighs_nothing_rather_than_zero(self):
        self.assertIsNone(weighted_usage(normalize_usage()))
        self.assertIsNone(weighted_usage(None))

    def test_a_cache_read_is_worth_a_fiftieth_of_an_output_token(self):
        self.assertEqual(USAGE_WEIGHTS["output_tokens"] / USAGE_WEIGHTS["cache_read_tokens"], 50)


class StatsRankingTests(unittest.TestCase):
    def test_a_cache_heavy_session_ranks_below_one_that_generated_more(self):
        # Equal raw totals, opposite costs. Ranking on the raw total put the
        # replayed cache first, which is the ordering this fixes.
        rows = _summarize_stats([
            _entry("replayer", cache_read_tokens=1_000_000),
            _entry("generator", input_tokens=500_000, output_tokens=500_000),
        ])

        self.assertEqual(rows[0]["total_tokens"], rows[1]["total_tokens"])
        self.assertEqual([row["session_name"] for row in rows], ["generator", "replayer"])

    def test_identical_raw_totals_still_produce_different_weighted_figures(self):
        rows = {row["session_name"]: row for row in _summarize_stats([
            _entry("replayer", cache_read_tokens=1_000_000),
            _entry("generator", input_tokens=500_000, output_tokens=500_000),
        ])}
        self.assertEqual(rows["replayer"]["weighted_tokens"], 100_000)
        self.assertEqual(rows["generator"]["weighted_tokens"], 3_000_000)


if __name__ == "__main__":
    unittest.main()
