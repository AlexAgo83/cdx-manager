"""cdx stats grouped by project or model: same accounting, another key."""

import unittest

from src.cli_args import _parse_stats_args
from src.commands.status import _stats_group, _summarize_stats
from src.errors import CdxError
from src.run_usage import normalize_usage


def _entry(session, cwd, model, cost_tokens):
    return {"session_name": session, "provider": "claude", "status": "success", "cwd": cwd,
            "usage_model": model, "usage": normalize_usage(input_tokens=cost_tokens, output_tokens=0)}


class StatsByTests(unittest.TestCase):
    def test_runs_regroup_by_project_folder_and_by_model(self):
        entries = [_entry("work", "/r/cts", "claude-opus-5-5", 100), _entry("main", "/r/cts/", "claude-opus-5-5", 50),
                   _entry("work", "/r/mpt", "claude-sonnet-5-5", 10)]
        by_project = _summarize_stats([{**e, "session_name": _stats_group(e, "project")} for e in entries])
        self.assertEqual([(r["session_name"], r["input_tokens"]) for r in by_project], [("cts", 150), ("mpt", 10)])
        by_model = _summarize_stats([{**e, "session_name": _stats_group(e, "model")} for e in entries])
        self.assertEqual({r["session_name"] for r in by_model}, {"claude-opus-5-5", "claude-sonnet-5-5"})

    def test_by_takes_only_known_groupings(self):
        self.assertEqual(_parse_stats_args(["--by", "project"])["by"], "project")
        self.assertEqual(_parse_stats_args([])["by"], "session")
        with self.assertRaises(CdxError):
            _parse_stats_args(["--by", "colour"])


if __name__ == "__main__":
    unittest.main()
