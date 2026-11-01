"""Tests for run, runs, run-status, run-report, run-tail, select, schema.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import io
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
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

    def test_remote_option_keeps_existing_run_options(self):
        parsed = _parse_run_args(["work", "--remote", "agent@worker", "--cwd", "/remote/project", "--prompt", "Work",
                                  "--permission", "full", "--budget", "2", "--label", "checks", "--detach", "--json"])
        self.assertEqual(parsed["remote"], "agent@worker")
        self.assertEqual(parsed["permission"], "full")
        self.assertEqual(parsed["budget"], 2)
        self.assertTrue(parsed["detach"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Isolated Codex runs are Linux-only")
    def test_source_project_is_captured_before_worktree_isolation(self):
        directory = pathlib.Path(self.make_temp_dir())
        source = directory / "source" / "app"
        source.mkdir(parents=True)
        subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "--allow-empty", "-m", "Initial"], check=True, capture_output=True)
        tree = directory / "missions" / "disposable"
        subprocess.run(["git", "-C", str(source), "worktree", "add", "-b", "mission", str(tree)],
                       check=True, capture_output=True)
        service = create_session_service({"base_dir": str(directory / "cdx")})
        session = self._authenticated_codex_session(service)
        from test_remote_run_py import credential
        pathlib.Path(session['authHome'], 'auth.json').write_text(json.dumps(credential()))
        calls = []

        def confine(command, checkout, **kwargs):
            running = RunRegistry(service["base_dir"]).list(limit=1)[0]
            self.assertEqual(running["project"], str(source.resolve()))
            self.assertEqual(running["cwd"], str(tree))
            calls.append(checkout)
            return command, kwargs["source"]

        for cwd, isolated in ((source, False), (tree, False), (tree, True)):
            output = self.make_io()
            # CI runners may lack the tmpfs this test does not exercise; the mount is covered in test_workspace_sandbox_auth_py.
            private = tempfile.TemporaryDirectory()
            self.addCleanup(private.cleanup)
            pathlib.Path(private.name, "auth.json").write_text(json.dumps({**credential(), "tokens": {**credential()["tokens"], "refresh_token": ""}}))
            pathlib.Path(private.name, "sessions").mkdir()
            home = mock.MagicMock()
            home.return_value.__enter__.return_value = private.name
            with mock.patch("src.workspace_sandbox.sandbox_command", side_effect=confine), mock.patch("src.workspace_sandbox.private_auth_home", home):
                self.assertEqual(main(["run", "work", "--cwd", str(cwd), "--prompt", "Work", "--json",
                                       *(["--isolate-workspace"] if isolated else [])],
                                      self.make_run_ctx(output, service, spawn_headless=lambda *a, **kw: _HeadlessChild(0))), 0)
            payload = json.loads(output["stdout"].getvalue())
            self.assertEqual(payload["project"], str(source.resolve()))
            self.assertEqual(payload["cwd"], str(cwd))
        self.assertEqual(calls, [tree])
        subprocess.run(["git", "-C", str(source), "worktree", "remove", "--force", str(tree)], check=True, capture_output=True)
        from src.commands.status import _stats_group
        history = service["get_launch_history"]("work", limit=0)
        self.assertEqual(len(history), 3)
        self.assertEqual({_stats_group(row, "project") for row in history}, {str(source.resolve())})
        self.assertEqual({row["cwd"] for row in history}, {str(source), str(tree)})

    @unittest.skipUnless(sys.platform.startswith("linux"), "Isolated observation is Linux-only")
    def test_isolated_model_evidence_survives_closeout_without_conversation(self):
        self._check_isolated_observation()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Isolated observation is Linux-only")
    def test_isolated_budget_uses_live_native_counters(self):
        self._check_isolated_observation(budget="0.000001")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Isolated observation is Linux-only")
    def test_isolated_budget_fails_for_unpriceable_native_counters(self):
        self._check_isolated_observation(budget="1", model="unknown-price")

    def _check_isolated_observation(self, budget=None, model="gpt-6.1-sol"):
        from datetime import datetime, timezone

        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        session = self._authenticated_codex_session(service)
        from test_remote_run_py import credential
        pathlib.Path(session['authHome'], 'auth.json').write_text(json.dumps(credential()))
        mounted = []
        counters = {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20}

        def confine(command, checkout, **kwargs):
            mounted.append(pathlib.Path(kwargs["observation_home"]))
            self.assertNotEqual(str(mounted[-1]), service["get_session"]("work")["authHome"])
            return command, kwargs["source"]

        def spawn(_argv, **kwargs):
            timestamp = datetime.now(timezone.utc).isoformat()
            records = [{"type": "session_meta", "payload": {"id": "22222222-2222-4222-8222-222222222222"}},
                       {"type": "turn_context", "timestamp": timestamp,
                        "payload": {"model": model, "turn_id": "turn-1", "prompt": "PRIVATE"}},
                       {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": counters}}},
                       {"type": "response_item", "payload": {"text": "PRIVATE"}}]
            (mounted[-1] / "rollout-test-22222222-2222-4222-8222-222222222222.jsonl").write_text("\n".join(map(json.dumps, records)))
            kwargs["stdout"].write(json.dumps({"type": "thread.started", "thread_id": "22222222-2222-4222-8222-222222222222"}) + "\n")
            if budget is None:
                kwargs["stdout"].write(json.dumps({"type": "turn.completed", "usage": counters}) + "\n")
            kwargs["stdout"].flush()
            return _HeadlessChild()

        output = self.make_io()
        with mock.patch("src.workspace_sandbox.sandbox_command", side_effect=confine):
            self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--json", "--isolate-workspace",
                                   *(["--budget", budget] if budget else [])],
                                  self.make_run_ctx(output, service, spawn_headless=spawn)), 125 if budget else 0)
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["usage_model"], model)
        if model == "unknown-price":
            self.assertIsNone(payload["cost_usd"])
            self.assertEqual(payload["error"]["code"], "budget_unverifiable")
        else:
            self.assertGreater(payload["cost_usd"], 0)
            if budget:
                self.assertEqual(payload["error"]["code"], "budget_exceeded")
        self.assertFalse(mounted[0].exists())
        self.assertNotIn("PRIVATE", json.dumps(payload))
        stored = RunRegistry(directory).get(payload["run_id"])
        history = service["get_launch_history"]("work", limit=1)[0]
        for key in ("usage", "usage_model", "usage_evidence", "cost_usd", "cost_status", "cost_reason"):
            self.assertEqual(stored[key], payload[key])
            self.assertEqual(history[key], payload[key])
        output = self.make_io()
        main(["history", "--json"], self.make_run_ctx(output, service))
        self.assertEqual(json.loads(output["stdout"].getvalue())["history"][0]["cost_usd"], payload["cost_usd"])
        output = self.make_io()
        main(["stats", "--json"], self.make_run_ctx(output, service))
        stats = json.loads(output["stdout"].getvalue())["stats"][0]
        if model == "unknown-price":
            self.assertEqual(stats["priced_runs"], 0)
            self.assertEqual(stats["unpriced_reasons"], {"model_price_unknown": 1})
        else:
            self.assertEqual(stats["cost_usd"], payload["cost_usd"])

    def test_history_cost_uses_stats_prices_and_preserves_unknowns(self):
        from src.run_usage import estimate_cost, normalize_usage

        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)
        usage = normalize_usage(input_tokens=100, cache_read_tokens=50, output_tokens=10)
        for model, measured in (("gpt-6.1-sol", usage), ("unknown-model", usage),
                                ("gpt-6.1-sol", None), (None, usage)):
            service["record_launch_history"]("work", {"usage": measured, "usage_model": model})
        output = self.make_io()
        with mock.patch.dict(os.environ, {"CDX_TOKEN_PRICES": json.dumps({"gpt-6.1-sol": {"input": 2, "output": 8}})}):
            self.assertEqual(main(["history", "--json"], self.make_run_ctx(output, service)), 0)
            entries = json.loads(output["stdout"].getvalue())["history"]
            priced = [row for row in entries if row["cost_usd"] is not None]
            self.assertEqual(len(priced), 1)
            self.assertEqual(priced[0]["cost_usd"], estimate_cost(usage, "gpt-6.1-sol"))
            output = self.make_io()
            self.assertEqual(main(["stats", "--json"], self.make_run_ctx(output, service)), 0)
            self.assertEqual(json.loads(output["stdout"].getvalue())["stats"][0]["cost_usd"], priced[0]["cost_usd"])

    def test_run_budget_stops_live_provider_and_persists_spending(self):
        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)
        child = _HeadlessChild()

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({"model": "gpt-6.1-sol", "usage": {
                "input_tokens": 1000000, "output_tokens": 1000000}}) + "\n")
            kwargs["stdout"].flush()
            return child

        output = self.make_io()
        self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", "0.01", "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "budget_exceeded")
        self.assertEqual(payload["exit_code"], 125)
        self.assertGreater(payload["error"]["spent_usd"], 0.01)
        self.assertEqual(payload["cost_usd"], payload["error"]["spent_usd"])
        self.assertNotEqual(child.returncode, 0)
        stored = RunRegistry(directory).get(payload["run_id"])
        self.assertEqual(stored["error"]["code"], "budget_exceeded")
        self.assertEqual(service["get_launch_history"]("work")[0]["exit_code"], 125)

    @mock.patch("src.commands.runs.time.sleep")
    def test_run_budget_includes_capacity_recovery_attempts(self, sleep):
        from src.run_usage import estimate_cost, normalize_usage

        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)
        calls = []
        cost = estimate_cost(normalize_usage(input_tokens=100), "gpt-6.1-sol")

        def spawn(_argv, **kwargs):
            calls.append(True)
            kwargs["stdout"].write(json.dumps({"model": "gpt-6.1-sol", "usage": {"input_tokens": 100}}) + "\n")
            kwargs["stdout"].flush()
            kwargs["stderr"].write("Selected model is at capacity. Please try a different model.\n")
            return _HeadlessChild(1)

        output = self.make_io()
        self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", str(cost * 1.5), "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(payload["attempts"]), 2)
        self.assertAlmostEqual(sum(row["cost_usd"] for row in payload["attempts"]), cost * 2)
        self.assertAlmostEqual(payload["error"]["spent_usd"], cost * 2)
        sleep.assert_called_once_with(1)
        history = service["get_launch_history"]("work", limit=0)
        self.assertEqual(len({row["stdout_path"] for row in history}), 2)
        self.assertEqual(len({row["attempt_id"] for row in history}), 2)
        self.assertTrue(all(pathlib.Path(row["stdout_path"]).exists() for row in history))

    def test_budget_does_not_mix_two_different_stdout_measurements(self):
        from src.commands.runs import _budget_observation
        from src.run_usage import empty_usage

        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)
        observations = []

        def observe(*args):
            observations.append(True)
            if len(observations) == 1:
                return {"usage": empty_usage(), "usage_model": None}
            return _budget_observation(*args)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({"model": "gpt-6.1-sol", "usage": {"input_tokens": 1000000}}) + "\n")
            kwargs["stdout"].flush()
            return _HeadlessChild()

        output = self.make_io()
        with mock.patch("src.commands.runs._budget_observation", side_effect=observe):
            self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", "0.01", "--json"],
                                  self.make_run_ctx(output, service, spawn_headless=spawn)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "budget_exceeded")
        self.assertEqual(len(observations), 2)

    def test_run_budget_unknown_price_does_not_claim_zero_cost(self):
        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({"model": "unknown-price", "usage": {"input_tokens": 1000000}}) + "\n")
            kwargs["stdout"].flush()
            return _HeadlessChild()

        output = self.make_io()
        self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", "1", "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertIsNone(payload["cost_usd"])
        self.assertEqual(payload["error"]["code"], "budget_unverifiable")
        self.assertEqual(payload["budget_status"], "unverifiable")
        self.assertEqual(payload["cost_reason"], "model_price_unknown")
        stored = RunRegistry(directory).get(payload["run_id"])
        self.assertEqual(stored["cost_reason"], payload["cost_reason"])
        self.assertEqual(stored["final_payload"], payload)

    def test_budget_distinguishes_no_measurement_missing_model_and_mixed_models(self):
        for models, measured, expected, reason in (([], False, 0, "usage_not_measured"),
                                                   ([], True, 125, "model_not_observed"),
                                                   (["gpt-6.1-sol", "gpt-6-sol"], True, 125, "mixed_models_without_counters")):
            with self.subTest(models=models, measured=measured):
                directory = self.make_temp_dir()
                service = create_session_service({"base_dir": directory})
                self._authenticated_codex_session(service)

                def spawn(_argv, measured=measured, models=models, **kwargs):
                    if measured:
                        for model in models or [None]:
                            record = {"type": "turn.completed", "usage": {"input_tokens": 10}}
                            if model:
                                record["model"] = model
                            kwargs["stdout"].write(json.dumps(record) + "\n")
                        kwargs["stdout"].flush()
                    return _HeadlessChild()

                output = self.make_io()
                self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", "1", "--json"],
                                      self.make_run_ctx(output, service, spawn_headless=spawn)), expected)
                payload = json.loads(output["stdout"].getvalue())
                self.assertIsNone(payload["cost_usd"])
                self.assertEqual(payload["cost_reason"], reason)
                self.assertEqual(payload["budget_status"], "unverifiable" if measured else "usage_not_measured")
                if measured:
                    self.assertEqual(payload["error"]["code"], "budget_unverifiable")
                    self.assertEqual(len(service["get_launch_history"]("work", limit=0)), 1)

    def test_run_budget_detach_uses_cdx_supervisor_and_passes_budget(self):
        directory, service, _session, _transcript = self._continuation_parent()
        for continuation in (False, True):
            with self.subTest(continuation=continuation):
                output = self.make_io()
                with mock.patch("src.commands.runs.supports_native_background") as native:
                    child = mock.Mock(return_value=_HeadlessChild())
                    extra = ["--continue-run", "parent"] if continuation else ["work"]
                    self.assertEqual(main(["run", *extra, "--cwd", directory, "--prompt", "Fix", "--budget", "0.5",
                                           "--detach", "--json"], self.make_run_ctx(output, service, spawn_detached=child)), 0)
                native.assert_not_called()
                argv = child.call_args.args[0]
                self.assertEqual(argv[argv.index("--budget") + 1], "0.5")
                if continuation:
                    self.assertEqual(argv[argv.index("--continue-run") + 1], "parent")

    def test_continued_budget_counts_only_new_transcript_usage(self):
        from src.run_usage import estimate_cost, normalize_usage

        directory, service, _session, transcript = self._continuation_parent()
        def record(tokens):
            return json.dumps({"type": "turn_context", "payload": {"model": "gpt-6.1-sol"}}) + "\n" + json.dumps({"payload": {"type": "token_count",
                                           "info": {"total_token_usage": {"input_tokens": tokens, "output_tokens": 0}}}}) + "\n"
        transcript.write_text(record(1000000), encoding="utf-8")
        observed = []

        class Child(_HeadlessChild):
            def wait(self, timeout=None):
                if timeout == 0.25 and not observed:
                    observed.append(True)
                    transcript.write_text(record(1000100), encoding="utf-8")
                    raise subprocess.TimeoutExpired("codex", timeout)
                return super().wait(timeout)

        child = Child()
        output = self.make_io()
        cost = estimate_cost(normalize_usage(input_tokens=100, output_tokens=0), "gpt-6.1-sol")
        self.assertEqual(main(["run", "--continue-run", "parent", "--cwd", directory, "--prompt", "Fix",
                               "--budget", str(cost), "--json"],
                              self.make_run_ctx(output, service, spawn_headless=lambda *_args, **_kwargs: child)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertTrue(observed, "The existing conversation must not exhaust the new run's budget")
        self.assertAlmostEqual(payload["error"]["spent_usd"], cost)
        self.assertEqual(payload["usage"]["input_tokens"], 100)

    def test_claude_budget_sums_live_transcript_messages_before_final_output(self):
        from src.run_usage import estimate_cost, normalize_usage

        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        session = service["create_session"]("work", "claude")
        auth = _AuthHarness(initial_auth={session["authHome"]: True})
        model = "claude-sonnet-5-5"
        cost = estimate_cost(normalize_usage(input_tokens=150), model)
        transcript = None

        def message(identifier):
            return json.dumps({"type": "assistant", "message": {"id": identifier, "model": model,
                                                                 "usage": {"input_tokens": 100}}}) + "\n"

        class Child(_HeadlessChild):
            def wait(self, timeout=None):
                if timeout == 0.25:
                    with transcript.open("a", encoding="utf-8") as handle:
                        handle.write(message("second"))
                    raise subprocess.TimeoutExpired("claude", timeout)
                return super().wait(timeout)

        def spawn(argv, **_kwargs):
            nonlocal transcript
            identifier = argv[argv.index("--session-id") + 1]
            transcript = pathlib.Path(session["authHome"]) / ".claude/projects/repo" / f"{identifier}.jsonl"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text(message("first"), encoding="utf-8")
            return Child()

        output = self.make_io()
        self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", str(cost), "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn, spawn_sync=auth.spawn_sync)), 125)
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["usage"]["input_tokens"], 200)
        self.assertEqual(payload["error"]["code"], "budget_exceeded")
        self.assertEqual(pathlib.Path(payload["stdout_path"]).read_text(), "")

    def test_budget_terminates_a_real_provider_process(self):
        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        self._authenticated_codex_session(service)
        children = []
        sentinel = pathlib.Path(directory) / "should-not-finish"
        program = (
            "import json, pathlib, time; "
            "print(json.dumps({'model': 'gpt-6.1-sol', 'usage': {'input_tokens': 1000000}}), flush=True); "
            "time.sleep(10); pathlib.Path('should-not-finish').touch()"
        )

        def spawn(_argv, **kwargs):
            child = subprocess.Popen([sys.executable, "-u", "-c", program], **kwargs)
            children.append(child)
            return child

        output = self.make_io()
        try:
            self.assertEqual(main(["run", "work", "--cwd", directory, "--prompt", "Work", "--budget", "0.01",
                                   "--timeout-seconds", "5", "--json"],
                                  self.make_run_ctx(output, service, spawn_headless=spawn)), 125)
            self.assertEqual(json.loads(output["stdout"].getvalue())["error"]["code"], "budget_exceeded")
            self.assertIsNotNone(children[0].poll())
            self.assertFalse(sentinel.exists())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.wait()

    def test_run_budget_rejects_invalid_values(self):
        from src.errors import CdxArgumentError

        for value in ("0", "-1", "nan", "inf", "-inf", "text"):
            with self.subTest(value=value), self.assertRaises(CdxArgumentError) as error:
                _parse_run_args(["work", "--cwd", ".", "--prompt", "Work", "--budget", value, "--json"])
            self.assertEqual(error.exception.arguments, ("--budget",))

    def _continuation_parent(self, provider="codex", model="gpt-6.1-sol", effort="high", status="succeeded"):
        directory = self.make_temp_dir()
        service = create_session_service({"base_dir": directory})
        session = (self._authenticated_codex_session(service) if provider == "codex"
                   else service["create_session"]("work", provider))
        identifier = "12345678-1234-1234-1234-123456789abc"
        if provider == "codex":
            transcript = pathlib.Path(session["authHome"]) / "sessions" / f"rollout-test-{identifier}.jsonl"
        else:
            transcript = pathlib.Path(session["authHome"]) / ".claude/projects/repo" / f"{identifier}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text('{}\n', encoding="utf-8")
        registry = RunRegistry(directory)
        registry.start("parent", kind="assistant", session="work", provider=provider, model=model, cwd=directory,
                       conversation_id=identifier, launch={"model": model, "power": effort}, reasoning_effort=effort)
        if status != "running":
            registry.finish("parent", status=status, final_payload={"model": model, "reasoning_effort": effort,
                                                                   "conversation_id": identifier})
        return directory, service, session, transcript

    def test_continue_run_reuses_exact_conversation_and_pins_settings_for_both_providers(self):
        for provider, model in (("codex", "gpt-6.1-sol"), ("claude", "claude-sonnet-5-5")):
            with self.subTest(provider=provider):
                directory = self.make_temp_dir()
                service = create_session_service({"base_dir": directory})
                session = (self._authenticated_codex_session(service) if provider == "codex"
                           else service["create_session"]("work", "claude"))
                service["set_launch_settings"]("work", {"model": model, "power": "high"})
                auth = _AuthHarness(initial_auth={session["authHome"]: True})
                identifier = "12345678-1234-1234-1234-123456789abc"
                commands = []

                def spawn(argv, commands=commands, provider=provider, session=session, identifier=identifier, model=model, **kwargs):
                    commands.append(argv)
                    if provider == "codex":
                        transcript = pathlib.Path(session["authHome"]) / "sessions" / f"rollout-test-{identifier}.jsonl"
                        count = len(commands)
                        cumulative = {"input_tokens": 100 * count, "cached_input_tokens": 72 * count,
                                      "output_tokens": count * (count + 1) // 2}
                        record = {"payload": {"type": "token_count", "info": {"total_token_usage": cumulative}}}
                        events = [{"type": "thread.started", "thread_id": identifier},
                                  {"type": "turn.completed", "usage": cumulative}]
                    else:
                        flag = "--resume" if "--resume" in argv else "--session-id"
                        native_id = argv[argv.index(flag) + 1]
                        transcript = pathlib.Path(session["authHome"]) / ".claude/projects/repo" / f"{native_id}.jsonl"
                        record = {"type": "assistant", "message": {"model": model}}
                        events = [{"type": "result", "session_id": native_id, "modelUsage": {model: {}},
                                   "usage": {"input_tokens": 20, "cache_creation_input_tokens": 8,
                                             "cache_read_input_tokens": 72, "output_tokens": len(commands)}}]
                    transcript.parent.mkdir(parents=True, exist_ok=True)
                    transcript.write_text(json.dumps(record) + "\n", encoding="utf-8")
                    if provider == "codex":
                        with transcript.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps({"type": "turn_context", "payload": {"model": model}}) + "\n")
                    for event in events:
                        kwargs["stdout"].write(json.dumps(event) + "\n")
                    return _HeadlessChild(0)

                def invoke(extra, directory=directory, service=service, spawn=spawn, auth=auth):
                    output = self.make_io()
                    result = main(["run", "--cwd", directory, "--prompt", "Fix the next issue", *extra, "--json"],
                                  self.make_run_ctx(output, service, spawn_headless=spawn, spawn_sync=auth.spawn_sync))
                    payload = json.loads(output["stdout"].getvalue())
                    self.assertEqual(result, 0, payload)
                    return payload

                cold = invoke(["work", "--project", directory])
                self.assertIsNone(cold["parent_run_id"])
                self.assertIsNotNone(cold["conversation_id"])
                service["set_launch_settings"]("work", {"model": "changed-model", "power": "low", "fallback_model": "other-model"})
                # Changing the profile's latest identity must not change the parent run's identity.
                if provider == "claude":
                    service["begin_conversation"]("work")
                continued = invoke(["--continue-run", cold["run_id"]])
                chained = invoke(["--continue-run", continued["run_id"], "--provider", provider])
                self.assertEqual(continued["parent_run_id"], cold["run_id"])
                self.assertEqual(chained["parent_run_id"], continued["run_id"])
                for record in (cold, continued, chained):
                    self.assertEqual(record["project"], directory)
                    self.assertEqual(record["project_source"], "operator")
                self.assertEqual(continued["conversation_id"], cold["conversation_id"])
                self.assertEqual(continued["model"], model)
                self.assertEqual(continued["reasoning_effort"], "high")
                self.assertEqual(continued["usage"]["output_tokens"], 2)
                self.assertEqual(continued["usage"]["cache_hit_ratio"], 0.72)
                for argv in commands[1:]:
                    self.assertEqual(argv[argv.index("--model") + 1], model)
                    if provider == "codex":
                        self.assertIn('model_reasoning_effort="high"', argv)
                        self.assertEqual(argv[argv.index("resume") + 1], cold["conversation_id"])
                    else:
                        self.assertEqual(argv[argv.index("--resume") + 1], cold["conversation_id"])
                        self.assertEqual(argv[argv.index("--effort") + 1], "high")
                        self.assertNotIn("--session-id", argv)
                        self.assertNotIn("--fallback-model", argv)
                stored = RunRegistry(directory).get(continued["run_id"])
                self.assertEqual(stored["parent_run_id"], cold["run_id"])
                self.assertEqual(stored["conversation_id"], cold["conversation_id"])
                history = service["get_launch_history"]("work", limit=0)
                self.assertEqual({h["parent_run_id"] for h in history}, {None, cold["run_id"], continued["run_id"]})
                self.assertEqual(service["get_session"]("work")["launch"]["model"], "changed-model")

    def test_continue_run_refuses_missing_expired_wrong_profile_and_changed_settings(self):
        cases = [
            (["--continue-run", "missing"], "continue_run_not_found", None),
            (["--continue-run", "parent", "other"], "continue_run_mismatch", None),
            (["--continue-run", "parent", "--provider", "claude"], "continue_run_mismatch", None),
            (["--continue-run", "parent"], "continue_run_unavailable", "expired"),
            (["--continue-run", "parent"], "continue_run_unavailable", "running"),
            (["--continue-run", "parent", "--model", "different"], "continue_run_settings_mismatch", None),
            (["--continue-run", "parent", "--power", "low"], "continue_run_settings_mismatch", None),
            (["--continue-run", "parent", "--failover"], "continue_run_settings_mismatch", None),
            (["--continue-run", "parent", "--isolate-workspace"], "continue_run_settings_mismatch", None),
            (["--continue-run", "parent"], "continue_run_unavailable", "unknown-settings"),
            (["--continue-run", "parent"], "continue_run_mismatch", "removed-profile"),
            (["--continue-run", "parent"], "continue_run_mismatch", "replaced-provider"),
        ]
        for extra, code, condition in cases:
            with self.subTest(extra=extra, condition=condition):
                directory, service, session, transcript = self._continuation_parent(
                    model=None if condition == "unknown-settings" else "gpt-6.1-sol",
                    status="running" if condition == "running" else "succeeded")
                if condition == "expired":
                    transcript.unlink()
                if condition in ("removed-profile", "replaced-provider"):
                    service["remove_session"]("work")
                if condition == "replaced-provider":
                    service["create_session"]("work", "claude")
                before = service["get_session"]("work")
                output = self.make_io()
                spawn = mock.Mock(side_effect=AssertionError("A refused continuation must not launch a provider"))
                result = main(["run", "--cwd", directory, "--prompt", "Fix", *extra, "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn))
                self.assertEqual(result, 1)
                self.assertEqual(json.loads(output["stdout"].getvalue())["error"]["code"], code)
                self.assertEqual(service["get_session"]("work"), before)
                spawn.assert_not_called()

    def test_continue_run_rejects_claude_passthrough_overrides_before_launch(self):
        options = ["--effort low --fallback-model other-model", "--effort=low", "--model other-model",
                   "--model=other-model", "--fallback-model=other-model", "--resume other-conversation",
                   "--resume=other-conversation", "-r other-conversation", "-rother-conversation",
                   "--continue", "-c", "--session-id other-conversation", "--session-id=other-conversation",
                   "--fork-session", "--resume-session-at message-id", "--from-pr 123", '--settings {"model":"other-model"}', "--agent other-agent"]
        for extra_args in options:
            with self.subTest(extra_args=extra_args):
                directory, service, _session, _transcript = self._continuation_parent(
                    provider="claude", model="claude-sonnet-5-5")
                service["set_launch_settings"]("work", {"extra_args": extra_args})
                before = service["get_session"]("work")
                output = self.make_io()
                spawn = mock.Mock(side_effect=AssertionError("A refused continuation must not launch a provider"))
                result = main(["run", "--continue-run", "parent", "--cwd", directory, "--prompt", "Fix", "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn))
                self.assertEqual(result, 1)
                self.assertEqual(json.loads(output["stdout"].getvalue())["error"]["code"],
                                 "continue_run_settings_mismatch")
                spawn.assert_not_called()
                self.assertEqual(service["get_session"]("work"), before)
                self.assertEqual(len(RunRegistry(directory).list()), 1)

    def test_continue_run_uses_current_security_settings_and_pins_only_model_and_effort(self):
        from src.commands.runs import _continue_run_session
        from src.provider_runtime import _build_headless_launch_spec

        for provider in ("codex", "claude"):
            with self.subTest(provider=provider):
                directory, service, _session, _transcript = self._continuation_parent(provider=provider)
                parent = RunRegistry(directory).get("parent")
                parent["launch"].update(permission="full", scrub_env=False)
                service["set_launch_settings"]("work", {
                    "permission": "review", "scrub_env": True, "model": "new-model", "power": "low",
                    "fallback_model": "other-model", "budget": 2, "extra_args": "--verbose",
                })
                current = service["get_session"]("work")
                with mock.patch("src.commands.runs._run_registry") as registry:
                    registry.return_value.get.return_value = parent
                    session = _continue_run_session({"continue_run": "parent"}, {"service": service})
                self.assertEqual(session["launch"]["permission"], "review")
                self.assertTrue(session["launch"]["scrub_env"])
                self.assertEqual(session["launch"]["budget"], 2)
                self.assertEqual(session["launch"]["model"], parent["model"])
                self.assertEqual(session["launch"]["reasoning_effort"], "high")
                self.assertEqual(session["launch"]["power"], "high")
                self.assertNotIn("fallback_model", session["launch"])
                self.assertEqual(session["launch"]["extra_args"], "--verbose")
                spec = _build_headless_launch_spec(session, cwd=directory, initial_prompt="Fix")
                if provider == "codex":
                    self.assertEqual(spec["args"][spec["args"].index("-s") + 1], "read-only")
                    self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", spec["args"])
                else:
                    self.assertIn("--verbose", spec["args"])
                    self.assertEqual(spec["args"][spec["args"].index("--permission-mode") + 1], "plan")
                    self.assertEqual(spec["options"]["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"], "1")
                    self.assertNotIn("--dangerously-skip-permissions", spec["args"])
                self.assertEqual(service["get_session"]("work"), current)

    def test_continue_run_usage_requires_stable_measurement_availability(self):
        from src.commands.runs import _observe_headless_usage
        from src.interactive_usage import MEASURED_KEYS
        from src.run_usage import normalize_usage

        session = {"provider": "codex", "authHome": "/unused", "conversation": {"id": "conversation"}}
        before = normalize_usage(input_tokens=100, cache_creation_tokens=10, cache_creation_1h_tokens=2,
                                 cache_read_tokens=0, output_tokens=20, reasoning_tokens=5)
        after = normalize_usage(input_tokens=200, cache_creation_tokens=20, cache_creation_1h_tokens=4,
                                cache_read_tokens=80, output_tokens=40, reasoning_tokens=10)
        cases = [(None, None), *((key, boundary) for key in MEASURED_KEYS for boundary in ("before", "after"))]
        for key, boundary in cases:
            with self.subTest(key=key, boundary=boundary):
                baseline, cumulative = dict(before), dict(after)
                if boundary == "before":
                    baseline.pop(key)
                elif boundary == "after":
                    cumulative[key] = None
                with mock.patch("src.commands.runs.extract_run_observation", return_value=(after, "model")), \
                        mock.patch("src.commands.runs.extract_interactive_usage",
                                   return_value=(cumulative, "transcript", "conversation_id", "model")):
                    observed = _observe_headless_usage(
                        session, {}, baseline=(baseline, "transcript", "conversation_id", "model"))
                self.assertEqual(observed["usage_cumulative"], cumulative)
                if boundary is None:
                    self.assertEqual(observed["usage_attribution"], "launch_boundary")
                    self.assertEqual(observed["usage"]["cache_read_tokens"], 80)
                    self.assertEqual(observed["usage"]["cache_hit_ratio"], 80 / 190)
                else:
                    self.assertEqual(observed["usage_attribution"], "continuation_usage_unavailable")
                    self.assertTrue(all(value is None for value in observed["usage"].values()))

    def test_continue_run_uses_observed_default_model_and_detaches_with_parent_metadata(self):
        directory, service, _session, _transcript = self._continuation_parent(model=None)
        registry = RunRegistry(directory)
        registry.finish("parent", status="succeeded", final_payload={
            "usage_model": "gpt-6.1-sol", "reasoning_effort": "high"})
        output = self.make_io()
        with mock.patch("src.commands.runs._spawn_detached_run", return_value={"pid": os.getpid(), "background_path": "cdx"}) as child, \
                mock.patch("src.commands.runs.supports_native_background") as native:
            result = main(["run", "--continue-run", "parent", "--cwd", directory,
                           "--prompt", "Fix", "--detach", "--model", "gpt-6.1-sol", "--power", "high", "--json"],
                          self.make_run_ctx(output, service))
        self.assertEqual(result, 0)
        native.assert_not_called()
        parsed = child.call_args.args[0]
        self.assertEqual(parsed["continue_run"], "parent")
        self.assertEqual(parsed["model"], "gpt-6.1-sol")
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["parent_run_id"], "parent")
        stored = registry.get(payload["run_id"])
        self.assertEqual(stored["parent_run_id"], "parent")
        self.assertEqual(stored["conversation_id"], registry.get("parent")["conversation_id"])
        self.assertEqual(stored["reasoning_effort"], "high")

    def test_continue_run_without_usage_boundaries_does_not_count_codex_conversation_totals(self):
        directory, service, _session, _transcript = self._continuation_parent()

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 10000, "cached_input_tokens": 9000, "output_tokens": 5000}}) + "\n")
            return _HeadlessChild(0)

        output = self.make_io()
        self.assertEqual(main(["run", "--continue-run", "parent", "--cwd", directory, "--prompt", "Fix", "--json"],
                              self.make_run_ctx(output, service, spawn_headless=spawn)), 0)
        payload = json.loads(output["stdout"].getvalue())
        self.assertTrue(all(value is None for value in payload["usage"].values()))
        history = service["get_launch_history"]("work")[0]
        self.assertEqual(history["usage_attribution"], "continuation_usage_unavailable")
        self.assertEqual(history["parent_run_id"], "parent")

    def test_continue_run_argument_validation(self):
        base = ["--cwd", ".", "--prompt", "Fix", "--json"]
        self.assertEqual(_parse_run_args([*base, "--continue-run", "parent"])["continue_run"], "parent")
        for args in ([*base, "--continue-run"], [*base, "--continue-run="]):
            with self.subTest(args=args), self.assertRaises(CdxError):
                _parse_run_args(args)

    def test_continue_run_does_not_fall_back_after_capacity_failure(self):
        directory, service, _session, _transcript = self._continuation_parent()
        commands = []

        def spawn(argv, **kwargs):
            commands.append(argv)
            kwargs["stdout"].write(json.dumps({"type": "error", "message": "Selected model is at capacity"}) + "\n")
            return _HeadlessChild(1)

        output = self.make_io()
        with mock.patch("src.commands.runs.time.sleep") as sleep:
            result = main(["run", "--continue-run", "parent", "--cwd", directory, "--prompt", "Fix", "--json"],
                          self.make_run_ctx(output, service, spawn_headless=spawn))
        self.assertEqual(result, 1)
        self.assertEqual(len(commands), 1)
        sleep.assert_not_called()
        payload = json.loads(output["stdout"].getvalue())
        self.assertEqual(payload["parent_run_id"], "parent")
        self.assertEqual(service["get_launch_history"]("work")[0]["parent_run_id"], "parent")

    def test_continue_run_detached_child_preserves_parent_and_settings(self):
        from src.commands.runs import _detached_child_argv

        parsed = _parse_run_args(["--continue-run", "parent", "--cwd", ".", "--prompt", "Fix", "--json"])
        parsed.update(model="gpt-6.1-sol", reasoning_effort="high")
        argv = _detached_child_argv(parsed, "/tmp/prompt", "work", "/tmp")
        self.assertEqual(argv[argv.index("--continue-run") + 1], "parent")
        self.assertEqual(argv[argv.index("--reasoning-effort") + 1], "high")
        self.assertEqual(argv[argv.index("--model") + 1], "gpt-6.1-sol")


    def test_codex_default_model_reaches_history_stats_and_report(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        session = self._authenticated_codex_session(service)
        thread_id = "12345678-1234-1234-1234-123456789abc"
        rollout = pathlib.Path(session["authHome"]) / "sessions" / f"rollout-test-{thread_id}.jsonl"

        def spawn(_argv, **kwargs):
            self.assertNotIn("--model", _argv)
            rollout.parent.mkdir(parents=True, exist_ok=True)
            rollout.write_text(json.dumps({"type": "turn_context", "payload": {"model": "gpt-6.1-sol"}}) + "\n")
            kwargs["stdout"].write(json.dumps({"type": "thread.started", "thread_id": thread_id}) + "\n")
            kwargs["stdout"].write(json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10,
            }}) + "\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["usage_model"], "gpt-6.1-sol")
        self.assertIsNone(payload["model"])
        history = service["get_launch_history"]("work", limit=10)
        self.assertEqual(history[0]["usage_model"], "gpt-6.1-sol")
        self.assertEqual(history[0]["usage"]["input_tokens"], 80)
        io_obj = self.make_io()
        self.assertEqual(main(["stats", "--by", "model", "--json"], self.make_run_ctx(io_obj, service)), 0)
        stats = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(stats["stats"][0]["session_name"], "gpt-6.1-sol")
        self.assertEqual(stats["stats"][0]["priced_runs"], 1)
        self.assertGreater(stats["stats"][0]["cost_usd"], 0)
        io_obj = self.make_io()
        self.assertEqual(main(["run-report", payload["run_id"], "--json"], self.make_run_ctx(io_obj, service)), 0)
        report = json.loads(io_obj["stdout"].getvalue())["report"]
        self.assertEqual(report["run"]["usage_model"], "gpt-6.1-sol")
        self.assertEqual(report["final_payload"]["usage_model"], "gpt-6.1-sol")

    def test_run_accepts_dir_as_the_launch_directory(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("work", "ollama")
        service["set_launch_settings"]("work", {"model": "llama3.2"})
        io_obj = self.make_io()

        self.assertEqual(main([
            "run", "work", "--dir", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=lambda *_args, **_kwargs: _HeadlessChild(0))), 0)

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
            "cached_input_tokens": None,
            "cache_creation_tokens": None,
            "cache_creation_1h_tokens": None,
            "cache_read_tokens": None,
            "output_tokens": 5,
            "reasoning_tokens": 2,
            "total_tokens": 16,
            "cache_hit_ratio": None,
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
            "cached_input_tokens": None,
            "cache_creation_tokens": None,
            "cache_creation_1h_tokens": None,
            "cache_read_tokens": None,
            "output_tokens": 0,
            "reasoning_tokens": None,
            "total_tokens": 3,
            "cache_hit_ratio": None,
        })

    @mock.patch("src.commands.runs.time.sleep")
    def test_run_provider_capacity_failure_remains_queryable_in_registry(self, sleep):
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
        self.assertEqual(run_payload["error"]["code"], "capacity_recovery_exhausted")
        self.assertEqual(run_payload["error"]["provider_code"], 1)
        self.assertEqual(sleep.call_args_list, [mock.call(1), mock.call(2)])
        self.assertEqual([event["action"] for event in run_payload["recovery_events"]], ["retry", "retry", "exhausted"])
        self.assertTrue(os.path.isabs(run_payload["stdout_path"]))

        runs_io = self.make_io()
        self.assertEqual(main(["runs", "--json"], self.make_run_ctx(runs_io, service)), 0)
        runs_payload = json.loads(runs_io["stdout"].getvalue())
        self.assertEqual(runs_payload["runs"][0]["run_id"], run_id)
        self.assertEqual(runs_payload["runs"][0]["status"], "failed")
        self.assertEqual(runs_payload["runs"][0]["cwd"], os.path.abspath(target_dir))
        self.assertEqual(runs_payload["runs"][0]["artifacts"]["stdout_path"], run_payload["stdout_path"])
        self.assertEqual(len(runs_payload["runs"][0]["recovery_events"]), 3)

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
        self.assertEqual(len(report_payload["report"]["final_payload"]["recovery_events"]), 3)

    @mock.patch("src.commands.runs.time.sleep")
    def test_capacity_retries_same_run_before_models_then_ranked_profiles(self, sleep):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        for name, priority, policy in (
            ("work", 0, "use"), ("low", 1, "use"), ("high", 90, "use"),
            ("ask", 100, "ask-first"), ("never", 100, "never"), ("disabled", 100, "use"),
        ):
            self._authenticated_codex_session(service, name)
            service["set_launch_settings"](name, {"model": "primary", "priority": priority, "policy": policy})
        service["set_launch_settings"]("work", {"fallback_model": "backup,primary,backup,last"})
        service["set_session_enabled"]("disabled", False)
        service["create_session"]("other-provider", "ollama")
        seen = []
        run_ids = set()

        def spawn(argv, **kwargs):
            run = RunRegistry(target_dir).list(limit=1)[0]
            run_ids.add(run["run_id"])
            model = argv[argv.index("--model") + 1]
            seen.append((run["session"], model))
            self.assertEqual(argv[-1], "Do it")
            if run["session"] == "low":
                return _HeadlessChild(0)
            kwargs["stdout"].write(json.dumps({"type": "turn.failed", "error": {
                "message": "Selected model is at capacity. Please try a different model.",
            }}) + "\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)
        self.assertEqual(seen, [("work", model) for model in ("primary", "backup", "last") for _ in range(3)]
                         + [("high", "primary")] * 3 + [("low", "primary")])
        self.assertEqual(len(run_ids), 1)
        self.assertEqual(sleep.call_args_list, [mock.call(delay) for _ in range(4) for delay in (1, 2)])
        payload = json.loads(io_obj["stdout"].getvalue())
        events = payload["recovery_events"]
        self.assertEqual([event["action"] for event in events].count("fallback_model"), 2)
        self.assertEqual([event["target_session"] for event in events if event["action"] == "fallback_profile"], ["high", "low"])
        self.assertEqual(payload["model"], "primary")
        self.assertIn("action=fallback_profile", io_obj["stderr"].getvalue())
        self.assertEqual(len(io_obj["stderr"].getvalue().splitlines()), len(events))
        self.assertEqual(len(RunRegistry(target_dir).list()), 1)
        for event in events:
            self.assertIn("Selected model is at capacity", pathlib.Path(event["artifacts"]["stdout_path"]).read_text())
        history = service["get_launch_history"]("work", limit=20)
        self.assertEqual(sorted(row["attempt"] for row in history), list(range(1, 10)))

    @mock.patch("src.commands.runs.time.sleep")
    def test_capacity_recovers_on_retry_without_using_another_model(self, sleep):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)
        service["set_launch_settings"]("work", {"fallback_model": "backup"})
        seen = []

        def spawn(argv, **kwargs):
            seen.append(argv)
            if len(seen) == 1:
                kwargs["stderr"].write("Error: Selected model is at capacity.\n")
                return _HeadlessChild(1)
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--model", "requested", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)
        self.assertEqual(seen[0], seen[1])
        sleep.assert_called_once_with(1)
        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["model"], "requested")

    @mock.patch("src.commands.runs.time.sleep")
    def test_capacity_model_fallback_reports_effective_model_on_explicit_ask_first_profile(self, sleep):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)
        service["set_launch_settings"]("work", {"policy": "ask-first", "fallback_model": "backup"})
        models = []

        def spawn(argv, **kwargs):
            model = argv[argv.index("--model") + 1]
            models.append(model)
            if model == "backup":
                return _HeadlessChild(0)
            kwargs["stdout"].write("Selected model is at capacity.\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--model", "requested", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)
        self.assertEqual(models, ["requested"] * 3 + ["backup"])
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["model"], "backup")
        self.assertEqual(RunRegistry(target_dir).get(payload["run_id"])["model"], "backup")
        self.assertEqual(service["get_session"]("work")["launch"].get("model"), None)

    @mock.patch("src.commands.runs.time.sleep", side_effect=KeyboardInterrupt)
    def test_capacity_backoff_cancellation_finishes_the_run(self, sleep):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        def spawn(argv, **kwargs):
            kwargs["stderr"].write("Selected model is at capacity.\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 130)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "run_cancelled")
        self.assertEqual(RunRegistry(target_dir).get(payload["run_id"])["status"], "cancelled")
        self.assertEqual(len(payload["recovery_events"]), 1)
        self.assertEqual(len(service["get_launch_history"]("work", limit=10)), 1)

    @mock.patch("src.commands.runs.time.sleep")
    def test_capacity_profile_transition_budget_is_bounded(self, sleep):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        for index in range(7):
            self._authenticated_codex_session(service, f"work{index}")
        seen = []

        def spawn(argv, **kwargs):
            seen.append(argv)
            kwargs["stdout"].write("Selected model is at capacity.\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work0", "--cwd", target_dir, "--prompt", "Do it", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)
        self.assertEqual(len(seen), 15)  # Initial profile plus four successors, three attempts each.
        self.assertEqual(sleep.call_count, 10)
        self.assertEqual(json.loads(io_obj["stdout"].getvalue())["error"]["code"], "capacity_recovery_exhausted")

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
                "cdx run: invalid --kind 'audit'; allowed values: assistant|code-review|retro.",
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
            "cached_input_tokens": None,
            "cache_creation_tokens": None,
            "cache_creation_1h_tokens": None,
            "cache_read_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
            "cache_hit_ratio": None,
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

    def test_detached_child_runs_the_cli_module_and_records_a_terminal_result(self):
        """A launched detached run must actually execute, not just report a run id."""
        for budgeted in (False, True):
            with self.subTest(budgeted=budgeted):
                target_dir = self.make_temp_dir()
                service = create_session_service({"base_dir": target_dir})
                self._authenticated_codex_session(service)

                # A synthetic provider on PATH: the child has to reach it, and no real
                # provider CLI or generation may be involved.
                bin_dir = self.make_temp_dir()
                if sys.platform == "win32":
                    stub = os.path.join(bin_dir, "codex.cmd")
                    with open(stub, "w", encoding="utf-8") as handle:
                        handle.write(
                            "@if \"%1\"==\"login\" (echo Logged in as synthetic) "
                            "else (echo {\"model\":\"gpt-6.1-sol\",\"usage\":{\"input_tokens\":1000000}})\r\n@exit /b 0\r\n"
                        )
                else:
                    stub = os.path.join(bin_dir, "codex")
                    with open(stub, "w", encoding="utf-8") as handle:
                        handle.write(
                            "#!/bin/sh\n"
                            "case \"$*\" in\n"
                            "  *'login status'*) echo 'Logged in as synthetic';;\n"
                            "  *) echo '{\"model\":\"gpt-6.1-sol\",\"usage\":{\"input_tokens\":1000000}}';;\n"
                            "esac\n"
                        )
                    os.chmod(stub, 0o755)

                io_obj = self.make_io()
                child_env = {
                    **os.environ,
                    "PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                    "CDX_HOME": target_dir,
                }
                with mock.patch.dict(os.environ, child_env, clear=True):
                    self.assertEqual(main([
                        "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--detach", *(["--budget", "0.01"] if budgeted else []), "--json"
                    ], self.make_run_ctx(io_obj, service)), 0)

                payload = json.loads(io_obj["stdout"].getvalue())
                run_id = payload["run_id"]
                registry = RunRegistry(target_dir)
                deadline = time.time() + 60
                run = None
                while time.time() < deadline:
                    run = registry.get(run_id)
                    if run and run.get("status") != "running":
                        break
                    time.sleep(0.2)

                launch_log = "".join(
                    path.read_text(encoding="utf-8", errors="replace")
                    for path in pathlib.Path(target_dir).rglob("*.launch.log")
                )
                self.assertIsNotNone(run, f"detached run never registered; launch log: {launch_log}")
                self.assertEqual(run.get("status"), "failed" if budgeted else "succeeded", f"launch log: {launch_log}")
                self.assertEqual(run.get("exit_code", run.get("run_info", {}).get("returncode")), 125 if budgeted else 0,
                                 f"launch log: {launch_log}")
                if budgeted:
                    self.assertEqual(run["error"]["code"], "budget_exceeded")
                    self.assertGreater(run["error"]["spent_usd"], 0.01)
                # The child owns cleanup of its staged prompt, which it only reaches
                # once the module it was told to run actually starts.
                self.assertNotIn("prompt.txt", launch_log)

    def test_detached_child_command_names_the_top_level_cli_module(self):
        from src.commands import runs as runs_module

        command, root = runs_module._cdx_self_command()
        self.assertEqual(command[1:], ["-m", "src.cli"])
        # The import root is the parent of every package component, so the
        # module it names is importable from there.
        self.assertTrue(os.path.isfile(os.path.join(root, "src", "cli.py")))

        # The installed Python-package layout resolves the same way.
        with mock.patch.dict(runs_module.__dict__, {"__package__": "cdx_manager.commands"}), \
             mock.patch.object(runs_module.importlib.util, "find_spec", return_value=object()):
            installed_command, installed_root = runs_module._cdx_self_command()
        self.assertEqual(installed_command[1:], ["-m", "cdx_manager.cli"])
        self.assertEqual(installed_root, root)

        # A module name that does not resolve must fail at launch, not silently
        # report a run that never executes.
        with mock.patch.object(runs_module.importlib.util, "find_spec", return_value=None):
            with self.assertRaisesRegex(CdxError, "CLI module src.cli was not found"):
                runs_module._cdx_self_command()

    def test_interrupting_a_headless_run_kills_the_provider_and_records_cancellation(self):
        """Ctrl-C must not leave the provider running outside its supervisor."""
        if sys.platform == "win32":
            self.skipTest("POSIX signal semantics; Windows interrupt handling is separate")
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)

        pid_holder = {}

        def spec(_session, **_kwargs):
            # Only the launch specification is synthetic; the spawn, the wait,
            # and the cleanup below are the real ones.
            return {
                "command": sys.executable,
                "args": ["-c", "import time; time.sleep(120)"],
                "options": {},
                "label": "synthetic provider",
            }

        class _RealChildInterruptedOnce:
            def __init__(self, argv, **kwargs):
                self._proc = subprocess.Popen(argv, start_new_session=True, **kwargs)
                self.pid = self._proc.pid
                pid_holder["pid"] = self._proc.pid
                self._interrupted = False

            @property
            def returncode(self):
                return self._proc.returncode

            def wait(self, timeout=None):
                if not self._interrupted:
                    # What the terminal actually does to a blocked supervisor.
                    self._interrupted = True
                    raise KeyboardInterrupt
                return self._proc.wait(timeout=timeout)

            def terminate(self):
                self._proc.terminate()

            def kill(self):
                self._proc.kill()

        io_obj = self.make_io()
        with mock.patch("src.provider_runtime._build_headless_launch_spec", side_effect=spec):
            exit_code = main([
                "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"
            ], self.make_run_ctx(io_obj, service, spawn_headless=_RealChildInterruptedOnce))

        self.assertEqual(exit_code, 130)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "run_cancelled")

        # Terminated and reaped: no orphan is left consuming quota.
        with self.assertRaises(ProcessLookupError):
            os.kill(pid_holder["pid"], signal.SIGTERM)

        run = RunRegistry(target_dir).get(payload["run_id"])
        self.assertEqual(run.get("status"), "cancelled")

    def test_sigterm_to_a_headless_run_kills_the_provider_too(self):
        """kill, systemctl stop or a closed SSH session must not orphan the provider."""
        if sys.platform == "win32":
            self.skipTest("POSIX signal semantics")
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service)
        pid_holder = {}

        def spec(_session, **_kwargs):
            return {"command": sys.executable, "args": ["-c", "import time; time.sleep(120)"],
                    "options": {}, "label": "synthetic provider"}

        class _RealChildTerminatedOnce:
            def __init__(self, argv, **kwargs):
                self._proc = subprocess.Popen(argv, start_new_session=True, **kwargs)
                self.pid = pid_holder["pid"] = self._proc.pid
                self._signalled = False

            @property
            def returncode(self):
                return self._proc.returncode

            def wait(self, timeout=None):
                if not self._signalled:
                    self._signalled = True
                    os.kill(os.getpid(), signal.SIGTERM)  # what `kill <supervisor>` does
                return self._proc.wait(timeout=timeout)

            def terminate(self):
                self._proc.terminate()

            def kill(self):
                self._proc.kill()

        previous = signal.getsignal(signal.SIGTERM)
        io_obj = self.make_io()
        with mock.patch("src.provider_runtime._build_headless_launch_spec", side_effect=spec):
            exit_code = main(["run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json"],
                             self.make_run_ctx(io_obj, service, spawn_headless=_RealChildTerminatedOnce))
        self.assertEqual(exit_code, 130)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid_holder["pid"], signal.SIGTERM)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

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

    def test_run_reports_permission_denials_without_failing(self):
        denials = [{"tool_name": "Bash", "tool_use_id": "tool-1", "tool_input": {"command": "pwd"}}]
        for reported in (denials, [], None):
            with self.subTest(permission_denials=reported):
                target_dir = self.make_temp_dir()
                service = create_session_service({"base_dir": target_dir})
                session = service["create_session"]("work", "claude")
                auth = _AuthHarness(initial_auth={session["authHome"]: True})
                result = {"type": "result", "subtype": "success", "result": "Done using another tool."}
                if reported is not None:
                    result["permission_denials"] = reported

                def spawn(_argv, result=result, **kwargs):
                    # Only structured result records count, not prose or other events.
                    kwargs["stdout"].write('Permission denied\n[]\n{"type":"assistant","permission_denials":[{}]}\n')
                    kwargs["stdout"].write(json.dumps(result) + "\n")
                    return _HeadlessChild(0)

                io_obj = self.make_io()
                self.assertEqual(main([
                    "run", "work", "--cwd", target_dir, "--prompt", "Do it", "--json",
                ], self.make_run_ctx(io_obj, service, spawn_headless=spawn, spawn_sync=auth.spawn_sync)), 0)

                payload = json.loads(io_obj["stdout"].getvalue())
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["exit_code"], 0)
                self.assertIsNone(payload["error"])
                if reported:
                    self.assertEqual([w["code"] for w in payload["warnings"]], ["permission_denials"])
                    self.assertEqual(payload["warnings"][0]["permission_denials"], denials)
                    self.assertEqual(payload["warnings"][0]["provider"], "claude")
                else:
                    self.assertEqual(payload["warnings"], [])
                stored = RunRegistry(target_dir).get(payload["run_id"])
                self.assertEqual(stored["status"], "succeeded")
                self.assertEqual(stored["final_payload"]["warnings"], payload["warnings"])

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
                    {"type": "error", "message": "Your workspace is out of credits. Add credits to continue."}
                ) + "\n")
                kwargs["stdout"].write(json.dumps({"type": "usage", "model": "gpt-6-sol", "usage": {
                    "input_tokens": 100, "output_tokens": 10,
                }}) + "\n")
                return _HeadlessChild(1)
            kwargs["stdout"].write(json.dumps({"type": "usage", "model": "gpt-6-luna", "usage": {
                "input_tokens": 200, "output_tokens": 20,
            }}) + "\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work1", "--cwd", target_dir, "--project", target_dir, "--prompt", "Do it", "--failover", "--json"
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
        first = service["get_launch_history"]("work1", limit=10)
        second = service["get_launch_history"]("work2", limit=10)
        self.assertEqual([(row["attempt"], row["usage"]["input_tokens"], row["usage"]["output_tokens"])
                          for row in first], [(1, 100, 10)])
        self.assertEqual([(row["attempt"], row["usage"]["input_tokens"], row["usage"]["output_tokens"])
                          for row in second], [(2, 200, 20)])
        self.assertEqual(first[0]["run_id"], second[0]["run_id"])
        for record in [*first, *second, payload, runs[0]]:
            self.assertEqual(record["project"], target_dir)
            self.assertEqual(record["project_source"], "operator")
            self.assertEqual(record["cwd"], target_dir)
        self.assertEqual(first[0]["usage_model"], "gpt-6-sol")
        self.assertEqual(second[0]["usage_model"], "gpt-6-luna")
        self.assertEqual(payload["usage_model"], "gpt-6-luna")
        self.assertEqual(runs[0]["usage_model"], "gpt-6-luna")
        from src.commands.status import _stats_totals, _summarize_stats
        totals = _stats_totals(_summarize_stats([*first, *second]))
        self.assertEqual((totals["input_tokens"], totals["output_tokens"]), (300, 30))
        self.assertEqual((totals["launches"], totals["priced_runs"]), (2, 2))

    def test_failover_reports_exhausting_every_account_distinctly(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service, "only")
        service["record_status"]("only", {"remaining_5h_pct": 0, "remaining_week_pct": 0})

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write(json.dumps(
                {"type": "error", "message": "Your workspace is out of credits. Add credits to continue."}
            ) + "\n")
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
            kwargs["stdout"].write(json.dumps(
                {"type": "error", "message": "Your workspace is out of credits. Add credits to continue."}
            ) + "\n")
            return _HeadlessChild(1)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "work1", "--cwd", target_dir, "--prompt", "Do it", "--json"
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 1)

        self.assertEqual(len(attempts), 1)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["error"]["code"], "provider_failed")

    def test_detached_failover_is_applied_by_the_detached_child(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        for name in ("work1", "work2"):
            self._authenticated_codex_session(service, name)
        service["record_status"]("work1", {"remaining_5h_pct": 0, "remaining_week_pct": 0})

        spawned = {}

        def spawn_detached(argv, **_kwargs):
            spawned["argv"] = argv
            child = _HeadlessChild(0)
            child.pid = os.getppid()
            return child

        io_obj = self.make_io()
        # Even where the provider could run its own background agent, failover
        # keeps the cdx child: nothing would be watching the provider's.
        with mock.patch("src.commands.runs.supports_native_background", return_value=True):
            self.assertEqual(main([
                "run", "work1", "--cwd", target_dir, "--prompt", "Do it", "--detach", "--failover", "--json"
            ], self.make_run_ctx(io_obj, service, spawn_detached=spawn_detached)), 0)
        run_id = json.loads(io_obj["stdout"].getvalue())["run_id"]
        child_argv = spawned["argv"][spawned["argv"].index("run"):]
        self.assertIn("--failover", child_argv)
        self.assertNotIn("--detach", child_argv)

        # Now be that child: the same blocking path, handed the parent's run id.
        def spawn(_argv, **kwargs):
            running = RunRegistry(target_dir).get(run_id)
            if running["session"] == "work1":
                kwargs["stdout"].write(json.dumps(
                    {"type": "error", "message": "Your workspace is out of credits."}
                ) + "\n")
                return _HeadlessChild(1)
            return _HeadlessChild(0)

        child_io = self.make_io()
        with mock.patch.dict(os.environ, {"CDX_RUN_ID": run_id}):
            self.assertEqual(main(child_argv, self.make_run_ctx(child_io, service, spawn_headless=spawn)), 0)

        run = RunRegistry(target_dir).get(run_id)
        self.assertEqual((run["status"], run["session"]), ("succeeded", "work2"))
        self.assertEqual([item["session"] for item in run["occupancies"]], ["work1", "work2"])


class RunRegistryPruneTests(unittest.TestCase):
    def test_start_keeps_running_runs_and_the_newest_finished_ones(self):
        from src import run_registry
        data = {"runs": [{"run_id": "live", "status": "running"}]
                + [{"run_id": f"done{i}", "status": "succeeded"} for i in range(run_registry.MAX_FINISHED_RUNS + 5)]}
        run_registry._prune_finished_runs(data)
        ids = [run["run_id"] for run in data["runs"]]
        self.assertEqual(ids[0], "live")
        self.assertEqual(len(ids), run_registry.MAX_FINISHED_RUNS + 1)
        self.assertEqual(ids[-1], f"done{run_registry.MAX_FINISHED_RUNS - 1}")


class RunCapOrderingTests(CliTestBase):
    def _service(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "ollama")
        service["set_launch_settings"]("work", {"model": "llama3.2"})
        calls = []
        begin = service["begin_conversation"]
        service["begin_conversation"] = lambda name: calls.append(name) or begin(name)
        return service, calls

    def _run(self, service, *extra, env=None):
        io_obj = self.make_io()
        code = main(["run", "work", "--cwd", service["base_dir"], "--prompt", "go", *extra, "--json"],
                    self.make_run_ctx(io_obj, service, env=env or {},
                                      spawn_headless=lambda *_a, **_k: _HeadlessChild(0)))
        return code, json.loads(io_obj["stdout"].getvalue())

    def test_a_run_refused_by_the_cap_leaves_the_conversation_alone(self):
        service, calls = self._service()
        RunRegistry(service["base_dir"]).start("busy", kind="assistant", session="work",
                                               provider="ollama", model=None, cwd=".")
        code, payload = self._run(service, "--max-parallel", "1")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["code"], "too_many_runs")
        self.assertEqual(calls, [])

    def test_a_finished_native_background_run_frees_its_slot(self):
        service, _calls = self._service()
        registry = RunRegistry(service["base_dir"])
        registry.start("bg", kind="assistant", session="work", provider="claude", model=None, cwd=".")
        registry.record_background("bg", path="provider_native", provider_session_id="s", provider_agent_id="a")
        outcome = {"usage": None, "usage_model": None, "result": "done"}
        with mock.patch("src.commands.runs.find_session_transcript", return_value=None), \
                mock.patch("src.commands.runs.read_transcript_outcome", return_value=outcome), \
                mock.patch("src.commands.runs.turn_is_complete", return_value=True), \
                mock.patch("src.commands.runs.stop_background_agent"):
            code, payload = self._run(service, "--max-parallel", "1")
        self.assertEqual(code, 0, payload)
        self.assertEqual(registry.get("bg")["status"], "succeeded")

    def test_cdx_max_runs_zero_or_negative_means_no_limit(self):
        from src.commands.runs import _env_max_runs
        self.assertIsNone(_env_max_runs({"env": {"CDX_MAX_RUNS": "0"}}))
        self.assertIsNone(_env_max_runs({"env": {"CDX_MAX_RUNS": "-3"}}))
        self.assertEqual(_env_max_runs({"env": {"CDX_MAX_RUNS": "2"}}), 2)
