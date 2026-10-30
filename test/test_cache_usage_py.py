"""Cache measurements preserve absence and use an input-weighted ratio."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cli import main
from src.interactive_usage import _claude_usage, _codex_usage, usage_delta
from src.provider_background import read_transcript_outcome
from src.run_usage import extract_run_usage, normalize_usage
from src.session_service import create_session_service


class CacheUsageTests(unittest.TestCase):
    def test_headless_provider_usage_and_missing_split(self):
        cases = [
            ("claude", {"input_tokens": 20, "cache_creation_input_tokens": 10,
                        "cache_read_input_tokens": 70, "output_tokens": 50}, 20, 10, 70, 0.7),
            ("codex", {"input_tokens": 100, "cached_input_tokens": 72, "output_tokens": 50}, 28, None, 72, 0.72),
            ("codex", {"input_tokens": 100, "cached_input_tokens": 60,
                       "cache_write_input_tokens": 10, "output_tokens": 50}, 30, 10, 60, 0.6),
            ("claude", {"input_tokens": 100, "output_tokens": 50}, 100, None, None, None),
            ("codex", {"input_tokens": 100, "output_tokens": 50}, 100, None, None, None),
            ("codex", {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 50}, 100, None, 0, 0.0),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.json"
            for provider, native, uncached, writes, reads, ratio in cases:
                with self.subTest(provider=provider, usage=native):
                    path.write_text(json.dumps({"usage": native}), encoding="utf-8")
                    usage = extract_run_usage(provider, str(path))
                    self.assertEqual(usage["input_tokens"], uncached)
                    self.assertEqual(usage["cache_creation_tokens"], writes)
                    self.assertEqual(usage["cache_read_tokens"], reads)
                    self.assertEqual(usage["output_tokens"], 50)
                    self.assertEqual(usage["cache_hit_ratio"], ratio)

    def test_transcript_readers_do_not_invent_missing_cache_counts(self):
        record = {"type": "assistant", "message": {"id": "one", "usage": {"input_tokens": 100, "output_tokens": 5}}}
        text = json.dumps(record) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.jsonl"
            path.write_text(text, encoding="utf-8")
            usages = [_claude_usage(io.StringIO(text))[0], read_transcript_outcome(str(path))["usage"]]
            codex = {"payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 100, "output_tokens": 5}}}}
            usages.append(_codex_usage(io.StringIO(json.dumps(codex)))[0])
            for usage in usages:
                self.assertIsNone(usage["cache_read_tokens"])
                self.assertIsNone(usage["cache_creation_tokens"])
                self.assertIsNone(usage["cache_hit_ratio"])
                self.assertEqual(usage["output_tokens"], 5)

    def test_codex_transcript_cache_writes_are_separate_from_reads(self):
        record = {"payload": {"type": "token_count", "info": {"total_token_usage": {
            "input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": 10, "output_tokens": 5}}}}
        usage, _model = _codex_usage(io.StringIO(json.dumps(record)))
        self.assertEqual(usage["input_tokens"], 30)
        self.assertEqual(usage["cache_creation_tokens"], 10)
        self.assertEqual(usage["cache_read_tokens"], 60)
        self.assertEqual(usage["total_tokens"], 105)
        self.assertEqual(usage["cache_hit_ratio"], 0.6)

    def test_ratio_is_recomputed_from_turn_delta_and_zero_input_is_unknown(self):
        before = normalize_usage(input_tokens=10, cache_read_tokens=90, output_tokens=10)
        after = normalize_usage(input_tokens=40, cache_read_tokens=160, output_tokens=500)
        self.assertEqual(usage_delta(after, before)["cache_hit_ratio"], 0.7)
        self.assertIsNone(normalize_usage(input_tokens=0, cache_read_tokens=0)["cache_hit_ratio"])

    def test_history_and_stats_json_keep_legacy_totals_and_add_cache_comparisons(self):
        with tempfile.TemporaryDirectory() as directory:
            service = create_session_service({"base_dir": directory})
            service["create_session"]("work", "codex")
            # Unequal input volumes expose accidental averaging of percentages.
            for usage, parent in [
                (normalize_usage(input_tokens=10, cache_read_tokens=90, output_tokens=7), None),
                (normalize_usage(input_tokens=720, cache_read_tokens=180, output_tokens=3), "parent"),
                (normalize_usage(input_tokens=50, output_tokens=1), None),
            ]:
                service["record_launch_history"]("work", {
                    "usage": usage, "parent_run_id": parent, "status": "success",
                    "usage_model": "gpt-6.1-sol", "cwd": directory,
                })

            def invoke(args):
                output = io.StringIO()
                self.assertEqual(main(args, {"stdout": output, "stderr": io.StringIO(), "service": service}), 0)
                return output.getvalue()

            history = json.loads(invoke(["history", "--json"]))["history"]
            self.assertEqual(len(history), 3)
            self.assertEqual({e["parent_run_id"] for e in history}, {None, "parent"})
            self.assertIn("cache_hit_ratio", history[0]["usage"])
            self.assertIn("cache n/d", invoke(["history"]))
            self.assertIn("cache 90 %", invoke(["history"]))
            for group in ("session", "project", "model"):
                with self.subTest(group=group):
                    payload = json.loads(invoke(["stats", "--by", group, "--json"]))
                    for summary in (payload["stats"][0], payload["totals"]):
                        self.assertEqual(summary["input_tokens"], 780)
                        self.assertEqual(summary["total_tokens"], 1061)
                        self.assertEqual(summary["cache_hit_ratio"], 0.27)
                        cache = summary["cache_usage"]
                        self.assertEqual(cache["cache_read_tokens"], 270)
                        self.assertIsNone(cache["cache_creation_tokens"])
                        self.assertEqual(cache["measured_runs"], 2)
                        self.assertEqual(cache["measured_input_tokens"], 1000)
                        self.assertEqual(summary["run_types"]["continued"]["runs"], 1)
                        self.assertEqual(summary["run_types"]["continued"]["cache_hit_ratio"], 0.2)
                        self.assertEqual(summary["run_types"]["cold"]["runs"], 2)
                        self.assertEqual(summary["run_types"]["cold"]["cache_hit_ratio"], 0.9)
            self.assertIn("cache 27 %", invoke(["stats"]))

    def test_stats_missing_split_is_null_and_text_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            service = create_session_service({"base_dir": directory})
            service["create_session"]("work", "claude")
            service["record_launch_history"]("work", {"usage": normalize_usage(input_tokens=4, output_tokens=2)})
            output = io.StringIO()
            self.assertEqual(main(["stats", "--json"], {"service": service, "stdout": output, "stderr": io.StringIO()}), 0)
            payload = json.loads(output.getvalue())
            for summary in (payload["stats"][0], payload["totals"]):
                self.assertIsNone(summary["cache_hit_ratio"])
                self.assertIsNone(summary["cache_usage"]["cache_read_tokens"])
                self.assertIsNone(summary["cache_usage"]["cache_creation_tokens"])
                # Existing numeric aggregate fields retain their previous contract.
                self.assertEqual(summary["cache_read_tokens"], 0)
