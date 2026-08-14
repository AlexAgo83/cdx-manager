"""Usage recorded before the field definition existed is dropped, not shown.

Those figures are not imprecise, they are fictitious: on a real store one
session reported 206.6M cached tokens for a period in which its own
conversation consumed 33,608. They cannot be recomputed -- a run's true usage
is the increment its transcript gained while it ran, and nothing recorded that
-- so the figures go and the run stays.
"""

import os
import tempfile
import unittest

from src.run_usage import normalize_usage
from src.session_store import create_session_store


class DropUnvouchedUsageTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.base = self._dir.name
        self.store = create_session_store(self.base)
        self.addCleanup(self._dir.cleanup)

    def _legacy(self, name, cached):
        return {"session_name": name, "provider": "claude", "status": "success",
                "duration_ms": 1000, "started_at": "2026-08-01T10:00:00",
                "usage": {"input_tokens": 2, "cached_input_tokens": cached,
                          "output_tokens": 4, "reasoning_tokens": None,
                          "total_tokens": 6}}

    def _current(self, name):
        return {"session_name": name, "provider": "claude", "status": "success",
                "duration_ms": 1000, "started_at": "2026-08-14T10:00:00",
                "usage": normalize_usage(input_tokens=2, cache_read_tokens=9, output_tokens=4),
                "usage_cumulative": normalize_usage(input_tokens=2, cache_read_tokens=9,
                                                    output_tokens=4)}

    def _headless(self, name):
        # A real headless record: full field set, and no cumulative because
        # that path never had one. It must not be mistaken for a legacy record.
        return {"session_name": name, "provider": "codex", "status": "success",
                "usage": normalize_usage(input_tokens=5, output_tokens=1)}

    def _history(self):
        return self.store["list_launch_history"](limit=0)

    def test_a_dry_run_counts_without_touching_anything(self):
        self.store["append_launch_history"](self._legacy("digital", 198_926_945))
        report = self.store["drop_unvouched_usage"](dry_run=True)

        self.assertEqual(report["dropped"], 1)
        self.assertTrue(report["dry_run"])
        self.assertIsNotNone(self._history()[0]["usage"])

    def test_legacy_usage_goes_and_the_run_stays(self):
        self.store["append_launch_history"](self._legacy("digital", 198_926_945))
        self.store["drop_unvouched_usage"](dry_run=False)

        entry = self._history()[0]
        self.assertIsNone(entry.get("usage"))
        self.assertEqual(entry["usage_dropped_reason"], "recorded_before_field_definition")
        # A run that happened still happened.
        self.assertEqual(entry["status"], "success")
        self.assertEqual(entry["duration_ms"], 1000)
        self.assertEqual(entry["started_at"], "2026-08-01T10:00:00")

    def test_records_written_after_the_fix_are_untouched(self):
        self.store["append_launch_history"](self._current("digital"))
        self.store["drop_unvouched_usage"](dry_run=False)

        entry = self._history()[0]
        self.assertEqual(entry["usage"]["cache_read_tokens"], 9)
        self.assertNotIn("usage_dropped_reason", entry)

    def test_a_headless_record_is_not_mistaken_for_a_legacy_one(self):
        # It carries no cumulative, which is exactly why the discriminator is
        # the field set rather than the cumulative's presence.
        self.store["append_launch_history"](self._headless("main"))
        report = self.store["drop_unvouched_usage"](dry_run=False)

        self.assertEqual(report["dropped"], 0)
        self.assertEqual(self._history()[0]["usage"]["input_tokens"], 5)

    def test_a_mixed_history_drops_only_the_unvouched_half(self):
        self.store["append_launch_history"](self._legacy("digital", 5_044_782))
        self.store["append_launch_history"](self._current("digital"))
        self.store["append_launch_history"](self._legacy("digital", 198_926_945))

        report = self.store["drop_unvouched_usage"](dry_run=False)

        self.assertEqual(report["scanned"], 3)
        self.assertEqual(report["dropped"], 2)
        surviving = [e for e in self._history() if e.get("usage")]
        self.assertEqual(len(surviving), 1)

    def test_an_unreadable_line_is_left_exactly_as_it_was(self):
        self.store["append_launch_history"](self._legacy("digital", 10))
        path = os.path.join(self.base, "state", "launch_history.jsonl")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"broken": \n')

        self.store["drop_unvouched_usage"](dry_run=False)

        with open(path, encoding="utf-8") as handle:
            self.assertIn('{"broken": \n', handle.read())

    def test_an_absent_history_is_not_an_error(self):
        empty = create_session_store(tempfile.mkdtemp())
        self.assertEqual(empty["drop_unvouched_usage"](dry_run=False)["scanned"], 0)


if __name__ == "__main__":
    unittest.main()


class UnvouchedUsageIsExcludedFromStatsTests(unittest.TestCase):
    """The exclusion is automatic, and it says so.

    An earlier draft of this work made it an explicit `cdx repair` step. That
    was wrong: an upgrade would have left the fictitious figures on screen
    until somebody remembered a command.
    """

    def _summarize(self, entries):
        from src.commands.status import _summarize_stats

        return {row["session_name"]: row for row in _summarize_stats(entries)}

    def _legacy_entry(self):
        return {"session_name": "digital", "provider": "claude", "status": "success",
                "usage": {"input_tokens": 2, "cached_input_tokens": 198_926_945,
                          "output_tokens": 4, "total_tokens": 6}}

    def _current_entry(self):
        return {"session_name": "digital", "provider": "claude", "status": "success",
                "usage": normalize_usage(input_tokens=2, cache_read_tokens=9, output_tokens=4)}

    def test_unvouched_usage_is_excluded_without_anyone_running_a_command(self):
        rows = self._summarize([self._legacy_entry()])
        self.assertEqual(rows["digital"]["total_tokens"], 0)
        self.assertEqual(rows["digital"]["usage_runs"], 0)

    def test_the_exclusion_is_counted_so_it_is_not_silent(self):
        rows = self._summarize([self._legacy_entry(), self._legacy_entry()])
        self.assertEqual(rows["digital"]["unvouched_runs"], 2)

    def test_vouched_usage_in_the_same_session_still_counts(self):
        rows = self._summarize([self._legacy_entry(), self._current_entry()])
        self.assertEqual(rows["digital"]["unvouched_runs"], 1)
        self.assertEqual(rows["digital"]["usage_runs"], 1)
        self.assertEqual(rows["digital"]["cache_read_tokens"], 9)
        self.assertEqual(rows["digital"]["total_tokens"], 15)

    def test_the_stored_record_is_left_alone(self):
        # Filtering, not mutation: if the marker ever proves wrong, nothing
        # has been destroyed.
        entry = self._legacy_entry()
        self._summarize([entry])
        self.assertEqual(entry["usage"]["cached_input_tokens"], 198_926_945)
