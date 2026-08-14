"""A run must be billed for its own tokens, not for the transcript's history."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from src.commands.launch import _attach_interactive_usage
from src.interactive_usage import usage_delta


def _assistant(message_id, output):
    return {
        "type": "assistant",
        "uuid": f"uuid-{message_id}",
        "requestId": f"req-{message_id}",
        "message": {"id": message_id, "usage": {
            "input_tokens": 1,
            "cache_creation_input_tokens": 2,
            "cache_read_input_tokens": 10,
            "output_tokens": output,
        }},
    }


class UsageDeltaTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.home = self._dir.name
        self.transcript = os.path.join(self.home, ".claude", "projects", "repo", "s.jsonl")
        os.makedirs(os.path.dirname(self.transcript), exist_ok=True)
        self.session = {"name": "work", "provider": "claude", "authHome": self.home}
        self.addCleanup(self._dir.cleanup)

    def _append(self, records):
        with open(self.transcript, "a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    def _run(self, history, started_at=None):
        started = started_at or (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        return _attach_interactive_usage(self.session, {"started_at": started}, history)

    def test_second_run_records_only_what_the_transcript_gained(self):
        self._append([_assistant("m1", 5)])
        first = self._run([])
        self._append([_assistant("m2", 7)])
        second = self._run([first])

        self.assertEqual(first["usage"]["output_tokens"], 5)
        self.assertEqual(second["usage"]["output_tokens"], 7)

    def test_the_runs_sum_to_the_transcript_total_not_a_multiple_of_it(self):
        self._append([_assistant("m1", 5)])
        first = self._run([])
        self._append([_assistant("m2", 7)])
        second = self._run([first])

        transcript_total = second["usage_cumulative"]["total_tokens"]
        summed = first["usage"]["total_tokens"] + second["usage"]["total_tokens"]
        self.assertEqual(summed, transcript_total)

    def test_a_resumed_session_is_not_billed_for_its_history_each_time(self):
        # The observed failure: one extra launch moved a session's cache read
        # from 2.6M to 7.6M because every run stored the whole file again.
        self._append([_assistant("m1", 5)])
        runs = [self._run([])]
        for index, output in enumerate((7, 11, 13)):
            self._append([_assistant(f"m{index + 2}", output)])
            runs.append(self._run(list(reversed(runs))))

        summed = sum(run["usage"]["total_tokens"] for run in runs)
        self.assertEqual(summed, runs[-1]["usage_cumulative"]["total_tokens"])

    def test_a_shrunken_transcript_reports_absence_rather_than_a_negative(self):
        self._append([_assistant("m1", 5), _assistant("m2", 7)])
        first = self._run([])
        os.remove(self.transcript)
        self._append([_assistant("m1", 5)])
        second = self._run([first])

        self.assertIsNone(second.get("usage"))
        # The baseline still moves, so the next run recovers instead of
        # inheriting a stale, larger cumulative forever.
        self.assertEqual(second["usage_cumulative"]["output_tokens"], 5)

    def test_a_transcript_that_predates_the_run_is_not_billed_to_it(self):
        # The real shape of this case: the file already existed when the run
        # started and was appended to during it. Its history is work cdx never
        # measured, so the run leaves a baseline and reports nothing.
        self._append([_assistant("m1", 5)])
        started = datetime.now(timezone.utc) + timedelta(seconds=1)
        touched = started.timestamp() + 60
        os.utime(self.transcript, (touched, touched))
        run = self._run([], started_at=started.isoformat())

        self.assertIsNone(run.get("usage"))
        self.assertEqual(run["usage_cumulative"]["output_tokens"], 5)


class UsageDeltaArithmeticTests(unittest.TestCase):
    def test_difference_is_taken_on_measured_fields_only(self):
        cumulative = {"input_tokens": 10, "cache_creation_tokens": 4, "cache_read_tokens": 100,
                      "output_tokens": 8, "reasoning_tokens": None,
                      "cached_input_tokens": 104, "total_tokens": 122}
        previous = {"input_tokens": 4, "cache_creation_tokens": 1, "cache_read_tokens": 40,
                    "output_tokens": 3, "reasoning_tokens": None,
                    "cached_input_tokens": 41, "total_tokens": 48}
        delta = usage_delta(cumulative, previous)
        self.assertEqual(delta["input_tokens"], 6)
        self.assertEqual(delta["cache_read_tokens"], 60)
        # Derived again from the differenced parts, never differenced itself.
        self.assertEqual(delta["cached_input_tokens"], 63)
        self.assertEqual(delta["total_tokens"], 74)

    def test_any_negative_component_voids_the_whole_delta(self):
        self.assertIsNone(usage_delta({"output_tokens": 1}, {"output_tokens": 5}))


class CodexUsageDeltaTests(unittest.TestCase):
    """Codex's snapshot is cumulative for the conversation, so it needs the
    same treatment -- and gets it, because the delta is computed on the record
    the reader returns rather than inside either provider's parser."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.home = self._dir.name
        self.transcript = os.path.join(self.home, "sessions", "rollout.jsonl")
        os.makedirs(os.path.dirname(self.transcript), exist_ok=True)
        self.session = {"name": "work", "provider": "codex", "authHome": self.home}
        self.addCleanup(self._dir.cleanup)

    def _snapshot(self, input_tokens, cached, output):
        with open(self.transcript, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"payload": {"type": "token_count", "info": {
                "total_token_usage": {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached,
                    "output_tokens": output,
                },
            }}}) + "\n")

    def _run(self, history):
        started = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        return _attach_interactive_usage(self.session, {"started_at": started}, history)

    def test_a_resumed_conversation_records_only_the_increment(self):
        self._snapshot(1000, 400, 50)
        first = self._run([])
        self._snapshot(1600, 900, 80)
        second = self._run([first])

        # Uncached input went 600 -> 700, cache reads 400 -> 900, output 50 -> 80.
        self.assertEqual(first["usage"]["input_tokens"], 600)
        self.assertEqual(second["usage"]["input_tokens"], 100)
        self.assertEqual(second["usage"]["cache_read_tokens"], 500)
        self.assertEqual(second["usage"]["output_tokens"], 30)


