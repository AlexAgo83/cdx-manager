"""Tests for run, runs, run-status, run-report, run-tail, select, schema.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import io
import json
import os
import re
import subprocess
import sys
from unittest import mock

from cli_test_support import (  # noqa: F401
    CRYPTOGRAPHY_REQUIRED,
    HAS_CRYPTOGRAPHY,
    CliTestBase,
    _AuthHarness,
    _Child,
    _HeadlessChild,
    _script_launch_args,
    _script_launch_invokes,
    _script_launch_text,
    _script_transcript_path,
    _SignalEmitter,
    _Stream,
    _TimeoutChild,
    _TtyStream,
)

from src.cli import (
    format_json_error,
    main,
)
from src.cli_args import (
    RUN_USAGE,
    _parse_run_args,
)
from src.errors import CdxError
from src.run_registry import RunRegistry
from src.session_ranking import RANKING_FACTORS
from src.session_service import create_session_service


class RunsCommandTests(CliTestBase):

    def test_headless_selection_priority_breaks_reasoning_ties_after_minimum_filter(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("lowp", "codex")
        service["create_session"]("highp", "codex")
        service["set_launch_settings"]("lowp", {"power": "low", "priority": 0})
        service["set_launch_settings"]("highp", {"power": "high", "priority": 100})
        for name in ("lowp", "highp"):
            service["update_auth_state"](name, lambda auth: {**auth, "status": "authenticated"})
            service["record_status"](name, {"remaining_5h_pct": 80, "remaining_week_pct": 80})

        low_min_io = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--min-reasoning-effort", "low", "--require-ready", "--json"
        ], {**low_min_io, "service": service}), 0)
        self.assertEqual(json.loads(low_min_io["stdout"].getvalue())["session"], "highp")

        high_min_io = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--min-reasoning-effort", "high", "--require-ready", "--json"
        ], {**high_min_io, "service": service}), 0)
        self.assertEqual(json.loads(high_min_io["stdout"].getvalue())["session"], "highp")

    def test_select_returns_ready_codex_session_as_json(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("low", "codex")
        service["create_session"]("full", "codex")
        service["update_auth_state"]("low", lambda auth: {**auth, "status": "authenticated"})
        service["update_auth_state"]("full", lambda auth: {**auth, "status": "authenticated"})
        service["record_status"]("low", {"remaining_5h_pct": 20, "remaining_week_pct": 20})
        service["record_status"]("full", {"remaining_5h_pct": 80, "remaining_week_pct": 80})

        io_obj = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--min-reasoning-effort", "low", "--require-ready", "--json"
        ], {**io_obj, "service": service}), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "full")
        self.assertEqual(payload["provider"], "codex")
        # The reason names the factor that actually decided this call, and the
        # policy is built from the ranking rather than typed out, so neither can
        # describe an order the code does not apply.
        self.assertIn(payload["deciding_factor"], (None, *RANKING_FACTORS))
        self.assertEqual(
            [factor["name"] for factor in payload["selection_policy"]["factors"]],
            list(RANKING_FACTORS),
        )
        self.assertIn("availability", payload["selection_policy"]["summary"])

    def test_select_without_minimum_includes_minimal_power_sessions(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("tiny", "claude")
        service["set_launch_settings"]("tiny", {"power": "minimal"})
        service["update_auth_state"]("tiny", lambda auth: {**auth, "status": "authenticated"})
        service["record_status"]("tiny", {"remaining_5h_pct": 80, "remaining_week_pct": 80})

        io_obj = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "claude", "--require-ready", "--json"
        ], {**io_obj, "service": service}), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "tiny")

    def test_select_reports_no_suitable_session(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("loggedout", "codex")
        service["update_auth_state"]("loggedout", lambda auth: {**auth, "status": "logged_out"})

        io_obj = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--min-power", "low", "--require-ready", "--json"
        ], {**io_obj, "service": service}), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "no_suitable_session")

    def test_select_require_ready_allows_local_no_auth_provider(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("local", "ollama")
        service["set_launch_settings"]("local", {"model": "llama3.2"})

        io_obj = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "ollama", "--require-ready", "--json"
        ], {**io_obj, "service": service}), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "local")
        self.assertEqual(payload["provider"], "ollama")

    def test_run_explicit_session_returns_json_and_captures_provider_output(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        prompt_path = os.path.join(target_dir, "prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            handle.write("Do it")
        calls = []

        def spawn(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            running = RunRegistry(target_dir).list(limit=1)[0]
            self.assertEqual(running["status"], "running")
            self.assertEqual(running["session"], "work")
            self.assertEqual(running["artifacts"]["stdout_path"], kwargs["stdout"].name)
            kwargs["stdout"].write(json.dumps({
                "type": "usage",
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 5,
                    "output_tokens_details": {"reasoning_tokens": 2},
                    "total_tokens": 16,
                },
            }) + "\n")
            kwargs["stderr"].write("provider stderr\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work",
            "--cwd", target_dir,
            "--prompt-file", prompt_path,
            "--model", "gpt-5.3-codex",
            "--reasoning-effort", "low",
            "--permission", "workspace-write",
            "--timeout-seconds", "30",
            "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "work")
        self.assertEqual(payload["provider"], "codex")
        self.assertEqual(payload["launcher"], "cdx")
        self.assertEqual(payload["model"], "gpt-5.3-codex")
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(payload["power"], "low")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["usage"], {
            "input_tokens": 11,
            "output_tokens": 5,
            "reasoning_tokens": 2,
            "total_tokens": 16,
        })
        history = service["get_launch_history"]("work", limit=1)
        self.assertEqual(history[0]["usage"], payload["usage"])
        self.assertIn("[prompt redacted]", history[0]["args"])
        self.assertNotIn("Do it", history[0]["args"])
        self.assertTrue(os.path.isabs(payload["transcript_path"]))
        with open(payload["stdout_path"], encoding="utf-8") as handle:
            self.assertIn("input_tokens", handle.read())
        with open(payload["stderr_path"], encoding="utf-8") as handle:
            self.assertIn("provider stderr", handle.read())
        self.assertEqual(calls[0]["argv"][:2], ["codex", "exec"])
        self.assertIn("--json", calls[0]["argv"])
        self.assertTrue(any("Do it" in arg for arg in calls[0]["argv"]))

    def test_runs_since_is_bounded_by_the_cursor_not_by_limit(self):
        # The cursor exists so a polling caller cannot miss completions. Bounding
        # it by --limit as well would silently reintroduce that miss: a watchdog
        # behind by more than `limit` completions would never see the older ones.
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("done\n")
            return _HeadlessChild(0)

        started = []
        for _ in range(3):
            run_io = self.make_io()
            self.assertEqual(main([
                "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
            ], self.make_run_ctx(run_io, service, spawn_headless=spawn)), 0)
            started.append(json.loads(run_io["stdout"].getvalue())["run_id"])

        since_io = self.make_io()
        self.assertEqual(
            main(["runs", "--since", "today", "--limit", "1", "--json"],
                 self.make_run_ctx(since_io, service)), 0)
        payload = json.loads(since_io["stdout"].getvalue())

        # All three come back despite --limit 1, and the caller is told why.
        self.assertEqual(sorted(r["run_id"] for r in payload["runs"]), sorted(started))
        self.assertIsNotNone(payload["since"])
        self.assertEqual([w["code"] for w in payload["warnings"]], ["limit_ignored_with_since"])

    def test_run_registry_exposes_recent_status_and_report_json(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("done\n")
            return _HeadlessChild(0)

        run_io = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(run_io, service, spawn_headless=spawn)), 0)
        run_payload = json.loads(run_io["stdout"].getvalue())

        runs_io = self.make_io()
        self.assertEqual(main(["runs", "--json"], self.make_run_ctx(runs_io, service)), 0)
        runs_payload = json.loads(runs_io["stdout"].getvalue())
        self.assertEqual(runs_payload["runs"][0]["run_id"], run_payload["run_id"])
        self.assertEqual(runs_payload["runs"][0]["status"], "succeeded")

        status_io = self.make_io()
        self.assertEqual(main(["run-status", run_payload["run_id"], "--json"], self.make_run_ctx(status_io, service)), 0)
        status_payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(status_payload["run"]["run_id"], run_payload["run_id"])
        self.assertEqual(status_payload["run"]["artifacts"]["stdout_path"], run_payload["stdout_path"])

        report_io = self.make_io()
        self.assertEqual(main(["run-report", run_payload["run_id"], "--json"], self.make_run_ctx(report_io, service)), 0)
        report_payload = json.loads(report_io["stdout"].getvalue())
        self.assertEqual(report_payload["report"]["final_payload"]["run_id"], run_payload["run_id"])
        self.assertEqual(report_payload["report"]["usage"], run_payload["usage"])

    def test_run_code_review_kind_persists_structured_task_report(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("review", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({
                "summary": "One issue found.",
                "findings": [{
                    "severity": "high",
                    "path": "src/app.py",
                    "line": 12,
                    "message": "Missing validation.",
                }],
                "next_steps": ["Create a Logics request for the finding."],
            }))
            return _HeadlessChild(0)

        run_io = self.make_io()
        self.assertEqual(main([
            "run", "review", "--cwd", target_dir, "--prompt", "Review it", "--kind", "code-review", "--json"
        ], self.make_run_ctx(run_io, service, spawn_headless=spawn)), 0)
        run_payload = json.loads(run_io["stdout"].getvalue())

        report_io = self.make_io()
        self.assertEqual(main(["run-report", run_payload["run_id"], "--json"], self.make_run_ctx(report_io, service)), 0)
        report_payload = json.loads(report_io["stdout"].getvalue())
        task_report = report_payload["report"]["task_report"]
        self.assertEqual(task_report["kind"], "code-review")
        self.assertEqual(task_report["summary"], "One issue found.")
        self.assertEqual(task_report["findings"][0]["path"], "src/app.py")
        self.assertEqual(task_report["next_steps"], ["Create a Logics request for the finding."])

    def test_run_json_reports_default_power_as_reasoning_effort(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **_kwargs):
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["reasoning_effort"], "medium")
        self.assertEqual(payload["power"], "medium")

    def test_run_requires_live_auth_probe_even_when_local_token_exists(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn_sync(command, args, _options=None):
            self.assertEqual(command, "codex")
            self.assertEqual(args, ["login", "status"])
            return {"stdout": "Not logged in\n", "stderr": ""}

        def spawn(_argv, **_kwargs):
            raise AssertionError("unauthenticated headless runs must not launch provider")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], {**io_obj, "service": service, "spawn_headless": spawn, "spawn_sync": spawn_sync}), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "cdx_error")
        self.assertIn("not authenticated", payload["error"]["message"])

    def test_run_provider_failure_uses_provider_error_source(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 0,
                    "total_tokens": 3,
                },
            }) + "\n")
            kwargs["stderr"].write("failed\n")
            return _HeadlessChild(7)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 7)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "provider")
        self.assertEqual(payload["error"]["code"], "provider_failed")
        self.assertEqual(payload["exit_code"], 7)
        self.assertEqual(payload["usage"], {
            "input_tokens": 3,
            "output_tokens": 0,
            "reasoning_tokens": None,
            "total_tokens": 3,
        })

    def test_run_provider_capacity_failure_remains_queryable_in_registry(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("auto", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["update_auth_state"]("auto", lambda auth: {**auth, "status": "authenticated"})
        service["record_status"]("auto", {"remaining_5h_pct": 75, "remaining_week_pct": 75})
        capacity_message = "Selected model is at capacity. Please try a different model."

        def spawn(_argv, **kwargs):
            running = RunRegistry(target_dir).list(limit=1)[0]
            self.assertEqual(running["status"], "running")
            self.assertEqual(running["session"], "auto")
            self.assertEqual(running["provider"], "codex")
            self.assertEqual(running["cwd"], os.path.abspath(target_dir))
            self.assertEqual(running["artifacts"]["stdout_path"], kwargs["stdout"].name)
            kwargs["stdout"].write(json.dumps({"type": "thread.started", "thread_id": "thread_123"}) + "\n")
            kwargs["stdout"].write(json.dumps({"type": "turn.started"}) + "\n")
            kwargs["stdout"].write(capacity_message + "\n")
            return _HeadlessChild(1)

        run_io = self.make_io()
        self.assertEqual(main([
            "run", "--provider", "codex", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(run_io, service, spawn_headless=spawn)), 1)
        run_payload = json.loads(run_io["stdout"].getvalue())
        run_id = run_payload["run_id"]

        self.assertFalse(run_payload["ok"])
        self.assertEqual(run_payload["session"], "auto")
        self.assertEqual(run_payload["provider"], "codex")
        self.assertEqual(run_payload["error"]["code"], "provider_failed")
        self.assertEqual(run_payload["error"]["provider_code"], 1)
        self.assertIn(capacity_message, run_payload["error"]["message"])
        self.assertTrue(os.path.isabs(run_payload["stdout_path"]))

        runs_io = self.make_io()
        self.assertEqual(main(["runs", "--json"], self.make_run_ctx(runs_io, service)), 0)
        runs_payload = json.loads(runs_io["stdout"].getvalue())
        self.assertEqual(runs_payload["runs"][0]["run_id"], run_id)
        self.assertEqual(runs_payload["runs"][0]["status"], "failed")
        self.assertEqual(runs_payload["runs"][0]["cwd"], os.path.abspath(target_dir))
        self.assertEqual(runs_payload["runs"][0]["artifacts"]["stdout_path"], run_payload["stdout_path"])
        self.assertIn(capacity_message, runs_payload["runs"][0]["error"]["message"])

        status_io = self.make_io()
        self.assertEqual(main(["run-status", run_id, "--json"], self.make_run_ctx(status_io, service)), 0)
        status_payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(status_payload["run"]["run_id"], run_id)
        self.assertEqual(status_payload["run"]["exit_code"], 1)

        report_io = self.make_io()
        self.assertEqual(main(["run-report", run_id, "--json"], self.make_run_ctx(report_io, service)), 0)
        report_payload = json.loads(report_io["stdout"].getvalue())
        self.assertEqual(report_payload["report"]["run"]["run_id"], run_id)
        self.assertEqual(report_payload["report"]["artifacts"]["stdout_path"], run_payload["stdout_path"])
        self.assertIn(capacity_message, report_payload["report"]["error"]["message"])

    def test_run_missing_provider_cli_returns_json_error(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **_kwargs):
            raise FileNotFoundError("codex")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 127)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "provider_cli_not_found")
        self.assertEqual(payload["exit_code"], 127)
        self.assertTrue(os.path.isabs(payload["transcript_path"]))

    def test_run_provider_spawn_os_error_returns_json_error(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **_kwargs):
            raise PermissionError("permission denied")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 126)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "provider_start_failed")
        self.assertEqual(payload["exit_code"], 126)
        self.assertTrue(os.path.isabs(payload["transcript_path"]))

    def test_run_rejects_missing_cwd_before_provider_start(self):
        target_dir = self.make_temp_dir()
        missing_dir = os.path.join(target_dir, "missing")
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **_kwargs):
            raise AssertionError("invalid cwd must not launch provider")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", missing_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "invalid_cwd")
        self.assertEqual(payload["exit_code"], None)
        self.assertEqual(payload["cwd"], os.path.abspath(missing_dir))

    def test_run_explicit_session_rejects_disabled_session(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["set_session_enabled"]("work", False)

        def spawn(_argv, **_kwargs):
            raise AssertionError("disabled sessions must not be launched")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        self.assertEqual(payload["error"]["code"], "session_disabled")
        self.assertIn("Session is disabled: work", payload["error"]["message"])

    def test_run_reasoning_power_conflict_has_stable_validation_code(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("work", "codex")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work",
            "--cwd", target_dir,
            "--prompt", "Do it",
            "--reasoning-effort", "low",
            "--power", "high",
            "--json",
        ], self.make_run_ctx(io_obj, service)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "cdx")
        # The two flags are aliases of one setting, so supplying conflicting
        # values is a mutual-exclusion failure, not an unsupported value. A bad
        # *value* still reports invalid_reasoning_effort (asserted below).
        self.assertEqual(payload["error"]["code"], "mutually_exclusive_arguments")
        self.assertEqual(payload["error"]["arguments"], ["--reasoning-effort", "--power"])
        self.assertIn("--reasoning-effort and --power", payload["error"]["message"])

    def test_run_unsupported_reasoning_effort_keeps_its_existing_code(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("work", "codex")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work",
            "--cwd", target_dir,
            "--prompt", "Do it",
            "--reasoning-effort", "turbo",
            "--json",
        ], self.make_run_ctx(io_obj, service)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "invalid_reasoning_effort")
        self.assertEqual(payload["error"]["arguments"], ["--reasoning-effort"])
        self.assertEqual(
            payload["error"]["allowed_values"],
            ["minimal", "low", "medium", "high", "xhigh"],
        )

    def test_run_validation_errors_are_specific_and_match_json_message(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        cases = [
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it"],
                "cdx run: --json is required.",
                "missing_required_argument", ["--json"],
            ),
            (
                ["main", "--cwd", target_dir, "--provider", "codex", "--prompt", "Do it", "--json"],
                "cdx run: cannot specify both a session name and --provider.",
                "mutually_exclusive_arguments", ["session", "--provider"],
            ),
            (
                ["--cwd", target_dir, "--prompt", "Do it", "--json"],
                "cdx run: specify a session name or --provider PROVIDER.",
                "missing_required_argument", ["session", "--provider"],
            ),
            (
                ["main", "--prompt", "Do it", "--json"],
                "cdx run: --cwd PATH is required.",
                "missing_required_argument", ["--cwd"],
            ),
            (
                ["main", "--cwd", target_dir, "--json"],
                "cdx run: specify exactly one prompt source: --prompt TEXT or --prompt-file PATH.",
                "missing_required_argument", ["--prompt-file", "--prompt"],
            ),
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it", "--prompt-file", __file__, "--json"],
                "cdx run: specify exactly one prompt source: --prompt TEXT or --prompt-file PATH.",
                "mutually_exclusive_arguments", ["--prompt-file", "--prompt"],
            ),
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it", "--kind", "audit", "--json"],
                "cdx run: invalid --kind 'audit'; allowed values: assistant|code-review.",
                "invalid_argument_value", ["--kind"],
            ),
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it", "--provider", "bogus", "--json"],
                "cdx run: invalid --provider 'bogus'; allowed values: codex|claude|antigravity|ollama.",
                "invalid_argument_value", ["--provider"],
            ),
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it", "--permission", "root", "--json"],
                "cdx run: invalid --permission 'root'; allowed values: review|default|auto|full|workspace-write|read-only|danger-full-access.",
                "invalid_argument_value", ["--permission"],
            ),
            (
                ["main", "--cwd", target_dir, "--prompt", "Do it", "--timeout-seconds", "0", "--json"],
                "cdx run: --timeout-seconds must be a positive number; got '0'.",
                "argument_value_out_of_range", ["--timeout-seconds"],
            ),
        ]

        seen_codes = set()
        for args, message, code, arguments in cases:
            with self.subTest(args=args):
                with self.assertRaisesRegex(CdxError, re.escape(message)):
                    _parse_run_args(args)

                io_obj = self.make_io()
                self.assertEqual(main(["run", *args], self.make_run_ctx(io_obj, service)), 1)
                payload = json.loads(io_obj["stdout"].getvalue())
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["action"], "run")
                self.assertEqual(payload["error"]["source"], "cdx")
                # Each failure class carries its own code and names the
                # offending arguments as data, so a caller branches without
                # ever parsing the human message.
                self.assertEqual(payload["error"]["code"], code)
                self.assertEqual(payload["error"]["arguments"], arguments)
                self.assertEqual(payload["error"]["message"], message)
                seen_codes.add(code)

        # The point of the change: these no longer collapse into one code.
        self.assertEqual(len(seen_codes), 4)
        self.assertNotIn("invalid_request", seen_codes)

    def test_run_unknown_flags_still_return_full_usage_contract(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "main", "--cwd", target_dir, "--prompt", "Do it", "--bogus", "--json"
        ], self.make_run_ctx(io_obj, service)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        # An unrecognized flag is its own class; the full usage line is still
        # returned for a human reading the terminal.
        self.assertEqual(payload["error"]["code"], "unknown_argument")
        self.assertEqual(payload["error"]["arguments"], [])
        self.assertEqual(payload["error"]["message"], RUN_USAGE)

    def test_run_auto_selects_session_from_provider(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("auto", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["update_auth_state"]("auto", lambda auth: {**auth, "status": "authenticated"})
        service["record_status"]("auto", {"remaining_5h_pct": 75, "remaining_week_pct": 75})

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "--provider", "codex", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "auto")
        self.assertEqual(payload["launcher"], "cdx")
        self.assertEqual(payload["usage"], {
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
        })

    def test_run_detach_returns_run_id_without_waiting(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        spawned = {}

        def spawn_detached(argv, **kwargs):
            spawned["argv"] = argv
            spawned["kwargs"] = kwargs
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_detached=spawn_detached)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["detached"])
        # The whole point: identity is available at launch, so a caller never
        # has to poll `cdx runs` to work out what it just started.
        self.assertTrue(payload["run_id"])
        self.assertIsNone(payload["error"])

        # The child is detached so the run outlives a launcher that exits (an
        # SSH command that returns, for instance). The mechanism is
        # platform-specific: POSIX gets its own session, Windows needs explicit
        # creation flags because start_new_session is ignored there.
        if sys.platform == "win32":
            flags = spawned["kwargs"]["creationflags"]
            self.assertTrue(flags & subprocess.DETACHED_PROCESS)
            self.assertTrue(flags & subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            self.assertTrue(spawned["kwargs"]["start_new_session"])
        self.assertNotIn("--detach", spawned["argv"])
        self.assertIn("--json", spawned["argv"])
        # The prompt reaches the child as a file, never on the command line.
        prompt_path = spawned["argv"][spawned["argv"].index("--prompt-file") + 1]
        with open(prompt_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "Do it")

    def test_run_detach_registers_the_run_before_returning(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        io_obj = self.make_io()
        child = _HeadlessChild(0)
        child.pid = os.getppid()  # a live pid, so the stale sweep leaves it alone
        ctx = self.make_run_ctx(io_obj, service, spawn_detached=lambda argv, **kw: child)
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--json"
        ], ctx), 0)
        run_id = json.loads(io_obj["stdout"].getvalue())["run_id"]

        status_io = self.make_io()
        self.assertEqual(main(["run-status", run_id, "--json"], self.make_run_ctx(status_io, service)), 0)
        status = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(status["run"]["run_id"], run_id)
        self.assertEqual(status["run"]["status"], "running")

    def test_run_detach_records_the_child_pid_not_the_launcher(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        # A live pid that is not this process: the record must move off the
        # launcher, and must still look alive to the stale sweep.
        child = _HeadlessChild(0)
        child.pid = os.getppid()

        io_obj = self.make_io()
        ctx = self.make_run_ctx(io_obj, service, spawn_detached=lambda argv, **kw: child)
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--json"
        ], ctx), 0)
        run_id = json.loads(io_obj["stdout"].getvalue())["run_id"]

        # The launcher exits immediately after this. If the record still
        # pointed at the launcher's pid, the stale sweep would mark the run
        # finished — and hand `runs --since` a completion that never happened.
        record = RunRegistry(service["base_dir"]).get(run_id)
        self.assertEqual(record["pid"], os.getppid())
        self.assertNotEqual(record["pid"], os.getpid())
        self.assertEqual(record["status"], "running")

    def test_run_detach_pins_the_session_the_parent_selected(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service, name="picked")

        spawned = {}

        def spawn_detached(argv, **_kwargs):
            spawned["argv"] = argv
            child = _HeadlessChild(0)
            child.pid = os.getppid()
            return child

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "--provider", "codex", "--cwd", target_dir, "--prompt", "Do it",
            "--detach", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_detached=spawn_detached)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["session"], "picked")
        # The child must not re-run auto-selection: it could land on a different
        # session than the one the launch payload just reported.
        self.assertIn("picked", spawned["argv"])
        self.assertNotIn("--provider", spawned["argv"])

    def test_detached_run_id_is_consumed_not_inherited(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        seen_env = {}

        def spawn(_argv, **kwargs):
            seen_env["env"] = dict(kwargs.get("env") or os.environ)
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        with mock.patch.dict(os.environ, {"CDX_RUN_ID": "outer-run"}):
            self.assertEqual(main([
                "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
            ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)
            # Left set, the provider inherits it and any nested `cdx run` the
            # agent makes claims this same run_id, wiping the outer run's
            # registry record and truncating its artifact files.
            self.assertIsNone(os.environ.get("CDX_RUN_ID"))

        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["run_id"], "outer-run")
        self.assertNotIn("CDX_RUN_ID", seen_env["env"])

    def test_detached_child_deletes_the_staged_prompt_file(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)
        prompt_path = os.path.join(self.make_temp_dir(), "cdx-run-x.prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            handle.write("secret prompt")

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        with mock.patch.dict(os.environ, {"CDX_RUN_ID": "child-run"}):
            self.assertEqual(main([
                "run", "work", "--cwd", target_dir, "--prompt-file", prompt_path, "--json"
            ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        # Prompts are kept out of everything else that persists; a detached run
        # must not leave a permanent cleartext copy in the log directory.
        self.assertFalse(os.path.exists(prompt_path))

    def test_ordinary_run_keeps_a_caller_supplied_prompt_file(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)
        prompt_path = os.path.join(self.make_temp_dir(), "task.prompt.txt")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            handle.write("mine to keep")

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt-file", prompt_path, "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        # Only a detached child cleans up, and only the copy cdx staged itself.
        self.assertTrue(os.path.exists(prompt_path))

    def test_run_warns_about_no_network_when_no_permission_is_given(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "gh pr list", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        # The most common invocation: no --permission at all. codex still runs
        # sandboxed by default, so this is exactly the silent degradation the
        # warning exists for — it must not be exempt.
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["network_disabled_by_permission"],
        )

    def test_run_tail_on_a_run_that_has_not_written_yet(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        registry = RunRegistry(service["base_dir"])
        missing = os.path.join(self.make_temp_dir(), "not-yet.stdout.log")
        registry.start("fresh", kind="assistant", session="work", provider="codex",
                       model=None, cwd=".", artifacts={"stdout_path": missing})

        io_obj = self.make_io()
        # launch detached -> tail immediately is the advertised flow; the child
        # has not written its first byte yet. "No output so far" is not fatal.
        self.assertEqual(main(["run-tail", "fresh", "--json"], self.make_run_ctx(io_obj, service)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["lines"], [])
        self.assertEqual(payload["status"], "running")

    def test_run_tail_missing_output_on_a_finished_run_is_an_error(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        registry = RunRegistry(service["base_dir"])
        missing = os.path.join(self.make_temp_dir(), "gone.stdout.log")
        registry.start("done", kind="assistant", session="work", provider="codex",
                       model=None, cwd=".", artifacts={"stdout_path": missing})
        registry.finish("done", status="succeeded")

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", "done", "--json"], self.make_run_ctx(io_obj, service)), 1)

        self.assertEqual(
            json.loads(io_obj["stdout"].getvalue())["error"]["code"],
            "run_output_unreadable",
        )

    def test_run_tail_drops_a_partial_leading_line(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        # One line larger than the read window, so the seek lands mid-line.
        body = (b"H" * (2 << 20)) + b"\nsecond line\n"
        run_id, _ = self._finished_run_with_output(service, body, run_id="huge")

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", run_id, "--lines", "10", "--json"],
                              self.make_run_ctx(io_obj, service)), 0)

        # Half of a line handed over as if it were whole is worse than one line
        # short, especially for codex's single-line JSON events.
        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["lines"], ["second line"])

    def test_schema_does_not_advertise_must_match_as_mutually_exclusive(self):
        io_obj = self.make_io()
        service = create_session_service({"base_dir": self.make_temp_dir()})
        self.assertEqual(main(["schema", "--json"], self.make_run_ctx(io_obj, service)), 0)
        schema = json.loads(io_obj["stdout"].getvalue())

        exclusive = {tuple(group["arguments"]) for group in schema["mutually_exclusive"]}
        must_match = {tuple(group["arguments"]) for group in schema["must_match"]}
        self.assertNotIn(("--reasoning-effort", "--power"), exclusive)
        self.assertIn(("--reasoning-effort", "--power"), must_match)

        # cdx accepts both when they agree, so validation generated from the
        # schema must not reject it.
        target = self.make_temp_dir()
        _parse_run_args(["main", "--cwd", target, "--prompt", "x",
                         "--reasoning-effort", "low", "--power", "low", "--json"])

    def test_schema_publishes_every_code_the_run_commands_emit(self):
        io_obj = self.make_io()
        service = create_session_service({"base_dir": self.make_temp_dir()})
        self.assertEqual(main(["schema", "--json"], self.make_run_ctx(io_obj, service)), 0)
        published = set()
        for group in json.loads(io_obj["stdout"].getvalue())["error_codes"].values():
            published.update(group)

        # An agent matching exhaustively over the advertised list must not fall
        # through on a code it will certainly see.
        for code in ("invalid_reasoning_effort", "run_not_found", "run_output_unavailable",
                     "run_output_unreadable", "no_suitable_session", "provider_failed"):
            self.assertIn(code, published)

    def test_run_detach_spawn_failure_stays_a_json_error(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn_detached(_argv, **_kwargs):
            raise FileNotFoundError("no such executable")

        io_obj = self.make_io()
        # A --json caller must get a payload, never a raw traceback.
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_detached=spawn_detached)), 126)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("Failed to start detached cdx run", payload["error"]["message"])

    def test_run_detached_child_reuses_the_run_id_it_was_given(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        with mock.patch.dict(os.environ, {"CDX_RUN_ID": "fixed-run-id"}):
            self.assertEqual(main([
                "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
            ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        # Parent and detached child must agree on the identity the parent
        # already reported to the caller.
        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["run_id"], "fixed-run-id")

    def test_run_warns_when_permission_costs_network_access(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it",
            "--permission", "review", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        # The run succeeded; that is exactly why the warning has to be there.
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["exit_code"], 0)
        codes = [warning["code"] for warning in payload["warnings"]]
        self.assertEqual(codes, ["network_disabled_by_permission"])

    def test_run_does_not_warn_when_permission_keeps_network(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it",
            "--permission", "full", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["warnings"], [])

    def test_run_reads_prompt_from_stdin(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        seen = {}

        def spawn(argv, **kwargs):
            seen["argv"] = argv
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        ctx = self.make_run_ctx(
            io_obj, service, spawn_headless=spawn, prompt_stdin=io.StringIO("piped prompt — é"),
        )
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt-file", "-", "--json"
        ], ctx), 0)

        self.assertTrue(json.loads(io_obj["stdout"].getvalue())["ok"])
        # The prompt is the last arg (cdx prefixes its own preamble); assert the
        # piped text arrived intact, non-ASCII included.
        self.assertTrue(seen["argv"][-1].endswith("piped prompt — é"))

    def test_run_refuses_stdin_prompt_from_a_terminal(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        class _Tty(io.StringIO):
            def isatty(self):
                return True

        io_obj = self.make_io()
        ctx = self.make_run_ctx(io_obj, service, prompt_stdin=_Tty(""))
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt-file", "-", "--json"
        ], ctx), 1)

        error = json.loads(io_obj["stdout"].getvalue())["error"]
        self.assertEqual(error["code"], "invalid_argument_value")
        self.assertEqual(error["arguments"], ["--prompt-file"])

    def test_run_tail_returns_the_last_lines_of_a_running_run(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        body = "".join(f"line {index}\n" for index in range(1, 11)).encode("utf-8")
        run_id, stdout_path = self._finished_run_with_output(service, body)

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", run_id, "--lines", "3", "--json"],
                              self.make_run_ctx(io_obj, service)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["lines"], ["line 8", "line 9", "line 10"])
        self.assertEqual(payload["stdout_path"], stdout_path)
        self.assertEqual(payload["status"], "running")

    def test_run_tail_survives_undecodable_output(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        run_id, _ = self._finished_run_with_output(service, b"before\n\xff\xfe bad bytes\nafter\n")

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", run_id, "--json"], self.make_run_ctx(io_obj, service)), 0)

        # Replacement characters, not an exception: the caller asked what the
        # run is doing, and a provider writing odd bytes is not a reason to fail.
        self.assertEqual(len(json.loads(io_obj["stdout"].getvalue())["lines"]), 3)

    def test_run_tail_reports_a_missing_output_path_distinctly(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        registry = RunRegistry(service["base_dir"])
        registry.start("no-artifacts", kind="assistant", session="work",
                       provider="codex", model=None, cwd=".")

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", "no-artifacts", "--json"],
                              self.make_run_ctx(io_obj, service)), 1)

        self.assertEqual(
            json.loads(io_obj["stdout"].getvalue())["error"]["code"],
            "run_output_unavailable",
        )

    def test_run_tail_unknown_run_matches_run_status(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})

        io_obj = self.make_io()
        self.assertEqual(main(["run-tail", "nope", "--json"], self.make_run_ctx(io_obj, service)), 1)

        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["error"]["code"], "run_not_found")

    def test_run_tail_rejects_out_of_range_lines_before_reading(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        run_id, stdout_path = self._finished_run_with_output(service, b"x\n")
        os.remove(stdout_path)  # unreadable: proves validation happens first

        io_obj = self.make_io()
        # Like `run-status`, argument failures on run-tail bubble to the CLI
        # entry point rather than being caught per-command; the structured code
        # survives that path too.
        with self.assertRaises(CdxError) as caught:
            main(["run-tail", run_id, "--lines", "0", "--json"], self.make_run_ctx(io_obj, service))

        error = json.loads(format_json_error(caught.exception))["error"]
        self.assertEqual(error["code"], "argument_value_out_of_range")
        self.assertEqual(error["arguments"], ["--lines"])

    def test_schema_matches_what_the_run_parser_accepts(self):
        io_obj = self.make_io()
        service = create_session_service({"base_dir": self.make_temp_dir()})
        self.assertEqual(main(["schema", "--json"], self.make_run_ctx(io_obj, service)), 0)
        schema = json.loads(io_obj["stdout"].getvalue())

        target = self.make_temp_dir()
        base = ["main", "--cwd", target, "--prompt", "Do it", "--json"]

        # Every advertised value must parse, and the parser must reject one the
        # schema does not advertise. This is the guard the ollama
        # --experimental-yolo mapping (issue #8) never had: a hand-copied enum
        # in a downstream caller drifted from cdx and nobody noticed.
        for permission in schema["enums"]["permission"]["accepted"]:
            _parse_run_args([*base, "--permission", permission])
        with self.assertRaises(CdxError):
            _parse_run_args([*base, "--permission", "not-a-permission"])

        for kind in schema["enums"]["kind"]["accepted"]:
            _parse_run_args([*base, "--kind", kind])
        with self.assertRaises(CdxError):
            _parse_run_args([*base, "--kind", "not-a-kind"])

        for effort in schema["enums"]["reasoning_effort"]["accepted"]:
            _parse_run_args([*base, "--reasoning-effort", effort])
        with self.assertRaises(CdxError):
            _parse_run_args([*base, "--reasoning-effort", "turbo"])

        for provider in schema["enums"]["provider"]["accepted"]:
            _parse_run_args(["--cwd", target, "--prompt", "Do it", "--json", "--provider", provider])
        with self.assertRaises(CdxError):
            _parse_run_args(["--cwd", target, "--prompt", "Do it", "--json", "--provider", "nope"])

    def test_schema_declares_the_mutually_exclusive_pairs_it_enforces(self):
        io_obj = self.make_io()
        service = create_session_service({"base_dir": self.make_temp_dir()})
        self.assertEqual(main(["schema", "--json"], self.make_run_ctx(io_obj, service)), 0)
        schema = json.loads(io_obj["stdout"].getvalue())

        declared = {tuple(group["arguments"]) for group in schema["mutually_exclusive"]}
        self.assertIn(("session", "--provider"), declared)

        target = self.make_temp_dir()
        with self.assertRaises(CdxError):
            _parse_run_args(["main", "--provider", "codex", "--cwd", target, "--prompt", "x", "--json"])

    def test_selection_policy_is_built_from_the_ranking(self):
        from src.session_ranking import RANKING_FACTORS, selection_policy

        policy = selection_policy()

        # Derived, so reordering RANKING_FACTORS changes what cdx publishes
        # without anyone editing a string.
        self.assertEqual([f["name"] for f in policy["factors"]], list(RANKING_FACTORS))
        self.assertNotIn("require_ready", [f["name"] for f in policy["factors"]])
        self.assertIn("require_ready", [f["name"] for f in policy["filters"]])

    def test_run_warns_when_it_selects_a_session_with_no_status(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("blind", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["update_auth_state"]("blind", lambda auth: {**auth, "status": "authenticated"})

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "--provider", "codex", "--cwd", target_dir, "--prompt", "Do it",
            "--permission", "full", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        # No availability was ever recorded, so the ranking chose on nothing.
        self.assertIn(
            "session_selected_without_status",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_run_no_suitable_session_includes_launcher(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("loggedout", "codex")
        service["update_auth_state"]("loggedout", lambda auth: {**auth, "status": "logged_out"})

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "--provider", "codex", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "run")
        self.assertEqual(payload["launcher"], "cdx")
        self.assertEqual(payload["error"]["code"], "no_suitable_session")

    def test_run_timeout_uses_provider_timeout_error(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = service["create_session"]("work", "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)

        def spawn(_argv, **_kwargs):
            return _TimeoutChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Slow", "--timeout-seconds", "0.01", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 124)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["source"], "provider")
        self.assertEqual(payload["error"]["code"], "provider_timeout")
        self.assertEqual(payload["exit_code"], 124)


    def test_failover_continues_the_task_on_the_next_account(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        for name in ("work1", "work2"):
            self._authenticated_codex_session(service, name)
        # work1 is spent, work2 is not, so the ranking prefers work2 as the
        # successor and the corroboration step agrees work1 is exhausted.
        service["record_status"]("work1", {"remaining_5h_pct": 0, "remaining_week_pct": 0})

        seen = []

        def spawn(_argv, **kwargs):
            running = RunRegistry(target_dir).list(limit=1)[0]
            seen.append(running["session"])
            if running["session"] == "work1":
                kwargs["stdout"].write(json.dumps(
                    {"type": "error", "payload": {"kind": "rate_limit"}}
                ) + "\n")
                return _HeadlessChild(1)
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work1", "--cwd", target_dir, "--prompt", "Do it", "--failover", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        self.assertEqual(seen, ["work1", "work2"])
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "work2")

        runs = RunRegistry(target_dir).list(limit=10)
        self.assertEqual(len(runs), 1, "a failover is one run, not several")
        self.assertEqual(
            [item["session"] for item in runs[0]["occupancies"]], ["work1", "work2"]
        )

    def test_failover_reports_exhausting_every_account_distinctly(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service, "only")
        service["record_status"]("only", {"remaining_5h_pct": 0, "remaining_week_pct": 0})

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}) + "\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "only", "--cwd", target_dir, "--prompt", "Do it", "--failover", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "failover_exhausted")

    def test_without_failover_a_rate_limited_run_fails_as_before(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        for name in ("work1", "work2"):
            self._authenticated_codex_session(service, name)
        service["record_status"]("work1", {"remaining_5h_pct": 0, "remaining_week_pct": 0})

        attempts = []

        def spawn(_argv, **kwargs):
            attempts.append(1)
            kwargs["stdout"].write(json.dumps({"type": "error", "payload": {"kind": "rate_limit"}}) + "\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work1", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)

        self.assertEqual(len(attempts), 1)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "provider_failed")

    def test_detach_and_failover_are_rejected_together(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service, "work")

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--failover", "--json"
        ], self.make_run_ctx(io_obj, service)), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "mutually_exclusive_arguments")
