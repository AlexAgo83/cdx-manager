"""Rank sessions by what they cost, not by how many tokens they moved."""

import unittest

from src.commands.status import _summarize_stats
from src.run_usage import (
    TOKEN_PRICES_REVIEWED,
    USAGE_WEIGHTS,
    estimate_cost,
    normalize_usage,
    token_prices,
    weighted_usage,
)


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


class CostEstimateTests(unittest.TestCase):
    """Cost is the weighted figure times one number per model."""

    def test_a_known_model_prices_the_weighted_figure(self):
        usage = normalize_usage(input_tokens=1_000_000)
        self.assertAlmostEqual(
            estimate_cost(usage, "claude-opus-5", {"claude-opus-5": 5.0}), 5.0)

    def test_cache_reads_cost_a_tenth_of_uncached_input(self):
        self.assertAlmostEqual(
            estimate_cost(normalize_usage(cache_read_tokens=1_000_000),
                          "claude-opus-5", {"claude-opus-5": 5.0}),
            0.5)

    def test_an_unknown_model_is_unpriced_rather_than_assumed(self):
        # Charging a default tier would turn "cdx does not know" into a number
        # someone might act on.
        usage = normalize_usage(output_tokens=1_000)
        self.assertIsNone(estimate_cost(usage, "some-future-model", {"claude-opus-5": 5.0}))
        self.assertIsNone(estimate_cost(usage, None, {"claude-opus-5": 5.0}))

    def test_unmeasured_usage_is_unpriced(self):
        self.assertIsNone(estimate_cost(normalize_usage(), "claude-opus-5", {"claude-opus-5": 5.0}))

    def test_prices_come_from_configuration_not_a_code_edit(self):
        table, source = token_prices({"CDX_TOKEN_PRICES": '{"claude-opus-5": 99.0}'})
        self.assertEqual(table["claude-opus-5"], 99.0)
        self.assertEqual(source, "CDX_TOKEN_PRICES")
        # A model the override does not mention keeps its built-in price.
        self.assertEqual(table["claude-haiku-4-5"], 1.0)

    def test_a_malformed_override_falls_back_and_says_so(self):
        table, source = token_prices({"CDX_TOKEN_PRICES": "not json"})
        self.assertEqual(table["claude-opus-5"], 5.0)
        self.assertIn("ignored", source)

    def test_the_default_table_states_when_it_was_reviewed(self):
        _table, source = token_prices({})
        self.assertIn(TOKEN_PRICES_REVIEWED, source)


if __name__ == "__main__":
    unittest.main()


class UnpricedModelReportingTests(unittest.TestCase):
    def test_a_model_with_no_price_is_named_rather_than_silently_dashed(self):
        # The operator asked why Codex rows showed no cost. A bare "-" cannot
        # answer that; the model name can, and it is the key CDX_TOKEN_PRICES
        # wants.
        rows = _summarize_stats([
            {**_entry("work", output_tokens=10), "usage_model": "gpt-5.6-terra"},
            {**_entry("digital", output_tokens=10), "usage_model": "claude-opus-5"},
        ])
        by_name = {row["session_name"]: row for row in rows}
        self.assertEqual(by_name["work"]["unpriced_models"], ["gpt-5.6-terra"])
        self.assertEqual(by_name["work"]["priced_runs"], 0)
        self.assertEqual(by_name["digital"]["unpriced_models"], [])
        self.assertEqual(by_name["digital"]["priced_runs"], 1)

    def test_a_run_with_no_model_at_all_is_not_reported_as_unpriced(self):
        # Nothing to name, and nothing the operator could add to the table.
        rows = _summarize_stats([_entry("work", output_tokens=10)])
        self.assertEqual(rows[0]["unpriced_models"], [])