class ModelAttributionTests(unittest.TestCase):
    """Which model served the run, read from the transcript."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.home = self._dir.name
        self.transcript = os.path.join(self.home, ".claude", "projects", "repo", "s.jsonl")
        os.makedirs(os.path.dirname(self.transcript), exist_ok=True)
        self.session = {"name": "work", "provider": "claude", "authHome": self.home}
        self.addCleanup(self._dir.cleanup)

    def _append(self, message_id, model):
        with open(self.transcript, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "type": "assistant", "uuid": f"u-{message_id}", "requestId": f"r-{message_id}",
                "message": {"id": message_id, "model": model,
                            "usage": {"input_tokens": 1, "output_tokens": 2}},
            }) + "\n")

    def _run(self, history=()):
        started = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        return _attach_interactive_usage(self.session, {"started_at": started}, list(history))

    def test_the_serving_model_is_recorded_on_the_run(self):
        self._append("m1", "claude-opus-5")
        self.assertEqual(self._run()["usage_model"], "claude-opus-5")

    def test_a_run_spanning_models_is_attributed_to_the_most_recent(self):
        # The documented rule: one model per run, the one serving its latest
        # record. A session that switched mid-run is priced at the newer model.
        self._append("m1", "claude-haiku-4-5")
        self._append("m2", "claude-opus-5")
        self.assertEqual(self._run()["usage_model"], "claude-opus-5")

    def test_a_transcript_naming_no_model_records_none(self):
        with open(self.transcript, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "type": "assistant", "uuid": "u", "requestId": "r",
                "message": {"id": "m", "usage": {"input_tokens": 1, "output_tokens": 2}},
            }) + "\n")
        self.assertIsNone(self._run().get("usage_model"))
