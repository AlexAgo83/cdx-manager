"""Tests for add, cp, ren, rmv, label, enable, disable.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
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
    main,
)
from src.errors import CdxError
from src.session_service import create_session_service


class LifecycleCommandTests(CliTestBase):

    def test_label_command_updates_json_and_conditional_list_column(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["create_session"]("side")

        no_label_io = self.make_io()
        self.assertEqual(main([], {
            **no_label_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertNotIn("LABEL", no_label_io["stdout"].getvalue().splitlines()[1])

        label_io = self.make_io()
        self.assertEqual(main(["label", "main", " client-a ", "--json"], {
            **label_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(label_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "label")
        self.assertEqual(payload["label"], "client-a")
        self.assertEqual(payload["session"]["label"], "client-a")
        self.assertNotIn("label", payload["session"]["launch"])

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = list_io["stdout"].getvalue()
        self.assertIn("LABEL", output.splitlines()[1])
        self.assertRegex(output, r"\bmain\s+client-a\s+enabled\b")
        self.assertRegex(output, r"\bside\s+-\s+enabled\b")

        json_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        sessions = {row["name"]: row for row in json.loads(json_io["stdout"].getvalue())["sessions"]}
        self.assertEqual(sessions["main"]["label"], "client-a")
        self.assertIsNone(sessions["side"].get("label"))

        clear_io = self.make_io()
        self.assertEqual(main(["label", "main", "--clear", "--json"], {
            **clear_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIsNone(json.loads(clear_io["stdout"].getvalue())["label"])
        self.assertNotIn("label", service["get_session"]("main"))

    def test_label_command_rejects_invalid_input_without_mutating(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_session_label"]("main", "work")

        with self.assertRaisesRegex(CdxError, "Session label"):
            main(["label", "main", "bad\nlabel"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            })
        with self.assertRaisesRegex(CdxError, "Usage: cdx label"):
            main(["label", "main"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            })

        self.assertEqual(service["get_session"]("main")["label"], "work")

    def test_add_and_launch_codex_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        create_io = self.make_io()
        self.assertEqual(main([
            "add", "main"
        ], {
            **create_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Created session main (codex)", create_io["stdout"].getvalue())

        launch_io = self.make_io()
        self.assertEqual(main([
            "main"
        ], {
            **launch_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Launching codex session main", launch_io["stdout"].getvalue())
        self.assertNotIn("Tip:", launch_io["stdout"].getvalue())

        launch_call = next(call for call in harness.calls if call["kind"] == "spawn" and call["command"] == "script")
        transcript_path = _script_transcript_path(launch_call)
        self.assertTrue(
            transcript_path.startswith(os.path.join(temp_dir, "profiles", "main", "log", "cdx-session-"))
        )
        self.assertTrue(transcript_path.endswith(".log"))
        self.assertTrue(_script_launch_invokes(launch_call, "codex"))
        self.assertEqual(_script_launch_args(launch_call)[:3], ["--no-alt-screen", "--cd", os.getcwd()])

    def test_disable_command_marks_session_and_blocks_launch(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })
        main(["add", "other"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        disable_io = self.make_io()
        self.assertEqual(main(["disable", "main", "--json"], {
            **disable_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        disable_payload = json.loads(disable_io["stdout"].getvalue())
        self.assertEqual(disable_payload["action"], "disable")
        self.assertFalse(disable_payload["session"]["enabled"])

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        lines = list_io["stdout"].getvalue().splitlines()
        session_lines = [line for line in lines if line.startswith(("main", "other"))]
        self.assertTrue(session_lines[0].startswith("other"))
        self.assertTrue(session_lines[1].startswith("main"))
        self.assertIn("disabled", session_lines[1])

        with self.assertRaisesRegex(CdxError, "Session is disabled: main"):
            main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })

        enable_io = self.make_io()
        self.assertEqual(main(["enable", "main"], {
            **enable_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Enabled session main", enable_io["stdout"].getvalue())

    def test_add_and_launch_claude_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        create_io = self.make_io()
        self.assertEqual(main([
            "add", "claude", "work1"
        ], {
            **create_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        launch_io = self.make_io()
        self.assertEqual(main([
            "work1"
        ], {
            **launch_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Launching claude session work1", launch_io["stdout"].getvalue())

        launch_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
            and _script_launch_args(call)[:1] == ["--name"]
        )
        self.assertEqual(_script_launch_args(launch_call)[:2], ["--name", "work1"])
        self.assertEqual(
            launch_call["options"]["env"]["HOME"],
            os.path.join(temp_dir, "profiles", "work1", "claude-home"),
        )
        self.assertEqual(
            launch_call["options"]["env"]["ANTHROPIC_CONFIG_DIR"],
            os.path.join(temp_dir, "profiles", "work1", "claude-home"),
        )
        self.assertNotIn("CLAUDE_CONFIG_DIR", launch_call["options"]["env"])
        self.assertEqual(
            launch_call["options"]["env"]["CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS"],
            "1",
        )

        claude_auth_calls = [
            call for call in harness.calls
            if call["command"] == "claude" and call["args"][:2] == ["auth", "status"]
        ]
        self.assertTrue(claude_auth_calls)
        self.assertNotIn("CLAUDE_CONFIG_DIR", claude_auth_calls[-1]["options"]["env"])

    def test_add_and_launch_antigravity_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        create_io = self.make_io()
        self.assertEqual(main([
            "add", "antigravity", "agy1"
        ], {
            **create_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Created session agy1 (antigravity)", create_io["stdout"].getvalue())

        launch_io = self.make_io()
        self.assertEqual(main([
            "agy1"
        ], {
            **launch_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Launching antigravity session agy1", launch_io["stdout"].getvalue())

        launch_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "agy")
        )
        self.assertEqual(
            launch_call["options"]["cwd"],
            os.getcwd(),
        )
        self.assertEqual(
            launch_call["options"]["env"]["HOME"],
            os.path.join(temp_dir, "profiles", "agy1", "antigravity-home"),
        )

    def test_add_set_model_and_launch_ollama_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        create_io = self.make_io()
        self.assertEqual(main([
            "add", "ollama", "local", "--model", "llama3.2", "--json"
        ], {
            **create_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        launch = json.loads(create_io["stdout"].getvalue())["session"]["launch"]
        self.assertEqual(launch["model"], "llama3.2")
        self.assertEqual(launch["power"], "medium")
        self.assertIs(launch["fast"], False)

        self.assertEqual(main(["power", "local", "medium"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertEqual(main(["perm", "local", "full"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        config_io = self.make_io()
        self.assertEqual(main(["config", "local"], {
            **config_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Model", config_io["stdout"].getvalue())
        self.assertIn("llama3.2", config_io["stdout"].getvalue())

        launch_io = self.make_io()
        self.assertEqual(main([
            "local"
        ], {
            **launch_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertIn("Launching ollama session local", launch_io["stdout"].getvalue())

        launch_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "ollama")
        )
        self.assertEqual(launch_call["options"]["env"]["OLLAMA_NOHISTORY"], "1")
        self.assertEqual(
            _script_launch_args(launch_call)[:2],
            ["run", "llama3.2"],
        )
        self.assertNotIn("logics-manager status", _script_launch_text(launch_call))
        self.assertNotIn("prefer RTK wrappers", _script_launch_text(launch_call))

    def test_add_ollama_requires_model(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        with self.assertRaisesRegex(CdxError, "Usage: cdx add ollama <name> --model MODEL"):
            main(["add", "ollama", "local"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })

    def test_remove_confirm_cancel_and_status(self):
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

        status_io = self.make_io()
        self.assertEqual(main(["status"], {**status_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertIn("SESSION", status_io["stdout"].getvalue())

        cancel_io = self.make_io()
        self.assertEqual(main([
            "rmv", "main"
        ], {
            **cancel_io,
            "env": {"CDX_HOME": temp_dir},
            "confirmRemove": lambda name: False,
        }), 0)
        self.assertIn("Cancelled.", cancel_io["stdout"].getvalue())

        force_io = self.make_io()
        self.assertEqual(main([
            "rmv", "main", "--force"
        ], {**force_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertIn("Removed session main", force_io["stdout"].getvalue())

    def test_rename_session_command(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("old")

        rename_io = self.make_io()
        self.assertEqual(main(["ren", "old", "new"], {
            **rename_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn("Renamed session old to new", rename_io["stdout"].getvalue())
        self.assertIsNone(service["get_session"]("old"))
        self.assertEqual(service["get_session"]("new")["name"], "new")

    def test_add_reports_missing_provider_cli_without_traceback(self):
        temp_dir = self.make_temp_dir()

        with mock.patch("src.session_service._get_global_codex_home", return_value=temp_dir):
            with mock.patch("src.provider_runtime.subprocess.run", side_effect=FileNotFoundError("codex")):
                with self.assertRaises(CdxError) as ctx:
                    main(["add", "main"], {
                        **self.make_io(),
                        "env": {"CDX_HOME": temp_dir},
                    })

        self.assertIn("Failed to check login status for main", str(ctx.exception))
        self.assertIn("codex CLI not found on PATH", str(ctx.exception))
        self.assertEqual(ctx.exception.exit_code, 127)

    def test_named_session_does_not_warn_about_selection(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        self._authenticated_codex_session(service, name="named")

        def spawn(_argv, **kwargs):
            kwargs["stdout"].write("ok\n")
            return _HeadlessChild(0)

        io_obj = self.make_io()
        self.assertEqual(main([
            "run", "named", "--cwd", target_dir, "--prompt", "Do it",
            "--permission", "full", "--json",
        ], self.make_run_ctx(io_obj, service, spawn_headless=spawn)), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertNotIn(
            "session_selected_without_status",
            [warning["code"] for warning in payload["warnings"]],
        )

