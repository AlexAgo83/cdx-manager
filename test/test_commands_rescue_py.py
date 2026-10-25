"""cdx rescue: hand a limit-stopped conversation to an account that can go on."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from src.commands import rescue
from src.errors import CdxError

NOW = datetime.now(timezone.utc).isoformat()


def _row(name, available, policy="use"):
    return {"session_name": name, "provider": "claude", "auth_status": "authenticated",
            "available_pct": available, "policy": policy, "last_launched_at": NOW, "reset_at": "Oct 25 12:45"}


class RescueTests(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp()
        self.rows = [_row("spent", 0), _row("fresh", 80), _row("shared", 95, "ask-first"), _row("theirs", 99, "never")]
        sessions = [{"name": r["session_name"], "provider": "claude",
                     "conversation": {"id": "conv-1"} if r["session_name"] == "spent" else {}} for r in self.rows]
        self.service = {
            "list_sessions": lambda: sessions,
            "get_status_rows": lambda force_refresh=False: self.rows,
            "get_launch_history": lambda name, limit=1: [{"cwd": self.cwd}],
            "mark_conversation_rescued": self._mark,
        }
        self.sessions = sessions
        self.out = []
        self.answers = []

    def _mark(self, name, conversation_id):
        session = next(s for s in self.sessions if s["name"] == name)
        session["conversation"] = {**session["conversation"], "rescuedAt": datetime.now(timezone.utc).isoformat()}

    def _ctx(self, tty=True):
        return {"service": self.service, "out": self.out.append, "use_color": False, "stdin_is_tty": tty,
                "options": {"input": lambda _q: self.answers.pop(0)}}

    def _run(self, *args, tty=True):
        with mock.patch.object(rescue, "handle_handoff", return_value=0) as handoff:
            code = rescue.handle_rescue(list(args), self._ctx(tty))
        return code, handoff

    def test_a_use_account_takes_over_after_confirmation(self):
        self.answers = ["y"]
        code, handoff = self._run()
        self.assertEqual(code, 0)
        args, ctx = handoff.call_args[0]
        self.assertEqual(args, ["spent", "fresh", "--source-conversation", "conv-1"])
        self.assertEqual(ctx["cwd"], self.cwd)

    def test_a_rescued_conversation_is_not_handed_off_twice(self):
        _code, handoff = self._run("--yes")
        handoff.assert_called_once()
        _code, handoff = self._run("--yes")
        handoff.assert_not_called()
        # Launched again after the rescue: it can be rescued again. Derived from
        # the stamp, not the clock: Windows' ~15 ms tick can make both equal.
        rescued = datetime.fromisoformat(self.sessions[0]["conversation"]["rescuedAt"])
        self.rows[0]["last_launched_at"] = (rescued + timedelta(seconds=1)).isoformat()
        _code, handoff = self._run("--yes")
        handoff.assert_called_once()

    def test_ask_first_is_the_fallback_and_yes_does_not_cover_it(self):
        self.rows[1]["available_pct"] = 0
        self.rows[1]["last_launched_at"] = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(CdxError):
            self._run("--yes", tty=False)
        self.answers = ["y"]
        _code, handoff = self._run("--yes")
        self.assertEqual(handoff.call_args[0][0][1], "shared")

    def test_never_is_never_offered(self):
        for row in self.rows[1:3]:
            row["available_pct"] = 0
            row["last_launched_at"] = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(CdxError):
            self._run("--yes")
        with self.assertRaises(CdxError):
            self._run("--to", "theirs", "--yes")

    def test_dry_run_and_a_refusal_hand_nothing_over(self):
        _code, handoff = self._run("--dry-run")
        handoff.assert_not_called()
        self.answers = ["n"]
        with self.assertRaises(CdxError):
            self._run()

    def test_nothing_to_rescue_when_no_account_is_spent(self):
        self.rows[0]["available_pct"] = 40
        code, handoff = self._run("--yes")
        self.assertEqual(code, 0)
        handoff.assert_not_called()
        self.assertIn("No conversation stopped", self.out[0])


if __name__ == "__main__":
    unittest.main()


class EndedOnLimitTests(unittest.TestCase):
    def _transcript(self, *records):
        import json
        import os
        path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(record) + "\n" for record in records))
        return path

    def test_claude_and_codex_limit_stops_are_recognised(self):
        claude = self._transcript({"type": "user"}, {"type": "assistant", "isApiErrorMessage": True, "error": "rate_limit"})
        codex = self._transcript({"type": "event_msg", "payload": {"type": "error", "codex_error_info": "usage_limit_exceeded"}})
        self.assertTrue(rescue.ended_on_limit(claude))
        self.assertTrue(rescue.ended_on_limit(codex))

    def test_a_reply_after_the_limit_means_the_conversation_went_on(self):
        resumed = self._transcript({"type": "assistant", "isApiErrorMessage": True, "error": "rate_limit"},
                                   {"type": "assistant", "message": {"content": "back"}})
        other_error = self._transcript({"type": "assistant", "isApiErrorMessage": True, "error": "server_error"})
        self.assertFalse(rescue.ended_on_limit(resumed))
        self.assertFalse(rescue.ended_on_limit(other_error))
        self.assertFalse(rescue.ended_on_limit(None))

    def test_a_transcript_stop_is_rescued_before_the_status_shows_zero(self):
        stopped = self._transcript({"type": "assistant", "isApiErrorMessage": True, "error": "rate_limit"})
        cwd = tempfile.mkdtemp()
        row = {"session_name": "work", "available_pct": 35, "last_launched_at": NOW}
        service = {
            "list_sessions": lambda: [{"name": "work", "provider": "claude", "conversation": {"id": "c"}}],
            "get_launch_history": lambda name, limit=1: [{"cwd": cwd, "provider_transcript_path": stopped}],
        }
        self.assertEqual([s["session"] for s in rescue.stranded(service, {"work": row})], ["work"])


class MarkRescuedTests(unittest.TestCase):
    def test_only_the_handed_off_conversation_is_stamped(self):
        from src.session_service import create_session_service
        service = create_session_service({"base_dir": tempfile.mkdtemp()})
        service["create_session"]("work", "claude")
        conversation = service["begin_conversation"]("work")["conversation"]["id"]
        service["mark_conversation_rescued"]("work", "another")
        self.assertNotIn("rescuedAt", service["get_session"]("work")["conversation"])
        service["mark_conversation_rescued"]("work", conversation)
        self.assertIn("rescuedAt", service["get_session"]("work")["conversation"])
