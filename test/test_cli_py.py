import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

from src.cli import (
    _format_blocking_quota,
    _format_reset_time,
    _format_status_rows,
    _pad_table,
    _visible_len,
    format_json_error,
    main,
)
from src.errors import CdxError
from src.health import collect_health_report
from src.session_service import create_session_service


class _Stream:
    def __init__(self):
        self._buffer = io.StringIO()

    def write(self, value):
        self._buffer.write(value)

    def getvalue(self):
        return self._buffer.getvalue()


class _TtyStream(_Stream):
    def isatty(self):
        return True


class _SignalEmitter:
    def __init__(self):
        self._handlers = {}

    def on(self, sig, handler):
        self._handlers.setdefault(sig, []).append(handler)

    def removeListener(self, sig, handler):
        handlers = self._handlers.get(sig, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, sig):
        for handler in list(self._handlers.get(sig, [])):
            handler()


class _Child:
    def __init__(self, on_wait=None):
        self.returncode = 0
        self._on_wait = on_wait
        self.signals = []

    def wait(self):
        if self._on_wait:
            self._on_wait(self)

    def send_signal(self, sig):
        self.signals.append(sig)
        self.returncode = -int(sig)


class _AuthHarness:
    def __init__(self, initial_auth=None):
        self.calls = []
        self.auth_by_home = dict(initial_auth or {})

    @staticmethod
    def _get_home(payload):
        if isinstance(payload, dict):
            env = payload.get("env", {})
            return env.get("CODEX_HOME") or env.get("HOME")
        return None

    def spawn_sync(self, command, args, options=None):
        options = options or {}
        self.calls.append({
            "kind": "spawnSync",
            "command": command,
            "args": list(args),
            "options": options,
        })
        home = self._get_home(options)
        authed = self.auth_by_home.get(home, False)
        if command == "codex" and args[:2] == ["login", "status"]:
            return {"stdout": "Logged in using ChatGPT\n" if authed else "Not logged in\n", "stderr": ""}
        if command == "claude" and args[:2] == ["auth", "status"]:
            text = '{"loggedIn": %s, "authMethod": "%s"}\n' % (
                "true" if authed else "false",
                "oauth" if authed else "none",
            )
            return {"stdout": text, "stderr": ""}
        return {"stdout": "", "stderr": ""}

    def spawn(self, argv, **kwargs):
        self.calls.append({
            "kind": "spawn",
            "command": argv[0],
            "args": list(argv[1:]),
            "options": kwargs,
        })
        home = self._get_home(kwargs)
        command = argv[0]
        args = argv[1:]
        if command == "codex" and args == ["login"]:
            self.auth_by_home[home] = True
        if command == "codex" and args == ["logout"]:
            self.auth_by_home[home] = False
        if command == "claude" and args == ["auth", "login"]:
            self.auth_by_home[home] = True
        if command == "claude" and args == ["auth", "logout"]:
            self.auth_by_home[home] = False
        return _Child()


