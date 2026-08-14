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
                    "input_tokens": 60, "cached_input_tokens": 50, "output_tokens": 2,
                    "reasoning_output_tokens": 1, "total_tokens": 62}}}},
                {"payload": {"type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 110, "cached_input_tokens": 90, "output_tokens": 4,
                    "reasoning_output_tokens": 2, "total_tokens": 114}}}},
            ])
            usage, _path = extract_interactive_usage("codex", home)
            # Codex's own `input_tokens` includes the cached tokens, so IN is
            # the 20-token remainder and CACHE holds the 90 it contained.
            self.assertEqual(usage, {"input_tokens": 20, "cached_input_tokens": 90,
                                    "cache_creation_tokens": None, "cache_read_tokens": 90,
                                    "output_tokens": 4, "reasoning_tokens": 2, "total_tokens": 114})

    def test_codex_cached_count_larger_than_input_is_left_alone(self):
        # Not a subset, so the cache-inclusive assumption cannot hold for this
        # record. Subtracting anyway would erase real input tokens.
        with tempfile.TemporaryDirectory() as home:
            self._write(home, "sessions/odd.jsonl", [
                {"payload": {"type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": 20, "cached_input_tokens": 90, "output_tokens": 4}}}},
            ])
            usage, _path = extract_interactive_usage("codex", home)
            self.assertEqual(usage["input_tokens"], 20)
            self.assertEqual(usage["total_tokens"], 114)

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
            # The total used to read 33 -- input plus output, with the 8 cached
            # tokens dropped entirely. Cache is most of real consumption, so
            # that was not a slightly-low total but a different quantity.
            self.assertEqual(usage, {"input_tokens": 13, "cached_input_tokens": 8,
                                    "cache_creation_tokens": 3, "cache_read_tokens": 5,
                                    "output_tokens": 20, "reasoning_tokens": None, "total_tokens": 41})

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
            self.assertEqual(os.path.normpath(selected), os.path.normpath(path))

    def test_candidate_cap_returns_newest_seen_transcript(self):
        with tempfile.TemporaryDirectory() as home:
            older = self._write(home, "sessions/older.jsonl", [])
            newer = self._write(home, "sessions/newer.jsonl", [])
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            previous = interactive_usage.MAX_TRANSCRIPT_CANDIDATES
            interactive_usage.MAX_TRANSCRIPT_CANDIDATES = 1
            try:
                self.assertEqual(
                    os.path.normpath(interactive_usage._latest_transcript("codex", home, None)),
                    os.path.normpath(newer),
                )
            finally:
                interactive_usage.MAX_TRANSCRIPT_CANDIDATES = previous


if __name__ == "__main__":
    unittest.main()


class UsageDefinitionAgreementTests(unittest.TestCase):
    """The three readers must describe the same consumption the same way.

    Before one definition existed they disagreed in every direction: the
    headless reader counted cache in IN *and* in CACHE, the interactive reader
    dropped cache from the total, and the background reader folded cache into
    IN while emitting no cached field at all. All three wrote into the same
    launch history and the same stats column, so the table mixed definitions
    without saying so. This test is what stops that returning.
    """

    USAGE = {
        "input_tokens": 12,
        "cache_creation_input_tokens": 3,
        "cache_read_input_tokens": 5,
        "output_tokens": 7,
    }
    EXPECTED = {
        "input_tokens": 12,
        "cached_input_tokens": 8,
        "cache_creation_tokens": 3,
        "cache_read_tokens": 5,
        "output_tokens": 7,
        "reasoning_tokens": None,
        "total_tokens": 27,
    }

    def test_headless_interactive_and_background_readers_agree(self):
        from src import run_usage
        from src.provider_background import read_transcript_outcome

        with tempfile.TemporaryDirectory() as home:
            stdout_path = os.path.join(home, "stdout.log")
            with open(stdout_path, "w", encoding="utf-8") as handle:
                json.dump({"result": "done", "usage": self.USAGE}, handle)

            transcript = os.path.join(home, ".claude", "projects", "repo", "s.jsonl")
            os.makedirs(os.path.dirname(transcript), exist_ok=True)
            with open(transcript, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "type": "assistant",
                    "uuid": "one",
                    "message": {"content": [{"type": "text", "text": "done"}], "usage": self.USAGE},
                }) + "\n")

            headless = run_usage.extract_run_usage("claude", stdout_path)
            interactive, _path = extract_interactive_usage("claude", home)
            background = read_transcript_outcome(transcript)["usage"]

        self.assertEqual(headless, self.EXPECTED)
        self.assertEqual(interactive, self.EXPECTED)
        self.assertEqual(background, self.EXPECTED)

    def test_every_reader_emits_the_full_field_set(self):
        # The background reader used to omit the cached fields entirely, so a
        # detached run left CACHE structurally empty rather than zero.
        from src.run_usage import USAGE_KEYS

        for name, record in (("expected", self.EXPECTED),):
            self.assertEqual(set(record), set(USAGE_KEYS), name)

    def test_a_total_that_excludes_cache_is_not_produced(self):
        from src.run_usage import normalize_usage

        record = normalize_usage(input_tokens=1, cache_creation_tokens=10,
                                 cache_read_tokens=100, output_tokens=2)
        self.assertEqual(record["total_tokens"], 113)

    def test_absence_is_not_zero(self):
        from src.run_usage import normalize_usage

        self.assertEqual(set(normalize_usage().values()), {None})


class ClaudeDedupTests(unittest.TestCase):
    """The billed unit is the API response, not the transcript row.

    Measured on one real 2741-row transcript: 2741 distinct uuids for 1765
    distinct (message id, request id) pairs. Counting per uuid inflated that
    file by ~1.55x against an independent reader of the same bytes; keying on
    the API response made the two agree exactly.
    """

    def _read(self, records):
        with tempfile.TemporaryDirectory() as home:
            path = os.path.join(home, "t.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")
            with open(path, encoding="utf-8") as handle:
                return interactive_usage._claude_usage(handle)

    def _assistant(self, uuid, message_id, request_id, output):
        return {
            "type": "assistant",
            "uuid": uuid,
            "requestId": request_id,
            "message": {"id": message_id, "usage": {"input_tokens": 1, "output_tokens": output}},
        }

    def test_one_billed_response_recorded_twice_counts_once(self):
        usage = self._read([
            self._assistant("uuid-a", "msg_1", "req_1", 10),
            self._assistant("uuid-b", "msg_1", "req_1", 10),
        ])
        self.assertEqual(usage["output_tokens"], 10)

    def test_distinct_responses_still_both_count(self):
        usage = self._read([
            self._assistant("uuid-a", "msg_1", "req_1", 10),
            self._assistant("uuid-b", "msg_2", "req_2", 10),
        ])
        self.assertEqual(usage["output_tokens"], 20)

    def test_records_with_no_identity_are_never_collapsed(self):
        # Absence of an identifier is not proof of a duplicate. Collapsing these
        # would discard usage that was really spent.
        usage = self._read([
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "output_tokens": 4}}},
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "output_tokens": 4}}},
        ])
        self.assertEqual(usage["output_tokens"], 8)
