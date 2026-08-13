import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from src import interactive_usage
from src.interactive_usage import MAX_TRANSCRIPT_BYTES, extract_interactive_usage


class InteractiveUsageTests(unittest.TestCase):
    def _write(self, root, relative, records):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
        return path

    def test_reads_latest_codex_cumulative_snapshot(self):
        with tempfile.TemporaryDirectory() as home:
            self._write(home, "sessions/2026/08/one.jsonl", [
                {"payload": {"type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 10, "cached_input_tokens": 50, "output_tokens": 2,
                    "reasoning_output_tokens": 1, "total_tokens": 12}}}},
                {"payload": {"type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 20, "cached_input_tokens": 90, "output_tokens": 4,
                    "reasoning_output_tokens": 2, "total_tokens": 24}}}},
            ])
            usage, _path = extract_interactive_usage("codex", home)
            self.assertEqual(usage, {"input_tokens": 20, "cached_input_tokens": 90,
                                    "output_tokens": 4, "reasoning_tokens": 2, "total_tokens": 24})

    def test_sums_unique_claude_assistant_messages(self):
        with tempfile.TemporaryDirectory() as home:
            self._write(home, ".claude/projects/repo/session.jsonl", [
                {"type": "assistant", "uuid": "one", "message": {"usage": {
                    "input_tokens": 2, "cache_creation_input_tokens": 3,
                    "cache_read_input_tokens": 5, "output_tokens": 7}}},
                {"type": "assistant", "uuid": "one", "message": {"usage": {
                    "input_tokens": 99, "output_tokens": 99}}},
                {"type": "assistant", "uuid": "two", "message": {"usage": {
                    "input_tokens": 11, "output_tokens": 13}}},
            ])
            usage, _path = extract_interactive_usage("claude", home)
            self.assertEqual(usage, {"input_tokens": 13, "cached_input_tokens": 8,
                                    "output_tokens": 20, "reasoning_tokens": None, "total_tokens": 33})

    def test_ignores_malformed_records_and_old_files(self):
        with tempfile.TemporaryDirectory() as home:
            old = self._write(home, "sessions/old.jsonl", [
                {"payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 4}}}},
            ])
            os.utime(old, (1, 1))
            started = datetime.now(timezone.utc).isoformat()
            usage, path = extract_interactive_usage("codex", home, started)
            self.assertIsNone(usage)
            self.assertIsNone(path)

    def test_oversized_transcript_is_unavailable_without_reading_it(self):
        with tempfile.TemporaryDirectory() as home:
            path = self._write(home, "sessions/large.jsonl", [])
            with open(path, "wb") as handle:
                handle.truncate(MAX_TRANSCRIPT_BYTES + 1)
            usage, selected = extract_interactive_usage("codex", home)
            self.assertIsNone(usage)
            self.assertEqual(selected, path)

    def test_candidate_cap_returns_newest_seen_transcript(self):
        with tempfile.TemporaryDirectory() as home:
            older = self._write(home, "sessions/older.jsonl", [])
            newer = self._write(home, "sessions/newer.jsonl", [])
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            previous = interactive_usage.MAX_TRANSCRIPT_CANDIDATES
            interactive_usage.MAX_TRANSCRIPT_CANDIDATES = 1
            try:
                self.assertEqual(interactive_usage._latest_transcript("codex", home, None), newer)
            finally:
                interactive_usage.MAX_TRANSCRIPT_CANDIDATES = previous


if __name__ == "__main__":
    unittest.main()