class CliPythonTests(unittest.TestCase):
    def make_temp_dir(self):
        return tempfile.mkdtemp(prefix="cdx-cli-py-")

    def make_io(self):
        return {
            "stdin": {"isTTY": True},
            "stdout": _Stream(),
            "stderr": _Stream(),
        }

    def test_reset_time_formatting_uses_countdown_under_24h(self):
        future = datetime.now().astimezone() + timedelta(hours=2, minutes=30)
        later = datetime.now().astimezone() + timedelta(days=2)
        past = datetime.now().astimezone() - timedelta(hours=1, minutes=5)

        self.assertIn(_format_reset_time(future.isoformat()), ("in 2h 29m", "in 2h 30m"))
        self.assertEqual(_format_reset_time(later.isoformat()), later.isoformat())
        self.assertEqual(_format_reset_time(past.isoformat()), "passed 1h ago")

    def test_status_table_is_sorted_by_priority_availability(self):
        output = _format_status_rows([
            {
                "session_name": "blocked",
                "provider": "codex",
                "available_pct": 0,
                "remaining_5h_pct": 0,
                "remaining_week_pct": 80,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "available",
                "provider": "codex",
                "available_pct": 42,
                "remaining_5h_pct": 42,
                "remaining_week_pct": 90,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "credit",
                "provider": "codex",
                "available_pct": 95,
                "remaining_5h_pct": 95,
                "remaining_week_pct": 95,
                "credits": 453,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        lines = output.splitlines()
        self.assertTrue(lines[1].startswith("available"))
        self.assertTrue(lines[2].startswith("credit"))
        self.assertTrue(lines[3].startswith("blocked"))

    def test_status_small_hides_metadata_columns(self):
        rows = [
            {
                "session_name": "main",
                "provider": "codex",
                "available_pct": 6,
                "remaining_5h_pct": 100,
                "remaining_week_pct": 6,
                "credits": 453,
                "reset_5h_at": "Apr 16 05:44",
                "reset_week_at": "Apr 18 00:08",
                "updated_at": "2026-04-15T10:00:00+00:00",
            },
            {
                "session_name": "claude",
                "provider": "claude",
                "available_pct": 0,
                "remaining_5h_pct": 0,
                "remaining_week_pct": 75,
                "credits": None,
                "reset_5h_at": "Apr 16 02:00",
                "reset_week_at": "Apr 21 14:00",
                "updated_at": "2026-04-15T10:00:00+00:00",
            },
        ]

        output = _format_status_rows(rows, small=True)
        header = output.splitlines()[0]
        self.assertIn("SESSION", header)
        self.assertIn("OK", header)
        self.assertIn("5H", header)
        self.assertIn("WEEK", header)
        self.assertIn("RESET 5H", header)
        self.assertIn("RESET WEEK", header)
        self.assertNotIn("PROV.", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        self.assertNotIn("UPDATED", header)
        self.assertIn("Priority:", output)
        self.assertIn("Tip:", output)

    def test_blocking_quota_formatting_identifies_lowest_limit(self):
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 99,
            "remaining_week_pct": 0,
        }), "WEEK")
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
        }), "5H")
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 0,
            "remaining_week_pct": 0,
        }), "5H+WEEK")

    def test_ansi_padding_uses_visible_width(self):
        table = _pad_table([
            ["H", "NEXT"],
            ["\033[31mred\033[0m", "x"],
        ])
        lines = table.splitlines()
        self.assertEqual(_visible_len(lines[0].split("NEXT")[0]), 5)
        self.assertEqual(_visible_len(lines[1].split("x")[0]), 5)
        self.assertEqual(_visible_len("\033[31mred\033[0m"), 3)

    def test_help_and_version_flags(self):
        help_io = self.make_io()
        version_io = self.make_io()

        self.assertEqual(main(["--help"], help_io), 0)
        self.assertIn("Usage:", help_io["stdout"].getvalue())

        self.assertEqual(main(["-v"], version_io), 0)
        self.assertRegex(version_io["stdout"].getvalue().strip(), r"^\d+\.\d+\.\d+$")

    def test_non_status_outputs_use_color_when_enabled(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("old")

        help_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["--help"], {
            **help_io,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        self.assertIn("\033[", help_io["stdout"].getvalue())

        list_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        self.assertIn("\033[", list_io["stdout"].getvalue())

        rename_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["ren", "old", "new"], {
            **rename_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        self.assertIn("\033[", rename_io["stdout"].getvalue())
        self.assertIn("Renamed session old to new", rename_io["stdout"].getvalue())

    def test_main_screen_formats_updated_as_relative_age(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("just now", output)
        self.assertNotRegex(output, r"\d{4}-\d{2}-\d{2}T")

    def test_main_screen_surfaces_update_notice(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("Update available: cdx-manager 9.9.9", output)

    def test_main_screen_json_includes_update_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "update_available")
        self.assertEqual(payload["warnings"][0]["latest_version"], "9.9.9")

    def test_root_list_supports_json_contract(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "list")
        self.assertEqual(payload["sessions"][0]["name"], "main")

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
        self.assertIn("Tip: run /status once the Codex session opens.", launch_io["stdout"].getvalue())

        launch_call = next(call for call in harness.calls if call["kind"] == "spawn" and call["command"] == "script")
        self.assertEqual(
            launch_call["args"][:3],
            ["-q", "-F", launch_call["args"][2]],
        )
        self.assertTrue(
            launch_call["args"][2].startswith(os.path.join(temp_dir, "profiles", "main", "log", "cdx-session-"))
        )
        self.assertTrue(launch_call["args"][2].endswith(".log"))
        self.assertEqual(launch_call["args"][3], "codex")
        self.assertEqual(launch_call["args"][4:7], ["--no-alt-screen", "--cd", os.getcwd()])

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
        self.assertIn("Update available: cdx-manager 9.9.9", launch_io["stdout"].getvalue())

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
            if call["kind"] == "spawn" and call["command"] == "claude" and call["args"] == ["--name", "work1"]
        )
        self.assertEqual(launch_call["args"], ["--name", "work1"])
        self.assertEqual(
            launch_call["options"]["env"]["HOME"],
            os.path.join(temp_dir, "profiles", "work1", "claude-home"),
        )

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

    def test_mutation_commands_support_json_contract(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        add_io = self.make_io()
        self.assertEqual(main(["add", "main", "--json"], {
            **add_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        add_payload = json.loads(add_io["stdout"].getvalue())
        self.assertTrue(add_payload["ok"])
        self.assertEqual(add_payload["action"], "add")
        self.assertEqual(add_payload["session"]["name"], "main")

        copy_io = self.make_io()
        self.assertEqual(main(["cp", "main", "copy", "--json"], {
            **copy_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        copy_payload = json.loads(copy_io["stdout"].getvalue())
        self.assertEqual(copy_payload["action"], "copy")
        self.assertEqual(copy_payload["session"]["name"], "copy")
        self.assertFalse(copy_payload["overwritten"])

        rename_io = self.make_io()
        self.assertEqual(main(["ren", "copy", "renamed", "--json"], {
            **rename_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        rename_payload = json.loads(rename_io["stdout"].getvalue())
        self.assertEqual(rename_payload["action"], "rename")
        self.assertEqual(rename_payload["session"]["name"], "renamed")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "main", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        clean_payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(clean_payload["action"], "clean")
        self.assertEqual(clean_payload["sessions"][0]["session_name"], "main")

        logout_io = self.make_io()
        self.assertEqual(main(["logout", "main", "--json"], {
            **logout_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        logout_payload = json.loads(logout_io["stdout"].getvalue())
        self.assertEqual(logout_payload["action"], "logout")
        self.assertEqual(logout_payload["session"]["auth"]["status"], "logged_out")

        login_io = self.make_io()
        self.assertEqual(main(["login", "main", "--json"], {
            **login_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        login_payload = json.loads(login_io["stdout"].getvalue())
        self.assertEqual(login_payload["action"], "login")
        self.assertEqual(login_payload["session"]["auth"]["status"], "authenticated")

        remove_io = self.make_io()
        self.assertEqual(main(["rmv", "renamed", "--force", "--json"], {
            **remove_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        remove_payload = json.loads(remove_io["stdout"].getvalue())
        self.assertEqual(remove_payload["action"], "remove")
        self.assertEqual(remove_payload["session"]["name"], "renamed")
        self.assertFalse(remove_payload["cancelled"])

    def test_export_import_commands_support_json_contract(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main", "--json"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        export_path = os.path.join(temp_dir, "backup.cdx")
        export_io = self.make_io()
        self.assertEqual(main(["export", export_path, "--json"], {
            **export_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertEqual(export_payload["action"], "export")
        self.assertEqual(export_payload["bundle"]["path"], export_path)
        self.assertEqual(export_payload["bundle"]["session_names"], ["main"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main(["import", export_path, "--json"], {
            **import_io,
            "env": {"CDX_HOME": import_dir},
        }), 0)
        import_payload = json.loads(import_io["stdout"].getvalue())
        self.assertEqual(import_payload["action"], "import")
        self.assertEqual(import_payload["bundle"]["session_names"], ["main"])

        imported_service = create_session_service({"base_dir": import_dir})
        self.assertEqual(imported_service["get_session"]("main")["name"], "main")

    def test_export_with_auth_uses_passphrase_env_and_import_restores_profile(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "claude", "claude1", "--json"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        auth_path = os.path.join(temp_dir, "profiles", "claude1", "claude-home", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')

        export_path = os.path.join(temp_dir, "secure.cdx")
        export_io = self.make_io()
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json",
        ], {
            **export_io,
            "env": {"CDX_HOME": temp_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertTrue(export_payload["bundle"]["include_auth"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main([
            "import", export_path, "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json",
        ], {
            **import_io,
            "env": {"CDX_HOME": import_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)
        imported_auth = os.path.join(import_dir, "profiles", "claude1", "claude-home", "auth.json")
        with open(imported_auth, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')

    def test_export_with_auth_rejects_non_interactive_without_passphrase_env(self):
        temp_dir = self.make_temp_dir()
        create_session_service({"base_dir": temp_dir})["create_session"]("main")
        io_obj = self.make_io()
        io_obj["stdin"] = {"isTTY": False}

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal or --passphrase-env"):
            main(["export", os.path.join(temp_dir, "backup.cdx"), "--include-auth"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir},
            })

    def test_import_rejects_wrong_passphrase(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        bundle_path = os.path.join(temp_dir, "secure.cdx")
        service["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        import_dir = self.make_temp_dir()
        with self.assertRaisesRegex(CdxError, "Invalid bundle passphrase or corrupted bundle"):
            main(["import", bundle_path, "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": import_dir, "CDX_BUNDLE_PASSPHRASE": "wrong"},
            })

    def test_status_uses_async_refresh_function(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1", "claude")

        async def refresh(_session):
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 60,
                "reset_5h_at": "Apr 16 02:21",
                "reset_week_at": "Apr 17 10:10",
                "reset_at": "Apr 17",
                "updated_at": "2026-04-15T10:00:00+00:00",
            }

        status_io = self.make_io()
        self.assertEqual(main([
            "status"
        ], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertIn("work1", output)
        self.assertIn("OK", output)
        self.assertIn("CR", output)
        self.assertNotIn("AVAIL.", output)
        self.assertNotIn("AVAILABLE", output)
        self.assertNotIn("CREDITS", output)
        self.assertIn("80%", output)
        self.assertIn("60%", output)
        self.assertIn("RESET 5H", output)
        self.assertIn("RESET WEEK", output)
        self.assertIn("Priority: use work1 first (60% OK).", output)

    def test_status_skips_fresh_claude_refresh_unless_forced(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        def refresh(_session):
            raise AssertionError("fresh status should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("80%", status_io["stdout"].getvalue())

        def forced_refresh(_session):
            return {
                "remaining_5h_pct": 55,
                "remaining_week_pct": 44,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        refresh_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **refresh_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": forced_refresh,
        }), 0)
        self.assertIn("44%", refresh_io["stdout"].getvalue())

    def test_status_detail_refreshes_only_requested_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["create_session"]("claude", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 70,
            "remaining_week_pct": 70,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        def refresh(_session):
            raise AssertionError("unrequested Claude session should not refresh")

        detail_io = self.make_io()
        self.assertEqual(main(["status", "main"], {
            **detail_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("Session: main", detail_io["stdout"].getvalue())

    def test_status_surfaces_claude_refresh_errors(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")

        def refresh(_session):
            raise RuntimeError("offline")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("Warning: Claude refresh failed for claude: offline", status_io["stdout"].getvalue())

        json_io = self.make_io()
        self.assertEqual(main(["status", "--json", "--refresh"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["action"], "status")
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["warnings"][0]["code"], "claude_refresh_failed")
        self.assertEqual(json_io["stderr"].getvalue(), "")

    def test_status_small_flag_renders_compact_table(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main", "codex")
        service["create_session"]("claude", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 99,
            "remaining_week_pct": 10,
            "credits": 453,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 17 10:10",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 17 10:10",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "-s"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = status_io["stdout"].getvalue()
        header = output.splitlines()[0]
        self.assertIn("SESSION", header)
        self.assertIn("RESET 5H", header)
        self.assertNotIn("PROV.", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        self.assertNotIn("UPDATED", header)
        self.assertIn("claude", output)
        self.assertIn("main", output)

    def test_status_color_respects_env_flags(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["status"], {
            **color_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        self.assertIn("\033[", color_io["stdout"].getvalue())

        plain_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["status"], {
            **plain_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1", "NO_COLOR": "1"},
        }), 0)
        self.assertNotIn("\033[", plain_io["stdout"].getvalue())

    def test_status_recommends_non_credit_session_first(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("credit")
        service["create_session"]("regular")
        service["record_status"]("credit", {
            "remaining_5h_pct": 95,
            "remaining_week_pct": 95,
            "credits": 453,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("regular", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T09:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Priority: use regular first (80% OK), next credit (95% OK).",
            status_io["stdout"].getvalue(),
        )

    def test_status_recommends_earliest_blocking_reset_for_zero_ok(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        future = datetime.now() + timedelta(days=1)
        later = future + timedelta(hours=1)
        service["create_session"]("work1")
        service["create_session"]("work2")
        service["create_session"]("claude", "claude")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("work2", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 69,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
            "reset_5h_at": future.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Priority: use work1 first (6% OK), next claude (0% OK, 5H resets first).",
            status_io["stdout"].getvalue(),
        )

    def test_status_uses_blocking_reset_before_credit_penalty_for_blocked_accounts(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        soon = datetime.now() + timedelta(hours=1)
        later = datetime.now() + timedelta(hours=2)
        service["create_session"]("work1")
        service["create_session"]("credit")
        service["create_session"]("regular")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("credit", {
            "remaining_5h_pct": 99,
            "remaining_week_pct": 0,
            "credits": 453,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": soon.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("regular", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 80,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Priority: use work1 first (6% OK), next credit (0% OK, WEEK resets first).",
            status_io["stdout"].getvalue(),
        )

    def test_status_recommends_refresh_when_blocking_reset_has_passed(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        past = datetime.now() - timedelta(hours=1)
        later_past = datetime.now() - timedelta(minutes=30)
        service["create_session"]("work1")
        service["create_session"]("work2")
        service["create_session"]("claude", "claude")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": "Apr 16 05:44",
            "reset_week_at": "Apr 18 00:08",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("work2", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 69,
            "reset_5h_at": later_past.astimezone().isoformat(),
            "reset_week_at": "Apr 22 16:51",
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
            "reset_5h_at": past.astimezone().isoformat(),
            "reset_week_at": "Apr 21 14:00",
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Priority: use work1 first (6% OK), refresh claude next (0% OK, 5H reset passed).",
            status_io["stdout"].getvalue(),
        )

    def test_status_json_global_and_detail_contract(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 39,
            "remaining_week_pct": 70,
            "credits": 453,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 17 10:10",
            "reset_at": "Apr 17 10:10",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        global_io = self.make_io()
        self.assertEqual(main(["status", "--json"], {
            **global_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(global_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        rows = payload["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["available_pct"], 39)
        self.assertEqual(rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(rows[0]["remaining_week_pct"], 70)
        self.assertEqual(rows[0]["credits"], 453)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17 10:10")

        detail_io = self.make_io()
        self.assertEqual(main(["status", "main", "--json"], {
            **detail_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        detail_payload = json.loads(detail_io["stdout"].getvalue())
        self.assertEqual(detail_payload["schema_version"], 1)
        row = detail_payload["session"]
        self.assertEqual(row["session_name"], "main")
        self.assertEqual(row["available_pct"], 39)
        self.assertEqual(row["credits"], 453)
        self.assertEqual(row["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(row["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(row["reset_at"], "Apr 17 10:10")

    def test_invalid_status_syntax_raises_usage_error(self):
        with self.assertRaises(CdxError) as ctx:
            main(["status", "main", "extra"], self.make_io())
        self.assertIn("Usage: cdx status [--json]", str(ctx.exception))
        with self.assertRaises(CdxError) as small_ctx:
            main(["status", "main", "--small"], self.make_io())
        self.assertIn("cdx status --small|-s", str(small_ctx.exception))
        with self.assertRaises(CdxError) as json_ctx:
            main(["status", "--small", "--json"], self.make_io())
        self.assertIn("cdx status --small|-s", str(json_ctx.exception))

    def test_non_interactive_login_and_remove_are_rejected(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        with self.assertRaises(CdxError) as login_ctx:
            main(["login", "main"], {
                "stdin": {"isTTY": False},
                "stdout": _Stream(),
                "stderr": _Stream(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })
        self.assertIn("Login requires an interactive terminal.", str(login_ctx.exception))

        with self.assertRaises(CdxError) as remove_ctx:
            main(["rmv", "main"], {
                "stdin": {"isTTY": False},
                "stdout": _Stream(),
                "stderr": _Stream(),
                "env": {"CDX_HOME": temp_dir},
            })
        self.assertIn("Removal requires confirmation", str(remove_ctx.exception))

    def test_probe_provider_auth_surfaces_spawn_sync_errors(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        class ProbeError(Exception):
            def __str__(self):
                return "boom"

        def bad_spawn_sync(_command, _args, _spec):
            return {"error": ProbeError()}

        with self.assertRaises(CdxError) as ctx:
            main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
                "spawn_sync": bad_spawn_sync,
                "spawn": lambda argv, **kwargs: _Child(),
            })
        self.assertIn("Failed to check login status", str(ctx.exception))

    def test_status_empty_json_is_stable(self):
        temp_dir = self.make_temp_dir()
        io_obj = self.make_io()
        self.assertEqual(main(["status", "--json"], {**io_obj, "env": {"CDX_HOME": temp_dir}}), 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["rows"], [])

    def test_doctor_reports_missing_state_and_json_summary(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        os.remove(os.path.join(temp_dir, "state", "main.json"))

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(doctor_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["report"]["summary"]["fail"], 1)
        self.assertTrue(any(issue["code"] == "missing_state" for issue in payload["report"]["issues"]))

    def test_doctor_windows_script_warning_mentions_expected_fallback(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch("src.health.sys.platform", "win32"):
            report = collect_health_report(service, temp_dir, env={"PATH": ""})

        issue = next(item for item in report["issues"] if item["code"] == "script_cli")
        self.assertIn("expected on many Windows setups", issue["message"])

    def test_json_error_payload_has_machine_readable_contract(self):
        error = CdxError("Unknown session: missing", exit_code=3)
        payload = json.loads(format_json_error(error))
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unknown_session")
        self.assertEqual(payload["error"]["message"], "Unknown session: missing")
        self.assertEqual(payload["error"]["exit_code"], 3)

    def test_repair_dry_run_and_force_recreate_missing_state(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        state_path = os.path.join(temp_dir, "state", "main.json")
        os.remove(state_path)

        dry_io = self.make_io()
        self.assertEqual(main(["repair", "--dry-run"], {
            **dry_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertFalse(os.path.exists(state_path))
        self.assertIn("PLANNED", dry_io["stdout"].getvalue())

        force_io = self.make_io()
        self.assertEqual(main(["repair", "--force"], {
            **force_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertTrue(os.path.exists(state_path))
        self.assertIn("APPLIED", force_io["stdout"].getvalue())

    def test_repair_force_quarantines_orphan_profile(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        orphan = os.path.join(temp_dir, "profiles", "old")
        os.makedirs(orphan, exist_ok=True)

        repair_io = self.make_io()
        self.assertEqual(main(["repair", "--force"], {
            **repair_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertFalse(os.path.exists(orphan))
        self.assertTrue(os.path.isdir(os.path.join(temp_dir, "profiles", ".old.remove.orphan")))

    def test_notify_at_reset_once_and_next_ready(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        reset = datetime.now().astimezone() - timedelta(minutes=1)
        service["record_status"]("main", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 20,
            "reset_5h_at": reset.isoformat(),
            "updated_at": reset.isoformat(),
        })
        notifications = []

        def spawn_sync(argv, **kwargs):
            notifications.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        notify_io = self.make_io()
        self.assertEqual(main(["notify", "main", "--at-reset", "--once"], {
            **notify_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": spawn_sync,
        }), 0)
        self.assertIn("main reset is due", notify_io["stdout"].getvalue())

        next_io = self.make_io()
        self.assertEqual(main(["notify", "--next-ready", "--once", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": spawn_sync,
        }), 0)
        payload = json.loads(next_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["event"]["ready"])

    def test_bin_cdx_runs_as_real_subprocess(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir}
        result = subprocess.run(
            [sys.executable, "bin/cdx", "--help"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_bin_cdx_colors_errors_when_enabled(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"}
        env.pop("NO_COLOR", None)
        result = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("\033[31m", result.stderr)
        self.assertIn("Usage: cdx status [--json]", result.stderr)

        plain = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra"],
            cwd=os.getcwd(),
            env={**env, "NO_COLOR": "1"},
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(plain.returncode, 0)
        self.assertNotIn("\033[", plain.stderr)

    def test_bin_cdx_writes_json_errors_when_requested(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir}
        result = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra", "--json"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_usage")
        self.assertIn("Usage: cdx status [--json]", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
