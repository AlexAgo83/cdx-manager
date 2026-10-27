"""The integration surface an external orchestrator reads instead of cdx internals.

Covers `runs --running`, `run-report` `final_message`, `sessions --json`,
`status --json` paths and `can-resume/resume --conversation`.
"""

import json
import os
import unittest

from cli_test_support import CliTestBase

from src.cli import main
from src.errors import CdxError
from src.run_registry import RunRegistry, final_message
from src.session_service import create_session_service

CODEX_STDOUT = "\n".join(json.dumps(record) for record in (
    {"type": "thread.started", "thread_id": "t1"},
    {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "I'll look first."}},
    {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "aggregated_output": "42\n"}},
    {"type": "item.completed", "item": {"id": "item_2", "type": "agent_message", "text": "Shipped: done\nResult: 42"}},
    {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
))
CLAUDE_STDOUT = json.dumps({"type": "result", "subtype": "success", "result": "Claude final answer"})
CODEX_LEGACY_STDOUT = json.dumps({"id": "0", "msg": {"type": "agent_message", "message": "old shape report"}})


class FinalMessageTests(CliTestBase):

    def _run_with_stdout(self, text):
        path = os.path.join(self.make_temp_dir(), "stdout.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return {"artifacts": {"stdout_path": path}, "final_payload": {}}

    def test_reads_the_last_message_of_each_provider_format(self):
        self.assertEqual(final_message(self._run_with_stdout(CODEX_STDOUT)), "Shipped: done\nResult: 42")
        self.assertEqual(final_message(self._run_with_stdout(CLAUDE_STDOUT)), "Claude final answer")
        self.assertEqual(final_message(self._run_with_stdout(CODEX_LEGACY_STDOUT)), "old shape report")

    def test_background_result_wins_and_unknown_output_is_none(self):
        run = self._run_with_stdout(CODEX_STDOUT)
        run["final_payload"] = {"result": "from the transcript"}
        self.assertEqual(final_message(run), "from the transcript")
        self.assertIsNone(final_message(self._run_with_stdout("plain text, no events\n")))
        self.assertIsNone(final_message({"artifacts": {"stdout_path": "/nonexistent/x.log"}}))
        self.assertIsNone(final_message({}))

    def test_run_report_carries_final_message(self):
        base_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": base_dir})
        run = self._run_with_stdout(CODEX_STDOUT)
        registry = RunRegistry(base_dir)
        registry.start("r1", kind="assistant", session="work", provider="codex", model=None,
                       cwd=base_dir, artifacts=run["artifacts"])
        registry.finish("r1", status="succeeded", final_payload={})

        io_obj = self.make_io()
        self.assertEqual(main(["run-report", "r1", "--json"], {**io_obj, "service": service}), 0)
        report = json.loads(io_obj["stdout"].getvalue())["report"]
        self.assertEqual(report["final_message"], "Shipped: done\nResult: 42")


class RunningFilterTests(CliTestBase):

    def test_running_returns_every_live_run_and_nothing_else(self):
        base_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": base_dir})
        registry = RunRegistry(base_dir)
        for run_id in ("live1", "live2", "done"):
            registry.start(run_id, kind="assistant", session="work", provider="codex", model=None, cwd=base_dir)
        registry.finish("done", status="succeeded", final_payload={})

        io_obj = self.make_io()
        self.assertEqual(main(["runs", "--running", "--limit", "1", "--json"], {**io_obj, "service": service}), 0)
        runs = json.loads(io_obj["stdout"].getvalue())["runs"]
        # Uncapped by --limit: a cap check must see every live run.
        self.assertEqual(sorted(run["run_id"] for run in runs), ["live1", "live2"])

    def test_running_and_since_are_mutually_exclusive(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        with self.assertRaisesRegex(CdxError, "mutually exclusive"):
            main(["runs", "--running", "--since", "today", "--json"], {**self.make_io(), "service": service})

    def test_kind_enum_is_published_in_the_schema(self):
        io_obj = self.make_io()
        self.assertEqual(main(["schema", "--json"], {**io_obj, "service": create_session_service({"base_dir": self.make_temp_dir()})}), 0)
        kinds = json.loads(io_obj["stdout"].getvalue())["enums"]["kind"]["accepted"]
        self.assertEqual(kinds, ["assistant", "code-review", "retro"])


class SessionsAndPathsTests(CliTestBase):

    def test_sessions_lists_only_live_interactive_sessions_with_paths(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        work = service["create_session"]("work", "claude")
        service["create_session"]("idle", "codex")
        service["start_session_runtime"]("work", {"pid": os.getpid(), "cwd": "/tmp/repo"})

        io_obj = self.make_io()
        self.assertEqual(main(["sessions", "--json"], {**io_obj, "service": service}), 0)
        rows = json.loads(io_obj["stdout"].getvalue())["sessions"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["session"], row["provider"], row["pid"], row["cwd"]),
                         ("work", "claude", os.getpid(), "/tmp/repo"))
        self.assertEqual(row["profile_dir"], work["sessionRoot"])
        self.assertEqual(row["transcripts_dir"], os.path.join(work["authHome"], ".claude", "projects"))

    def test_all_resolves_idle_accounts_without_naming_the_credential_home(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        codex = service["create_session"]("main", "codex")

        io_obj = self.make_io()
        self.assertEqual(main(["sessions", "--all", "--json"], {**io_obj, "service": service}), 0)
        row = json.loads(io_obj["stdout"].getvalue())["sessions"][0]
        self.assertFalse(row["active"])
        self.assertIsNone(row["pid"])
        self.assertEqual(row["profile_dir"], codex["sessionRoot"])
        self.assertEqual(row["transcripts_dir"], os.path.join(codex["authHome"], "sessions"))
        self.assertNotIn("auth_home", row)


class ConversationResumeTests(CliTestBase):

    CONVERSATION = "0199a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b"

    def _codex_with_rollout(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        session = service["create_session"]("main", "codex")
        day = os.path.join(session["authHome"], "sessions", "2026", "10", "27")
        os.makedirs(day, exist_ok=True)
        with open(os.path.join(day, f"rollout-2026-10-27T10-00-00-{self.CONVERSATION}.jsonl"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        return service

    def _can_resume(self, service, *args):
        io_obj = self.make_io()
        self.assertEqual(main(["can-resume", "main", *args, "--json"], {
            **io_obj, "service": service, "cwd": "/tmp/repo",
            "spawn": lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not spawn")),
        }), 0)
        return json.loads(io_obj["stdout"].getvalue())

    def test_a_named_conversation_that_exists_is_resumed_by_id(self):
        payload = self._can_resume(self._codex_with_rollout(), "--conversation", self.CONVERSATION)
        self.assertTrue(payload["resumable"])
        self.assertEqual(payload["identity"], self.CONVERSATION)
        self.assertEqual(payload["provenance"], "requested")
        self.assertEqual(payload["command_preview"], ["codex", "resume", self.CONVERSATION, "--cd", "/tmp/repo"])

    def test_a_named_conversation_that_is_missing_never_falls_back_to_last(self):
        payload = self._can_resume(self._codex_with_rollout(), "--conversation=11111111-2222-3333-4444-555555555555")
        self.assertFalse(payload["resumable"])
        self.assertEqual(payload["reason"], "conversation_not_found")
        self.assertEqual(payload["command_preview"], [])

    def test_resume_refuses_a_missing_conversation_before_launching(self):
        service = self._codex_with_rollout()
        with self.assertRaisesRegex(CdxError, "not found"):
            main(["resume", "main", "--conversation", "11111111-2222-3333-4444-555555555555", "--json"], {
                **self.make_io(), "service": service,
                "spawn": lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not spawn")),
            })


if __name__ == "__main__":
    unittest.main()
