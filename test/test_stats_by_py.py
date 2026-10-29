"""cdx stats grouped by project or model: same accounting, another key."""

import unittest

from src.cli_args import _parse_stats_args
from src.commands.status import _project_labels, _stats_group, _summarize_stats
from src.errors import CdxError
from src.run_usage import normalize_usage


def _entry(session, cwd, model, cost_tokens, provider="claude"):
    return {"session_name": session, "provider": provider, "status": "success", "cwd": cwd,
            "usage_model": model, "usage": normalize_usage(input_tokens=cost_tokens, output_tokens=0)}


class StatsByTests(unittest.TestCase):
    def test_runs_regroup_by_project_folder_and_by_model(self):
        entries = [_entry("work", "/r/cts", "claude-opus-5-5", 100), _entry("main", "/r/cts/", "claude-opus-5-5", 50),
                   _entry("work", "/r/mpt", "claude-sonnet-5-5", 10)]
        by_project = _summarize_stats([{**e, "session_name": _stats_group(e, "project")} for e in entries])
        self.assertEqual([(r["session_name"], r["input_tokens"]) for r in by_project], [("/r/cts", 150), ("/r/mpt", 10)])
        by_model = _summarize_stats([{**e, "session_name": _stats_group(e, "model")} for e in entries])
        self.assertEqual({r["session_name"] for r in by_model}, {"claude-opus-5-5", "claude-sonnet-5-5"})

    def test_same_named_folders_stay_apart_and_keep_every_provider(self):
        entries = [_entry("work", "/a/app", "m", 100), _entry("cx", "/a/app", "m", 50, provider="codex"),
                   _entry("work", "/b/app", "m", 10)]
        rows = _summarize_stats([{**e, "session_name": _stats_group(e, "project")} for e in entries])
        self.assertEqual([(r["session_name"], r["provider"]) for r in rows], [("/a/app", "claude+codex"), ("/b/app", "claude")])
        self.assertEqual(_project_labels(["/a/app", "/b/app", "/c/web", "/x/b/app"]),
                         {"/a/app": "a/app", "/b/app": "/b/app", "/c/web": "web", "/x/b/app": "x/b/app"})

    def test_by_takes_only_known_groupings(self):
        self.assertEqual(_parse_stats_args(["--by", "project"])["by"], "project")
        self.assertEqual(_parse_stats_args([])["by"], "session")
        with self.assertRaises(CdxError):
            _parse_stats_args(["--by", "colour"])

    def test_claude_context_variant_shares_base_model_row_and_keeps_cost(self):
        entries = [_entry("work", "/r", "claude-opus-5-5", 100),
                   _entry("work", "/r", "claude-opus-5-5[1m]", 50)]
        rows = _summarize_stats([{**e, "session_name": _stats_group(e, "model")} for e in entries])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_name"], "claude-opus-5-5")
        self.assertEqual(rows[0]["priced_runs"], 2)
        self.assertEqual(rows[0]["input_tokens"], 150)
        self.assertEqual(entries[1]["usage_model"], "claude-opus-5-5[1m]")


if __name__ == "__main__":
    unittest.main()
