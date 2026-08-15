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
            usage, _path, _match, _model = extract_interactive_usage("codex", home)
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
            usage, _path, _match, _model = extract_interactive_usage("codex", home)
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
            usage, _path, _match, _model = extract_interactive_usage("claude", home)
            # The total used to read 33 -- input plus output, with the 8 cached
            # tokens dropped entirely. Cache is most of real consumption, so
            # that was not a slightly-low total but a different quantity.
            self.assertEqual(usage, {"input_tokens": 13, "cached_input_tokens": 8,
                                    "cache_creation_tokens": 3, "cache_read_tokens": 5,
                                    "output_tokens": 20, "reasoning_tokens": None, "total_tokens": 41})

    def test_ignores_a_synthetic_model_placeholder(self):
        with tempfile.TemporaryDirectory() as home:
            self._write(home, ".claude/projects/repo/session.jsonl", [
                {"type": "assistant", "uuid": "one", "message": {"model": "claude-sonnet-5", "usage": {"input_tokens": 2}}},
                {"type": "assistant", "uuid": "two", "message": {"model": "<synthetic>", "usage": {"input_tokens": 3}}},
            ])
            _usage, _path, _match, model = extract_interactive_usage("claude", home)
            self.assertEqual(model, "claude-sonnet-5")

    def test_ignores_malformed_records_and_old_files(self):
        with tempfile.TemporaryDirectory() as home:
            old = self._write(home, "sessions/old.jsonl", [
                {"payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": 4}}}},
            ])
            os.utime(old, (1, 1))
            started = datetime.now(timezone.utc).isoformat()
            usage, path, _match, _model = extract_interactive_usage("codex", home, started)
            self.assertIsNone(usage)
            self.assertIsNone(path)

    def test_oversized_transcript_is_unavailable_without_reading_it(self):
        with tempfile.TemporaryDirectory() as home:
            path = self._write(home, "sessions/large.jsonl", [])
            with open(path, "wb") as handle:
                handle.truncate(MAX_TRANSCRIPT_BYTES + 1)
            usage, selected, _match, _model = extract_interactive_usage("codex", home)
            self.assertIsNone(usage)
            self.assertEqual(os.path.normpath(selected), os.path.normpath(path))

    def test_candidate_cap_reports_absence_rather_than_a_partial_guess(self):
        # An inconclusive scan used to return whichever candidate it had
        # reached, which is indistinguishable from a real measurement. A run
        # billed against an unrelated file is worse than a run with no number.
        with tempfile.TemporaryDirectory() as home:
            older = self._write(home, "sessions/older.jsonl", [])
            newer = self._write(home, "sessions/newer.jsonl", [])
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))
            previous = interactive_usage.MAX_TRANSCRIPT_CANDIDATES
            interactive_usage.MAX_TRANSCRIPT_CANDIDATES = 1
            try:
                self.assertIsNone(interactive_usage._latest_transcript("codex", home, None))
            finally:
                interactive_usage.MAX_TRANSCRIPT_CANDIDATES = previous


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
            interactive, _path, _match, _model = extract_interactive_usage("claude", home)
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
                return interactive_usage._claude_usage(handle)[0]

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


if __name__ == "__main__":
    unittest.main()


