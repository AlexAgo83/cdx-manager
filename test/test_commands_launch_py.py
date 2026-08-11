"""Tests for launch, resume, can-resume, handoff.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
import subprocess
import uuid

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
    main,
)
from src.errors import CdxError
from src.session_service import create_session_service


class LaunchCommandTests(CliTestBase):

    def test_launch_directory_is_explicit_recorded_and_exposed_while_running(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(), "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn, "spawn_sync": harness.spawn_sync,
        }), 0)

        self.assertEqual(main(["main", "--dir", workspace], {
            **self.make_io(), "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn, "spawn_sync": harness.spawn_sync,
        }), 0)

        launch_call = [call for call in harness.calls if call["kind"] == "spawn" and call["command"] == "script"][-1]
        launch_args = _script_launch_args(launch_call)
        self.assertEqual(launch_args[launch_args.index("--cd") + 1], os.path.realpath(workspace))
        history = create_session_service({"base_dir": temp_dir})["get_launch_history"]("main", limit=1)
        self.assertEqual(history[0]["cwd"], os.path.realpath(workspace))

    def test_launch_rejects_missing_explicit_directory_before_provider_starts(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(), "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn, "spawn_sync": harness.spawn_sync,
        }), 0)

        missing = os.path.join(temp_dir, "missing")
        with self.assertRaisesRegex(CdxError, "Invalid directory"):
            main(["main", "--dir", missing], {
                **self.make_io(), "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn, "spawn_sync": harness.spawn_sync,
            })
        self.assertEqual(harness.calls, [])

    def test_handoff_installs_context_for_target_session_json(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["context", "set", "Next Steps: continue here"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)

        handoff_io = self.make_io()
        self.assertEqual(main(["handoff", "main", "--json"], {
            **handoff_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        payload = json.loads(handoff_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "handoff")
        target_path = payload["context"]["target_path"]
        self.assertTrue(target_path.endswith("shared-context.md"))
        with open(target_path, encoding="utf-8") as handle:
            self.assertIn("Next Steps: continue here", handle.read())

    def test_handoff_from_source_session_builds_context_for_target_json(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        for name in ("account1", "account2"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "cwd": workspace,
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        source_log = os.path.join(
            temp_dir,
            "profiles",
            "account1",
            "log",
            "cdx-session-20260522T100000.000000Z-123.log",
        )
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Goal: finish the quota handoff\nNext Steps: run tests\n")

        handoff_io = self.make_io()
        self.assertEqual(main(["handoff", "account1", "account2", "--json"], {
            **handoff_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)

        payload = json.loads(handoff_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "handoff")
        self.assertEqual(payload["source_session"]["name"], "account1")
        self.assertEqual(payload["target_session"]["name"], "account2")
        self.assertEqual(payload["source_transcript"], source_log)
        self.assertIn("Read $CODEX_HOME/shared-context.md first", payload["launch_prompt"])
        with open(payload["context"]["target_path"], encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Resume the work from `account1` in `account2`", content)
        self.assertIn("Goal: finish the quota handoff", content)
        self.assertIn("Next Steps: run tests", content)

    def test_handoff_launches_target_with_initial_prompt(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        for name in ("account1", "account2"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "cwd": workspace,
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        source_log = os.path.join(temp_dir, "profiles", "account1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Continue the implementation\n")

        self.assertEqual(main(["handoff", "account1", "account2"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        launch_call = harness.calls[-1]
        self.assertEqual(launch_call["kind"], "spawn")
        self.assertEqual(launch_call["command"], "script")
        self.assertTrue(_script_launch_invokes(launch_call, "codex"))
        self.assertIn("Read $CODEX_HOME/shared-context.md first", _script_launch_text(launch_call))

    def test_handoff_from_claude_source_builds_context_for_claude_target_json(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        for name in ("claude1", "claude2"):
            self.assertEqual(main(["add", "claude", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "cwd": workspace,
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        source_log = os.path.join(
            temp_dir,
            "profiles",
            "claude1",
            "claude-home",
            "log",
            "cdx-session-20260522T100000.000000Z-123.log",
        )
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Claude progress\nNext Steps: continue with Claude\n")

        handoff_io = self.make_io()
        self.assertEqual(main(["handoff", "claude1", "claude2", "--json"], {
            **handoff_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)

        payload = json.loads(handoff_io["stdout"].getvalue())
        target_path = payload["context"]["target_path"]
        self.assertEqual(payload["source_session"]["provider"], "claude")
        self.assertEqual(payload["target_session"]["provider"], "claude")
        self.assertIn(f"Read {target_path} first", payload["launch_prompt"])
        self.assertTrue(target_path.endswith(os.path.join("claude-home", "shared-context.md")))
        with open(target_path, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Claude progress", content)
        self.assertIn("Next Steps: continue with Claude", content)

    def test_handoff_from_claude_source_uses_native_project_jsonl_without_launch_log(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        for name in ("corvus", "digital"):
            self.assertEqual(main(["add", "claude", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "cwd": workspace,
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        native_log = os.path.join(
            temp_dir,
            "profiles",
            "corvus",
            "claude-home",
            ".claude",
            "projects",
            "-tmp-repo",
            "session.jsonl",
        )
        os.makedirs(os.path.dirname(native_log), exist_ok=True)
        with open(native_log, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Goal: finish the Claude handoff"}],
                },
            }))
            handle.write("\n")
            handle.write(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Next Steps: run the migration tests"}],
                },
            }))
            handle.write("\n")

        handoff_io = self.make_io()
        self.assertEqual(main(["handoff", "corvus", "digital", "--json"], {
            **handoff_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)

        payload = json.loads(handoff_io["stdout"].getvalue())
        self.assertEqual(payload["source_transcript"], native_log)
        with open(payload["context"]["target_path"], encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("[user]\nGoal: finish the Claude handoff", content)
        self.assertIn("[assistant]\nNext Steps: run the migration tests", content)

    def test_handoff_allows_codex_to_claude_target_json(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        self.assertEqual(main(["add", "codex1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["add", "claude", "claude1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        source_log = os.path.join(temp_dir, "profiles", "codex1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Codex context for Claude\n")

        handoff_io = self.make_io()
        self.assertEqual(main(["handoff", "codex1", "claude1", "--json"], {
            **handoff_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)

        payload = json.loads(handoff_io["stdout"].getvalue())
        self.assertEqual(payload["source_session"]["provider"], "codex")
        self.assertEqual(payload["target_session"]["provider"], "claude")
        self.assertIn(f"Read {payload['context']['target_path']} first", payload["launch_prompt"])
        with open(payload["context"]["target_path"], encoding="utf-8") as handle:
            self.assertIn("Codex context for Claude", handle.read())

    def test_resume_flag_launches_codex_resume(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        resume_io = self.make_io()
        self.assertEqual(main(["main", "-r"], {
            **resume_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
            "cwd": "/tmp/repo",
        }), 0)

        self.assertIn("Resuming codex session main", resume_io["stdout"].getvalue())
        resume_call = harness.calls[-1]
        self.assertEqual(resume_call["command"], "script")
        self.assertTrue(_script_launch_invokes(resume_call, "codex"))
        self.assertEqual(_script_launch_args(resume_call)[:4], ["resume", "--last", "--cd", "/tmp/repo"])

    def test_resume_command_launches_claude_continue_json(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "claude", "work"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        resume_io = self.make_io()
        self.assertEqual(main(["resume", "work", "--json"], {
            **resume_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
            "cwd": "/tmp/repo",
        }), 0)

        payload = json.loads(resume_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "resume")
        # The session was launched above, so it carries a conversation id and
        # resume names it rather than falling back to --continue.
        self.assertEqual(payload["resume"]["strategy"], "provider_conversation_id")
        self.assertEqual(payload["resume"]["provenance"], "imposed")
        resume_call = harness.calls[-1]
        self.assertEqual(resume_call["command"], "script")
        self.assertTrue(_script_launch_invokes(resume_call, "claude"))
        resume_args = _script_launch_args(resume_call)
        self.assertEqual(resume_args[0], "--resume")
        self.assertEqual(resume_args[1], payload["resume"]["identity"])
        self.assertEqual(resume_args[2:4], ["--name", "work"])

    def test_can_resume_reports_json_without_launching_provider(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main", "codex")

        io_obj = self.make_io()
        self.assertEqual(main(["can-resume", "main", "--json"], {
            **io_obj,
            "service": service,
            "spawn": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
            "cwd": "/tmp/repo",
        }), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["resumable"])
        self.assertEqual(payload["provider"], "codex")
        self.assertEqual(payload["strategy"], "provider_last")
        self.assertEqual(payload["command_preview"], ["codex", "resume", "--last", "--cd", "/tmp/repo"])

    def test_resume_rejects_unsupported_provider_without_normal_launch(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("local", "ollama")

        with self.assertRaisesRegex(CdxError, "does not support native resume"):
            main(["local", "--resume"], {
                **self.make_io(),
                "service": service,
                "spawn": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
            })

    def test_persisted_codex_launch_settings_are_applied_until_unset(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "main", "--power", "medium", "--permission", "full", "--fast", "off", "--model", "gpt-test", "--json"
        ], {
            **set_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(set_io["stdout"].getvalue())
        self.assertEqual(payload["launch"], {
            "power": "medium",
            "permission": "full",
            "fast": False,
            "model": "gpt-test",
        })

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        launch_text = _script_launch_text(launch_call)
        self.assertIn("--model", launch_text)
        self.assertIn("gpt-test", launch_text)
        self.assertIn("-c", launch_text)
        self.assertIn('model_reasoning_effort="medium"', launch_text)
        self.assertIn("danger-full-access", launch_text)
        self.assertIn("never", launch_text)

        unset_io = self.make_io()
        self.assertEqual(main(["unset", "main", "--all", "--json"], {
            **unset_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertEqual(json.loads(unset_io["stdout"].getvalue())["launch"], {})

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertEqual(_script_launch_args(launch_call)[:3], ["--no-alt-screen", "--cd", os.getcwd()])
        self.assertNotIn('model_reasoning_effort="medium"', _script_launch_text(launch_call))

    def test_launch_setting_aliases_update_single_and_bulk_targets(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"], ["add", "ollama", "local", "--model", "llama3.2"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        power_io = self.make_io()
        self.assertEqual(main(["power", "all", "low", "--json"], {
            **power_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        power_payload = json.loads(power_io["stdout"].getvalue())
        self.assertEqual(power_payload["action"], "power")
        self.assertEqual(power_payload["updated_count"], 3)
        self.assertTrue(all(session["launch"]["power"] == "low" for session in power_payload["sessions"]))

        perm_io = self.make_io()
        self.assertEqual(main(["perm", "provider:claude", "review", "--json"], {
            **perm_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        perm_payload = json.loads(perm_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in perm_payload["sessions"]], ["work1"])
        self.assertEqual(perm_payload["sessions"][0]["launch"]["permission"], "review")

        fast_io = self.make_io()
        self.assertEqual(main(["fast", "main,local", "on", "--json"], {
            **fast_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        fast_payload = json.loads(fast_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in fast_payload["sessions"]], ["main", "local"])
        self.assertTrue(all(session["launch"]["fast"] for session in fast_payload["sessions"]))

        model_io = self.make_io()
        self.assertEqual(main(["model", "provider:ollama", "llama3.2", "--json"], {
            **model_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        model_payload = json.loads(model_io["stdout"].getvalue())
        self.assertEqual(model_payload["sessions"][0]["launch"]["model"], "llama3.2")

    def test_launch_setting_alias_default_clears_field(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["power", "main", "medium"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        clear_io = self.make_io()
        self.assertEqual(main(["power", "main", "default", "--json"], {
            **clear_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(clear_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "power")
        self.assertEqual(payload["launch"], {"fast": False})

    def test_session_list_hides_fast_off_launch_label(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_launch_settings"]("main", {"fast": False})

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("medium", output)
        self.assertNotIn("fast-off", output)

    def test_launch_history_records_success_and_failure(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        def failing_spawn(argv, **kwargs):
            harness.calls.append({
                "kind": "spawn",
                "command": argv[0],
                "args": list(argv[1:]),
                "options": kwargs,
            })
            child = _Child()
            child.returncode = 7
            return child

        with self.assertRaisesRegex(CdxError, "exited with code 7"):
            main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": failing_spawn,
                "spawn_sync": harness.spawn_sync,
            })

        history_io = self.make_io()
        self.assertEqual(main(["history", "main", "--json"], {
            **history_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(history_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "history")
        self.assertEqual([entry["status"] for entry in payload["history"][:2]], ["failed", "success"])
        self.assertEqual(payload["history"][0]["exit_code"], 1)
        self.assertEqual(payload["history"][0]["returncode"], 7)
        self.assertEqual(payload["history"][0]["session_name"], "main")
        self.assertEqual(payload["history"][0]["provider"], "codex")
        self.assertIn("transcript_path", payload["history"][0])

        text_io = self.make_io()
        self.assertEqual(main(["history", "--limit", "1"], {
            **text_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = text_io["stdout"].getvalue()
        self.assertIn("SESSION", output)
        self.assertIn("failed", output)

        service = create_session_service({"base_dir": temp_dir})
        service["start_session_runtime"]("main", {"pid": os.getpid()})
        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["history", "--limit", "1"], {
            **color_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        color_output = color_io["stdout"].getvalue()
        self.assertIn("\033[", color_output)
        self.assertIn("main*", color_output)

        summary_io = self.make_io()
        self.assertEqual(main(["history", "--summary", "--json"], {
            **summary_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        summary_payload = json.loads(summary_io["stdout"].getvalue())
        self.assertEqual(summary_payload["summary"][0]["session_name"], "main")
        self.assertEqual(summary_payload["summary"][0]["launches"], 2)
        self.assertEqual(summary_payload["summary"][0]["successes"], 1)
        self.assertEqual(summary_payload["summary"][0]["failures"], 1)
        self.assertGreaterEqual(summary_payload["summary"][0]["duration_ms"], 0)
        self.assertEqual(summary_payload["summary"][0]["session_name"], "main")

        summary_text_io = self.make_io()
        self.assertEqual(main(["history", "--summary"], {
            **summary_text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        summary_output = summary_text_io["stdout"].getvalue()
        self.assertIn("Assistant time:", summary_output)
        self.assertIn("LAUNCHES", summary_output)
        self.assertIn("main*", summary_output)

        summary_color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["history", "--summary"], {
            **summary_color_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        self.assertIn("\033[", summary_color_io["stdout"].getvalue())

    def test_launch_rejects_session_marked_logged_out(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "logged_out",
        })

        def should_not_spawn(*_args, **_kwargs):
            raise AssertionError("logged-out sessions should not launch")

        with self.assertRaisesRegex(CdxError, "Run: cdx login claude"):
            main(["claude"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
                "spawn": should_not_spawn,
                "spawn_sync": should_not_spawn,
            })

    def test_launch_surfaces_update_notice(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        launch_io = self.make_io()
        self.assertEqual(main(["main"], {
            **launch_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)
        output = launch_io["stdout"].getvalue()
        self.assertIn("Update available: cdx-manager 9.9.9", output)
        self.assertIn("Run: cdx update", output)
        self.assertNotIn("https://example.invalid/release", output)

    def test_codex_launch_uses_quoted_custom_script_args(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        env = {
            "CDX_HOME": temp_dir,
            "CDX_SCRIPT_ARGS": '-q -c "wrapped command" {transcript}',
        }
        main(["add", "main"], {
            **self.make_io(),
            "env": env,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": env,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        launch_call = next(call for call in harness.calls if call["kind"] == "spawn" and call["command"] == "script")
        self.assertEqual(launch_call["args"][:3], ["-q", "-c", "wrapped command"])
        self.assertTrue(launch_call["args"][3].endswith(".log"))
        self.assertEqual(launch_call["args"][4], "codex")

    def test_persisted_claude_launch_settings_are_applied(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "claude", "work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        self.assertEqual(main(["set", "work1", "--power", "high", "--permission", "review", "--fast", "on", "--model", "sonnet"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        config_io = self.make_io()
        self.assertEqual(main(["config", "work1"], {
            **config_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Launch settings:", config_io["stdout"].getvalue())
        self.assertIn("SETTING", config_io["stdout"].getvalue())
        self.assertIn("VALUE", config_io["stdout"].getvalue())
        self.assertIn("Power", config_io["stdout"].getvalue())
        self.assertIn("high", config_io["stdout"].getvalue())
        self.assertIn("Permission", config_io["stdout"].getvalue())
        self.assertIn("review", config_io["stdout"].getvalue())
        self.assertIn("Fast", config_io["stdout"].getvalue())
        self.assertIn("on", config_io["stdout"].getvalue())
        self.assertIn("Model", config_io["stdout"].getvalue())
        self.assertIn("sonnet", config_io["stdout"].getvalue())
        self.assertIn(
            "Set a value: cdx set work1 --power medium --permission auto --fast on --rtk on --logics on --notify on --notify-preview on --model MODEL --priority 80",
            config_io["stdout"].getvalue(),
        )

        self.assertEqual(main(["work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        ][-1]
        launch_args = _script_launch_args(launch_call)
        self.assertEqual(launch_args[:2], ["--name", "work1"])
        for flag, value in [
            ("--model", "sonnet"),
            ("--effort", "high"),
            ("--permission-mode", "plan"),
        ]:
            self.assertEqual(launch_args[launch_args.index(flag) + 1], value)
        # The launch mints the conversation id it will carry, so resume can name
        # it later instead of asking for "the most recent conversation here".
        conversation_id = launch_args[launch_args.index("--session-id") + 1]
        self.assertEqual(str(uuid.UUID(conversation_id)), conversation_id)

    def test_persisted_claude_api_model_is_normalized_for_cli_launch(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "claude", "work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["set", "work1", "--model", "claude-sonnet-4-5-20250929"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        config_io = self.make_io()
        self.assertEqual(main(["config", "work1"], {
            **config_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("claude-sonnet-4-5-20250929", config_io["stdout"].getvalue())

        self.assertEqual(main(["work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        ][-1]
        model_index = _script_launch_args(launch_call).index("--model") + 1
        self.assertEqual(_script_launch_args(launch_call)[model_index], "claude-sonnet-4-5")

    def test_handoff_launches_claude_target_with_initial_prompt(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)
        harness = _AuthHarness()

        for name in ("claude1", "claude2"):
            self.assertEqual(main(["add", "claude", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "cwd": workspace,
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        source_log = os.path.join(temp_dir, "profiles", "claude1", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Continue from Claude transcript\n")

        self.assertEqual(main(["handoff", "claude1", "claude2"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        launch_call = harness.calls[-1]
        self.assertEqual(launch_call["kind"], "spawn")
        self.assertEqual(launch_call["command"], "script")
        self.assertTrue(_script_launch_invokes(launch_call, "claude"))
        self.assertEqual(_script_launch_args(launch_call)[:2], ["--name", "claude2"])
        self.assertIn("claude-home", _script_launch_text(launch_call))
        self.assertIn("shared-context.md first", _script_launch_text(launch_call))

    def test_signal_emitter_interrupts_launch(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        create_io = self.make_io()
        main([
            "add", "main"
        ], {
            **create_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        emitter = _SignalEmitter()
        seen = []

        def spawn(argv, **kwargs):
            self.assertEqual(argv[0], "script")

            def on_wait(child):
                emitter.emit("SIGINT")
                seen.extend(child.signals)

            return _Child(on_wait=on_wait)

        with self.assertRaises(CdxError) as ctx:
            main([
                "main"
            ], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": spawn,
                "spawn_sync": harness.spawn_sync,
                "signalEmitter": emitter,
            })
        self.assertEqual(ctx.exception.exit_code, 130)
        self.assertIn("SIGINT", str(ctx.exception))
        self.assertEqual(seen, [2])

    def test_codex_launch_falls_back_when_script_is_missing(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })
        calls = []

        def spawn(argv, **kwargs):
            calls.append(argv[0])
            if argv[0] == "script":
                raise FileNotFoundError("script")
            return _Child()

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(calls, ["script", "codex"])

    def test_codex_launch_falls_back_when_script_wrapper_fails_before_logging(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })
        calls = []

        def spawn(argv, **kwargs):
            calls.append(argv[0])
            if argv[0] == "script":
                return _Child(on_wait=lambda child: setattr(child, "returncode", 1))
            return _Child()

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(calls, ["script", "codex"])

    def test_launch_auth_probe_timeout_reports_degraded_status(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        def timeout_probe(_command, _args, _spec):
            raise subprocess.TimeoutExpired("codex", 15)

        with self.assertRaises(CdxError) as ctx:
            main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
                "spawn_sync": timeout_probe,
                "spawn": lambda argv, **kwargs: _Child(),
            })

        message = str(ctx.exception)
        self.assertIn("Auth probe timed out", message)
        self.assertIn("degraded", message)
        self.assertNotIn("not authenticated", message)

    def test_launch_requires_live_auth_probe_even_when_local_token_exists(self):
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
            raise AssertionError("unauthenticated interactive launches must not start provider")

        with self.assertRaisesRegex(CdxError, "not authenticated"):
            main(["work"], {
                **self.make_io(),
                "service": service,
                "spawn": spawn,
                "spawn_sync": spawn_sync,
            })
