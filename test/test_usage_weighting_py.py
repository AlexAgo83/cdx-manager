"""Rank sessions by what they cost, not by how many tokens they moved."""

import unittest
from datetime import date, datetime

from src.commands.status import _summarize_stats
from src.run_usage import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    DEFAULT_TOKEN_PRICES,
    TOKEN_PRICES_MAX_AGE_DAYS,
    TOKEN_PRICES_REVIEWED,
    estimate_cost,
    normalize_usage,
    output_multiplier,
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

    def test_the_output_ratio_follows_the_model_that_served_the_run(self):
        # The one multiplier that differs by model is output. Weighing every
        # Codex run at 5x under-stated Terra output.
        usage = normalize_usage(output_tokens=1000)
        self.assertEqual(weighted_usage(usage, "claude-opus-5"), 5000)
        self.assertEqual(weighted_usage(usage, "gpt-5.6-terra"), 6000)

    def test_the_cache_multipliers_are_the_same_on_both_vendors(self):
        for model in ("claude-opus-5", "gpt-5.6-terra"):
            rate = DEFAULT_TOKEN_PRICES[model]
            cost = estimate_cost(normalize_usage(cache_read_tokens=1_000_000), model)
            self.assertAlmostEqual(cost, rate["input"] * CACHE_READ_MULTIPLIER)
            cost = estimate_cost(normalize_usage(cache_creation_tokens=1_000_000), model)
            self.assertAlmostEqual(cost, rate["input"] * CACHE_WRITE_MULTIPLIER)

    def test_reasoning_is_excluded_because_it_is_a_subset_of_output(self):
        without = weighted_usage(normalize_usage(output_tokens=10))
        with_reasoning = weighted_usage(normalize_usage(output_tokens=10, reasoning_tokens=4))
        self.assertEqual(without, with_reasoning)

    def test_absence_weighs_nothing_rather_than_zero(self):
        self.assertIsNone(weighted_usage(normalize_usage()))
        self.assertIsNone(weighted_usage(None))

    def test_a_cache_read_is_worth_a_fiftieth_of_an_output_token(self):
        self.assertEqual(output_multiplier("claude-opus-5") / CACHE_READ_MULTIPLIER, 50)


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

    def test_each_class_is_priced_directly_rather_than_through_the_weighting(self):
        # The weighted shortcut was only correct while every model shared one
        # output ratio. It does not, so cost prices each class at its own rate.
        usage = normalize_usage(input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertAlmostEqual(estimate_cost(usage, "claude-opus-5"), 30.0)
        self.assertAlmostEqual(estimate_cost(usage, "gpt-5.6-terra"), 14.0)

    def test_current_codex_and_claude_models_are_priced(self):
        table = DEFAULT_TOKEN_PRICES
        expected = {
            "gpt-6-astra": {"input": 10.0, "output": 50.0},
            "gpt-5.6": {"input": 4.0, "output": 20.0},
            "gpt-5.5": {"input": 5.0, "output": 30.0},
            "gpt-5.5-2026-04-23": {"input": 5.0, "output": 30.0},
            "gpt-5.4": {"input": 2.5, "output": 15.0},
            "gpt-5.4-mini": {"input": 0.75, "output": 4.5},
            "gpt-5.4-nano": {"input": 0.2, "output": 1.25},
            "gpt-5.3-codex": {"input": 1.75, "output": 14.0},
            "claude-sonnet-5": {"input": 2.0, "output": 10.0},
            "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
            "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
            "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
        }
        for model, rate in expected.items():
            self.assertEqual(table[model], rate, model)

    def test_an_unknown_model_is_unpriced_rather_than_assumed(self):
        # Charging a default tier would turn "cdx does not know" into a number
        # someone might act on.
        usage = normalize_usage(output_tokens=1_000)
        self.assertIsNone(estimate_cost(usage, "some-future-model"))
        self.assertIsNone(estimate_cost(usage, None))

    def test_unmeasured_usage_is_unpriced(self):
        self.assertIsNone(estimate_cost(normalize_usage(), "claude-opus-5"))

    def test_prices_come_from_configuration_not_a_code_edit(self):
        table, source = token_prices(
            {"CDX_TOKEN_PRICES": '{"gpt-5.7": {"input": 3, "output": 18}}'})
        self.assertEqual(table["gpt-5.7"], {"input": 3.0, "output": 18.0})
        self.assertEqual(source, "CDX_TOKEN_PRICES")
        # A model the override does not mention keeps its built-in price.
        self.assertEqual(table["claude-haiku-4-5"]["input"], 1.0)

    def test_a_malformed_override_falls_back_and_says_so(self):
        table, source = token_prices({"CDX_TOKEN_PRICES": "not json"})
        self.assertEqual(table["claude-opus-5"]["input"], 5.0)
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
        # wants. Any model can fall out of the table -- vendors ship faster
        # than this file is reviewed.
        rows = _summarize_stats([
            {**_entry("work", output_tokens=10), "usage_model": "gpt-6-unreleased"},
            {**_entry("digital", output_tokens=10), "usage_model": "claude-opus-5"},
        ])
        by_name = {row["session_name"]: row for row in rows}
        self.assertEqual(by_name["work"]["unpriced_models"], ["gpt-6-unreleased"])
        self.assertEqual(by_name["work"]["priced_runs"], 0)
        self.assertEqual(by_name["digital"]["unpriced_models"], [])
        self.assertEqual(by_name["digital"]["priced_runs"], 1)

    def test_a_run_with_no_model_at_all_is_not_reported_as_unpriced(self):
        # Nothing to name, and nothing the operator could add to the table.
        rows = _summarize_stats([_entry("work", output_tokens=10)])
        self.assertEqual(rows[0]["unpriced_models"], [])


class PriceTableFreshnessTests(unittest.TestCase):
    """Prices are the one input here that rots on its own.

    The ratios hold across vendors and the arithmetic does not drift, but a
    vendor can reprice any morning and nothing in cdx would notice. This test
    is the noticing: it fails on a schedule so somebody re-checks, and the fix
    is to run scripts/check_token_prices.py and either confirm the table or
    correct it -- then cut a corrective release.

    Offline and deterministic on purpose. A test that fetched vendor pages
    would fail for network reasons and be muted within a month.
    """

    def test_the_table_has_been_reviewed_recently_enough(self):
        reviewed = datetime.strptime(TOKEN_PRICES_REVIEWED, "%Y-%m-%d").date()
        age = (date.today() - reviewed).days
        self.assertLessEqual(
            age, TOKEN_PRICES_MAX_AGE_DAYS,
            f"Token prices were last reviewed {age} days ago "
            f"({TOKEN_PRICES_REVIEWED}). Run scripts/check_token_prices.py and "
            f"follow logics/runbook/run_005_maintaining_the_token_price_table.md.")

    def test_the_review_date_is_not_in_the_future(self):
        # A future date would silence the check indefinitely. One day of slack,
        # because "today" differs by timezone and a reviewer west of whoever
        # set the date must not see a failing suite.
        reviewed = datetime.strptime(TOKEN_PRICES_REVIEWED, "%Y-%m-%d").date()
        self.assertLessEqual((reviewed - date.today()).days, 1)

    def test_every_priced_model_carries_both_rates(self):
        for model, rate in DEFAULT_TOKEN_PRICES.items():
            self.assertEqual(set(rate), {"input", "output"}, model)
            self.assertGreater(rate["input"], 0, model)
            self.assertGreaterEqual(rate["output"], rate["input"], model)