class TranscriptResolutionTests(unittest.TestCase):
    """Measure the session that ran, not whichever file was touched last.

    The mtime scan this replaces is why sessions reported three runs and
    eighteen output tokens: they were billed against an unrelated file that
    happened to be newer.
    """

    def _claude_transcript(self, home, session_id, output):
        path = os.path.join(home, ".claude", "projects", "some-repo", f"{session_id}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "type": "assistant", "uuid": f"u-{session_id}", "requestId": f"r-{session_id}",
                "message": {"id": f"m-{session_id}", "usage": {"input_tokens": 1, "output_tokens": output}},
            }) + "\n")
        return path

    def test_a_newer_unrelated_transcript_does_not_win(self):
        with tempfile.TemporaryDirectory() as home:
            mine = self._claude_transcript(home, "11111111-1111-1111-1111-111111111111", 5)
            theirs = self._claude_transcript(home, "22222222-2222-2222-2222-222222222222", 999)
            os.utime(mine, (1, 1))
            os.utime(theirs, (10, 10))

            usage, path, match, _model = extract_interactive_usage(
                "claude", home, None, "11111111-1111-1111-1111-111111111111")

            self.assertEqual(os.path.normpath(path), os.path.normpath(mine))
            self.assertEqual(usage["output_tokens"], 5)
            self.assertEqual(match, interactive_usage.MATCH_CONVERSATION_ID)

    def test_a_known_id_with_no_transcript_reports_absence_not_a_guess(self):
        with tempfile.TemporaryDirectory() as home:
            self._claude_transcript(home, "22222222-2222-2222-2222-222222222222", 999)

            usage, path, match, _model = extract_interactive_usage(
                "claude", home, None, "11111111-1111-1111-1111-111111111111")

            # Nothing found means nothing to describe: no usage, no path, and
            # no match kind. What must not happen is falling back to the scan
            # and billing this session for another session's file.
            self.assertIsNone(usage)
            self.assertIsNone(path)
            self.assertIsNone(match)

    def test_no_conversation_id_falls_back_but_says_so(self):
        with tempfile.TemporaryDirectory() as home:
            self._claude_transcript(home, "22222222-2222-2222-2222-222222222222", 9)

            usage, path, match, _model = extract_interactive_usage("claude", home)

            self.assertIsNotNone(path)
            self.assertEqual(usage["output_tokens"], 9)
            self.assertEqual(match, interactive_usage.MATCH_RECENCY)

    def test_codex_resolves_the_rollout_carrying_its_conversation_id(self):
        with tempfile.TemporaryDirectory() as home:
            identifier = "33333333-3333-3333-3333-333333333333"
            root = os.path.join(home, "sessions", "2026", "08")
            os.makedirs(root, exist_ok=True)
            for name, output in (
                (f"rollout-2026-08-14T10-00-00-{identifier}.jsonl", 4),
                ("rollout-2026-08-14T11-00-00-44444444-4444-4444-4444-444444444444.jsonl", 999),
            ):
                with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
                    handle.write(json.dumps({"payload": {"type": "token_count", "info": {
                        "total_token_usage": {"input_tokens": 10, "cached_input_tokens": 0,
                                              "output_tokens": output}}}}) + "\n")

            usage, path, match, _model = extract_interactive_usage("codex", home, None, identifier)

            self.assertIn(identifier, os.path.basename(path))
            self.assertEqual(usage["output_tokens"], 4)
            self.assertEqual(match, interactive_usage.MATCH_CONVERSATION_ID)


class CodexNewConversationTests(unittest.TestCase):
    """Codex names its conversation only after the run has produced it.

    A real turn reported no usage at all because of this: the session still
    carried the previous conversation's id, that rollout was untouched by the
    run, and differencing an unchanged file yields zero.
    """

    def _rollout(self, home, identifier, stamp, output):
        root = os.path.join(home, "sessions", "2026", "08")
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, f"rollout-{stamp}-{identifier}.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": 10, "cached_input_tokens": 0,
                                      "output_tokens": output}}}}) + "\n")
        return path

    def test_a_rollout_untouched_by_this_run_gives_way_to_the_current_one(self):
        previous = "019ffc96-f601-7c20-b365-1a6e9ab0b5d1"
        with tempfile.TemporaryDirectory() as home:
            old = self._rollout(home, previous, "2026-08-13T21-26-19", 5)
            current = self._rollout(home, "019fffde-c50c-7331-9a48-1e000138913e",
                                    "2026-08-14T12-43-37", 69)
            os.utime(old, (1, 1))
            started = datetime.fromtimestamp(os.path.getmtime(current) - 5, timezone.utc)

            usage, path, match, _model = extract_interactive_usage(
                "codex", home, started.isoformat(), previous)

            self.assertEqual(os.path.normpath(path), os.path.normpath(current))
            self.assertEqual(usage["output_tokens"], 69)
            self.assertEqual(match, interactive_usage.MATCH_RECENCY)

    def test_a_rollout_this_run_did_touch_is_kept_and_named_as_an_id_match(self):
        identifier = "019fffde-c50c-7331-9a48-1e000138913e"
        with tempfile.TemporaryDirectory() as home:
            current = self._rollout(home, identifier, "2026-08-14T12-43-37", 69)
            started = datetime.fromtimestamp(os.path.getmtime(current) - 5, timezone.utc)

            _usage, path, match, _model = extract_interactive_usage(
                "codex", home, started.isoformat(), identifier)

            self.assertEqual(os.path.normpath(path), os.path.normpath(current))
            self.assertEqual(match, interactive_usage.MATCH_CONVERSATION_ID)

    def test_claude_does_not_get_the_fallback(self):
        # Claude's id is minted by cdx before the run, so a missing transcript
        # there means something is wrong -- not that a newer file is the right
        # answer. That fallback is exactly what billed a session against an
        # unrelated project's transcript.
        with tempfile.TemporaryDirectory() as home:
            other = os.path.join(home, ".claude", "projects", "elsewhere", "other.jsonl")
            os.makedirs(os.path.dirname(other), exist_ok=True)
            with open(other, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "assistant", "uuid": "u", "requestId": "r",
                                         "message": {"id": "m", "usage": {"output_tokens": 999}}}) + "\n")

            usage, path, _match, _model = extract_interactive_usage(
                "claude", home, None, "11111111-1111-1111-1111-111111111111")

            self.assertIsNone(usage)
            self.assertIsNone(path)
