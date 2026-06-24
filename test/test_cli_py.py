import io
import importlib.util
import json
import os
import shlex
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
from src.cli_commands import _extract_claude_oauth_token
from src.errors import CdxError
from src.health import collect_health_report
from src.session_service import create_session_service


HAS_CRYPTOGRAPHY = importlib.util.find_spec("cryptography") is not None
CRYPTOGRAPHY_REQUIRED = "cryptography is required for encrypted auth bundle tests"


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


class _HeadlessChild:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.pid = 4321

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = 124

    def kill(self):
        self.returncode = 124


class _TimeoutChild(_HeadlessChild):
    def wait(self, timeout=None):
        if timeout is not None and self.returncode == 0:
            raise subprocess.TimeoutExpired("codex", timeout)
        return self.returncode


class _AuthHarness:
    def __init__(self, initial_auth=None, claude_login_authenticates=True, claude_setup_token_text=None):
        self.calls = []
        self.auth_by_home = dict(initial_auth or {})
        self.claude_login_authenticates = claude_login_authenticates
        self.claude_setup_token_text = claude_setup_token_text

    @staticmethod
    def _get_home(payload):
        if isinstance(payload, dict):
            env = payload.get("env", {})
            return env.get("CODEX_HOME") or env.get("HOME")
        return None

    @staticmethod
    def _auth_path(home):
        return os.path.join(home, "auth.json") if home else None

    @staticmethod
    def _claude_oauth_path(home):
        return os.path.join(home, "credentials", "default.json") if home else None

    def _is_authed(self, home):
        if self.auth_by_home.get(home):
            return True
        auth_path = self._auth_path(home)
        claude_oauth_path = self._claude_oauth_path(home)
        return bool(
            (auth_path and os.path.isfile(auth_path))
            or (claude_oauth_path and os.path.isfile(claude_oauth_path))
        )

    def spawn_sync(self, command, args, options=None):
        options = options or {}
        self.calls.append({
            "kind": "spawnSync",
            "command": command,
            "args": list(args),
            "options": options,
        })
        home = self._get_home(options)
        authed = self._is_authed(home)
        if command == "codex" and args[:2] == ["login", "status"]:
            return {"stdout": "Logged in using ChatGPT\n" if authed else "Not logged in\n", "stderr": ""}
        if command == "claude" and args[:2] == ["auth", "status"]:
            text = '{"loggedIn": %s, "authMethod": "%s"}\n' % (
                "true" if authed else "false",
                "oauth" if authed else "none",
            )
            return {"stdout": text, "stderr": ""}
        if command == "agy" and args == ["--version"]:
            return {"stdout": "agy 1.0.0\n", "stderr": ""}
        if command == "ollama" and args == ["--version"]:
            return {"stdout": "ollama version is 0.12.10\n", "stderr": ""}
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
            if home:
                os.makedirs(home, exist_ok=True)
                with open(self._auth_path(home), "w", encoding="utf-8") as handle:
                    handle.write("{}\n")
        if command == "codex" and args == ["logout"]:
            self.auth_by_home[home] = False
            if home:
                try:
                    os.remove(self._auth_path(home))
                except FileNotFoundError:
                    pass
        if command == "claude" and args[:2] == ["auth", "login"]:
            self.auth_by_home[home] = self.claude_login_authenticates
        if command == "claude" and args == ["auth", "logout"]:
            self.auth_by_home[home] = False
        if command == "script" and _script_launch_invokes(self.calls[-1], "claude"):
            launch_args = _script_launch_args(self.calls[-1])
            if launch_args == ["setup-token"]:
                transcript_path = _script_transcript_path(self.calls[-1])
                os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
                with open(transcript_path, "w", encoding="utf-8") as handle:
                    handle.write(
                        self.claude_setup_token_text
                        or "Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat-test\n"
                    )
        if command == "agy":
            self.auth_by_home[home] = True
        if command == "ollama":
            self.auth_by_home[home] = True
        return _Child()


def _script_launch_text(call):
    args = call["args"]
    if args[:3] == ["-q", "-F", "-c"]:
        return args[3]
    return " ".join(shlex.quote(arg) for arg in args[3:])


def _script_launch_invokes(call, command):
    text = _script_launch_text(call)
    return text == command or text.startswith(f"{command} ")


def _script_launch_args(call):
    args = call["args"]
    if args[:3] == ["-q", "-F", "-c"]:
        return shlex.split(args[3])[1:]
    return args[4:]


def _script_transcript_path(call):
    args = call["args"]
    if args[:3] == ["-q", "-F", "-c"]:
        return args[4]
    return args[2]


class CliPythonTests(unittest.TestCase):
    def setUp(self):
        self.codex_status_patch = mock.patch("src.session_service.fetch_codex_rate_limits", return_value=None)
        self.codex_status_patch.start()
        self.update_check_patch = mock.patch("src.cli.check_for_update", return_value=None)
        self.update_check_patch.start()

    def tearDown(self):
        self.update_check_patch.stop()
        self.codex_status_patch.stop()

    def make_temp_dir(self):
        return tempfile.mkdtemp(prefix="cdx-cli-py-")

    def make_io(self):
        return {
            "stdin": {"isTTY": True},
            "stdout": _Stream(),
            "stderr": _Stream(),
        }

    def make_run_ctx(self, io_obj, service, **overrides):
        return {
            **io_obj,
            "service": service,
            "spawn_sync": _AuthHarness().spawn_sync,
            **overrides,
        }

    def test_reset_time_formatting_uses_countdown(self):
        now = datetime.now().astimezone()
        future = now + timedelta(hours=2, minutes=30)
        soon = now + timedelta(seconds=90)
        later = now + timedelta(days=2)
        later_with_hours = now + timedelta(days=2, hours=3)
        past = now - timedelta(hours=1, minutes=5)

        with mock.patch("src.status_view._now_timestamp", return_value=now.timestamp()):
            self.assertEqual(_format_reset_time(future.isoformat()), "in 2h 31m")
            self.assertEqual(_format_reset_time(soon.isoformat()), "in 2m")
            self.assertEqual(_format_reset_time(later.isoformat()), "in 2d")
            self.assertEqual(_format_reset_time(later_with_hours.isoformat()), "in 2d 3h")
            self.assertEqual(_format_reset_time(past.isoformat()), "passed 1h ago")

    def test_status_table_is_sorted_by_priority_availability(self):
        output = _format_status_rows([
            {
                "session_name": "blocked",
                "provider": "codex",
                "auth_status": "authenticated",
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
                "auth_status": "authenticated",
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
                "auth_status": "authenticated",
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
        self.assertIn("AUTH", lines[0])
        self.assertIn("logged", lines[1])
        self.assertTrue(lines[1].startswith("available"))
        self.assertTrue(lines[2].startswith("credit"))
        self.assertTrue(lines[3].startswith("blocked"))

    def test_status_table_formats_credits_with_two_decimals(self):
        output = _format_status_rows([
            {
                "session_name": "credit",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 95,
                "remaining_5h_pct": 95,
                "remaining_week_pct": 95,
                "credits": "453.456",
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        self.assertRegex(output.splitlines()[1], r"\b453\.46\b")
        self.assertNotIn("453.456", output)

    def test_status_priority_skips_logged_out_sessions(self):
        output = _format_status_rows([
            {
                "session_name": "loggedout",
                "provider": "claude",
                "auth_status": "logged_out",
                "available_pct": 100,
                "remaining_5h_pct": 100,
                "remaining_week_pct": 100,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "loggedin",
                "provider": "claude",
                "auth_status": "authenticated",
                "available_pct": 50,
                "remaining_5h_pct": 50,
                "remaining_week_pct": 50,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        self.assertIn("Priority: use loggedin first", output)
        self.assertNotIn("use loggedout", output)

    def test_status_auth_is_not_applicable_for_local_providers(self):
        output = _format_status_rows([
            {
                "session_name": "local",
                "provider": "ollama",
                "auth_status": "authenticated",
                "available_pct": None,
                "remaining_5h_pct": None,
                "remaining_week_pct": None,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "agy",
                "provider": "antigravity",
                "auth_status": "authenticated",
                "available_pct": None,
                "remaining_5h_pct": None,
                "remaining_week_pct": None,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        lines = output.splitlines()
        self.assertRegex(lines[1], r"\bollama\s+enabled\s+n/a\b")
        self.assertRegex(lines[2], r"\bantigravity\s+enabled\s+n/a\b")

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
        self.assertIn("Current:", output)
        self.assertNotIn("Tip:", output)

    def test_blocking_quota_formatting_identifies_lowest_limit(self):
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
        }), "-")
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
        self.assertIn("cdx update [--check] [--yes] [--json] [--version TAG]", help_io["stdout"].getvalue())
        self.assertIn("cdx ready [--refresh] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx next [--json] [--refresh]", help_io["stdout"].getvalue())
        self.assertIn("cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b>", help_io["stdout"].getvalue())
        self.assertIn("cdx stats [name]", help_io["stdout"].getvalue())
        self.assertIn("cdx resume <name> [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx can-resume <name> [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx add [provider] <name> [--model MODEL] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx set <name>|--sessions all|a,b|--provider PROVIDER", help_io["stdout"].getvalue())
        self.assertIn("--model MODEL", help_io["stdout"].getvalue())
        self.assertIn("--priority 0..100", help_io["stdout"].getvalue())
        self.assertIn("--rtk on|off", help_io["stdout"].getvalue())
        self.assertIn("--min-power minimal|low|medium|high|xhigh", help_io["stdout"].getvalue())
        self.assertIn("--power minimal|low|medium|high|xhigh", help_io["stdout"].getvalue())
        self.assertIn("workspace-write|read-only|danger-full-access", help_io["stdout"].getvalue())

        self.assertEqual(main(["-v"], version_io), 0)
        self.assertRegex(version_io["stdout"].getvalue().strip(), r"^\d+\.\d+\.\d+$")

    def test_update_check_json_reports_available_update(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")

        list_io = self.make_io()
        self.assertEqual(main(["update", "--check", "--json"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "update")
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["target_version"], "9.9.9")
        self.assertEqual(payload["warnings"][0]["code"], "update_available")

    def test_update_runs_the_injected_installer(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")

        commands = []

        def run_update(command, cwd=None, env=None, check=False):
            commands.append({
                "command": command,
                "cwd": cwd,
                "env": env,
                "check": check,
            })
            return {"returncode": 0, "stdout": "", "stderr": ""}

        def run_version_check(command, **kwargs):
            return {"returncode": 0, "stdout": "9.9.9\n", "stderr": ""}

        list_io = self.make_io()
        self.assertEqual(main(["update", "--yes"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
            "runUpdate": run_update,
            "runVersionCheck": run_version_check,
        }), 0)

        self.assertEqual(commands[0]["command"], ["npm", "install", "-g", "cdx-manager@9.9.9"])
        self.assertIn("Updated cdx-manager to 9.9.9", list_io["stdout"].getvalue())

    def test_update_warns_when_path_resolves_old_version(self):
        temp_dir = self.make_temp_dir()
        bin_dir = os.path.join(temp_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        cdx_path = os.path.join(bin_dir, "cdx.cmd" if os.name == "nt" else "cdx")
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        with open(cdx_path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
        os.chmod(cdx_path, 0o755)

        def run_update(command, cwd=None, env=None, check=False):
            return {"returncode": 0, "stdout": "", "stderr": ""}

        def run_version_check(command, **kwargs):
            self.assertEqual(os.path.normcase(command[0]), os.path.normcase(cdx_path))
            self.assertEqual(command[1:], ["-v"])
            return {"returncode": 0, "stdout": "8.8.8\n", "stderr": ""}

        update_io = self.make_io()
        self.assertEqual(main(["update", "--yes", "--json"], {
            **update_io,
            "env": {"CDX_HOME": temp_dir, "PATH": bin_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
            "runUpdate": run_update,
            "runVersionCheck": run_version_check,
        }), 0)

        payload = json.loads(update_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["warnings"][0]["code"], "update_version_mismatch")
        self.assertEqual(os.path.normcase(payload["warnings"][0]["path"]), os.path.normcase(cdx_path))
        self.assertEqual(payload["warnings"][0]["resolved_version"], "8.8.8")

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

    def test_main_screen_next_actions_are_curated(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        lines = list_io["stdout"].getvalue().splitlines()
        start = lines.index("Next actions:") + 1
        self.assertEqual(lines[start:start + 10], [
            "  cdx status",
            "  cdx next",
            "  cdx configs",
            "  cdx stats",
            "  cdx ready",
            "  cdx perm all default",
            "  cdx handoff <source> <target>",
            "  cdx history",
            "  cdx help",
            "  cdx update",
        ])
        self.assertNotIn("  cdx add <name>", lines[start:])
        self.assertNotIn("  cdx login <name>", lines[start:])
        self.assertNotIn("  cdx handoff <name>", lines[start:])

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
        self.assertIn("Run: cdx update", output)
        self.assertNotIn("https://example.invalid/release", output)

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

    def test_context_commands_store_context_per_workspace(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)

        set_io = self.make_io()
        self.assertEqual(main(["context", "set", "Goal: ship handoff", "--json"], {
            **set_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        set_payload = json.loads(set_io["stdout"].getvalue())
        self.assertEqual(set_payload["action"], "context.set")
        self.assertTrue(set_payload["context"]["path"].endswith("context.md"))

        show_io = self.make_io()
        self.assertEqual(main(["context", "show"], {
            **show_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        self.assertIn("Goal: ship handoff", show_io["stdout"].getvalue())

        other_io = self.make_io()
        other_workspace = os.path.join(temp_dir, "other")
        os.makedirs(other_workspace)
        self.assertEqual(main(["context", "show"], {
            **other_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other_workspace,
        }), 0)
        self.assertIn("No shared context", other_io["stdout"].getvalue())

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
        with open(target_path, "r", encoding="utf-8") as handle:
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
        with open(payload["context"]["target_path"], "r", encoding="utf-8") as handle:
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
        with open(target_path, "r", encoding="utf-8") as handle:
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
        with open(payload["context"]["target_path"], "r", encoding="utf-8") as handle:
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
        with open(payload["context"]["target_path"], "r", encoding="utf-8") as handle:
            self.assertIn("Codex context for Claude", handle.read())

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
        self.assertEqual(payload["resume"]["strategy"], "provider_continue")
        resume_call = harness.calls[-1]
        self.assertEqual(resume_call["command"], "script")
        self.assertTrue(_script_launch_invokes(resume_call, "claude"))
        self.assertEqual(_script_launch_args(resume_call)[:3], ["--continue", "--name", "work"])

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

    def test_set_launch_settings_can_target_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"], ["add", "ollama", "local", "--model", "llama3.2"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "all", "--permission", "full", "--json"
        ], {
            **set_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(set_io["stdout"].getvalue())
        self.assertEqual(payload["updated_count"], 3)
        self.assertIsNone(payload["session"])
        self.assertEqual(
            {session["name"]: session["launch"]["permission"] for session in payload["sessions"]},
            {"main": "full", "work1": "full", "local": "full"},
        )

    def test_set_launch_settings_can_target_provider_or_named_subset(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "side"], ["add", "claude", "work1"], ["add", "ollama", "local", "--model", "llama3.2"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        provider_io = self.make_io()
        self.assertEqual(main([
            "set", "--provider", "codex", "--power", "low", "--json"
        ], {
            **provider_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        provider_payload = json.loads(provider_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in provider_payload["sessions"]], ["main", "side"])

        subset_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "work1,local", "--fast", "on", "--json"
        ], {
            **subset_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        subset_payload = json.loads(subset_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in subset_payload["sessions"]], ["work1", "local"])
        self.assertTrue(all(session["launch"]["fast"] for session in subset_payload["sessions"]))

    def test_set_launch_priority_affects_headless_selection_tie_breaker(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("alpha", "codex")
        service["create_session"]("beta", "codex")
        for name in ("alpha", "beta"):
            service["update_auth_state"](name, lambda auth: {**auth, "status": "authenticated"})
            service["record_status"](name, {"remaining_5h_pct": 80, "remaining_week_pct": 80})

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "beta", "--priority", "50", "--json"
        ], {**set_io, "service": service}), 0)
        self.assertEqual(json.loads(set_io["stdout"].getvalue())["launch"]["priority"], 50)

        select_io = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--require-ready", "--json"
        ], {**select_io, "service": service}), 0)

        payload = json.loads(select_io["stdout"].getvalue())
        self.assertEqual(payload["session"], "beta")

    def test_set_launch_rtk_preference_can_be_unset(self):
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
            "set", "main", "--rtk", "on", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertTrue(json.loads(set_io["stdout"].getvalue())["launch"]["rtk"])

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "main", "--rtk", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertNotIn("rtk", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_set_launch_logics_preference_can_be_unset(self):
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
            "set", "main", "--logics", "off", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertFalse(json.loads(set_io["stdout"].getvalue())["launch"]["logics"])

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "main", "--logics", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertNotIn("logics", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_logics_prompt_defaults_on_when_cli_is_detected_and_can_be_disabled(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        with mock.patch(
            "src.provider_runtime.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            self.assertEqual(main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertIn("logics-manager status", _script_launch_text(launch_call))
        self.assertIn("cdx view", _script_launch_text(launch_call))

        self.assertEqual(main(["set", "main", "--logics", "off"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        with mock.patch(
            "src.provider_runtime.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            self.assertEqual(main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertNotIn("logics-manager status", _script_launch_text(launch_call))

    def test_fast_on_enables_codex_service_tier_without_lowering_power(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "main,work1", "--fast", "on", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        payload = json.loads(set_io["stdout"].getvalue())
        self.assertTrue(all(
            session["launch"] == {"power": "medium", "fast": True, "fastMode": "service_tier"}
            for session in payload["sessions"]
        ))

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        codex_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        codex_text = _script_launch_text(codex_call)
        self.assertIn('model_reasoning_effort="medium"', codex_text)
        self.assertIn('service_tier="fast"', codex_text)
        self.assertIn("features.fast_mode=true", codex_text)

        self.assertEqual(main(["work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        claude_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        ][-1]
        self.assertIn("--effort", _script_launch_args(claude_call))
        self.assertIn("medium", _script_launch_args(claude_call))

        unset_io = self.make_io()
        self.assertEqual(main([
            "set", "main", "--fast", "off", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertEqual(json.loads(unset_io["stdout"].getvalue())["launch"], {"fast": False, "power": "medium"})

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

    def test_unset_launch_settings_can_target_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main([
            "set", "--sessions", "all", "--permission", "full"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "--sessions", "all", "--permission", "--json"
        ], {
            **unset_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(unset_io["stdout"].getvalue())
        self.assertEqual(payload["updated_count"], 2)
        self.assertTrue(all("permission" not in session["launch"] for session in payload["sessions"]))
        self.assertTrue(all(session["launch"]["power"] == "medium" for session in payload["sessions"]))
        self.assertTrue(all(session["launch"]["fast"] is False for session in payload["sessions"]))

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

    def test_last_launches_most_recent_existing_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        for name in ("first", "second"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main(["first"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["second"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        last_io = self.make_io()
        self.assertEqual(main(["last"], {
            **last_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        output = last_io["stdout"].getvalue()
        self.assertIn("Launching last session: second", output)
        self.assertIn("Launching codex session second", output)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertTrue(
            _script_transcript_path(launch_call).startswith(os.path.join(temp_dir, "profiles", "second", "log", "cdx-session-"))
        )

    def test_last_skips_removed_sessions_and_supports_json(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        for name in ("first", "second"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)
            self.assertEqual(main([name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main(["rmv", "second", "--force"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        last_io = self.make_io()
        self.assertEqual(main(["last", "--json"], {
            **last_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(last_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "launch")
        self.assertEqual(payload["session"]["name"], "first")

    def test_last_requires_launch_history(self):
        temp_dir = self.make_temp_dir()

        with self.assertRaisesRegex(CdxError, "No launch history yet"):
            main(["last"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_history_summary_filters_by_period(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        service["create_session"]("personal")
        now = datetime(2026, 5, 28, 12, 0, 0).astimezone()
        recent = now - timedelta(days=2)
        old = now - timedelta(days=10)
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 120000,
            "started_at": recent.isoformat(),
            "ended_at": (recent + timedelta(minutes=2)).isoformat(),
        })
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 300000,
            "started_at": old.isoformat(),
            "ended_at": (old + timedelta(minutes=5)).isoformat(),
        })
        service["record_launch_history"]("personal", {
            "status": "failed",
            "duration_ms": 60000,
            "started_at": recent.isoformat(),
            "ended_at": (recent + timedelta(minutes=1)).isoformat(),
        })

        summary_io = self.make_io()
        self.assertEqual(main(["history", "--summary", "--since", "7d", "--json"], {
            **summary_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: now.timestamp(),
        }), 0)
        payload = json.loads(summary_io["stdout"].getvalue())
        rows = {row["session_name"]: row for row in payload["summary"]}
        self.assertEqual(set(rows), {"work", "personal"})
        self.assertEqual(rows["work"]["duration_ms"], 120000)
        self.assertEqual(rows["personal"]["failures"], 1)
        self.assertIsNotNone(payload["period"]["from"])
        self.assertIsNone(payload["period"]["to"])

        text_io = self.make_io()
        self.assertEqual(main(["history", "--summary", "--from", recent.date().isoformat(), "--to", now.date().isoformat()], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: now.timestamp(),
        }), 0)
        output = text_io["stdout"].getvalue()
        self.assertIn("Period:", output)
        self.assertIn("work", output)
        self.assertNotIn("5m00s", output)

    def test_stats_aggregates_known_usage_by_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        service["create_session"]("personal")
        now = datetime(2026, 5, 28, 12, 0, 0).astimezone()
        recent = now - timedelta(days=1)
        old = now - timedelta(days=9)
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 7500000,
            "started_at": recent.isoformat(),
            "usage": {
                "input_tokens": 10,
                "output_tokens": 4,
                "reasoning_tokens": 2,
                "total_tokens": 14,
            },
        })
        service["record_launch_history"]("work", {
            "status": "failed",
            "duration_ms": 30000,
            "started_at": recent.isoformat(),
            "usage": {
                "input_tokens": 3,
                "output_tokens": 0,
                "total_tokens": 3,
            },
        })
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 60000,
            "started_at": old.isoformat(),
            "usage": {"total_tokens": 99},
        })
        service["record_launch_history"]("personal", {
            "status": "success",
            "duration_ms": 1000,
            "started_at": recent.isoformat(),
        })

        stats_io = self.make_io()
        self.assertEqual(main(["stats", "--since", "7d", "--json"], {
            **stats_io,
            "service": service,
            "now": lambda: now.timestamp(),
        }), 0)

        payload = json.loads(stats_io["stdout"].getvalue())
        rows = {row["session_name"]: row for row in payload["stats"]}
        self.assertEqual(rows["work"]["launches"], 2)
        self.assertEqual(rows["work"]["failures"], 1)
        self.assertEqual(rows["work"]["usage_runs"], 2)
        self.assertEqual(rows["work"]["input_tokens"], 13)
        self.assertEqual(rows["work"]["output_tokens"], 4)
        self.assertEqual(rows["work"]["reasoning_tokens"], 2)
        self.assertEqual(rows["work"]["total_tokens"], 17)
        self.assertEqual(rows["personal"]["usage_runs"], 0)
        self.assertEqual(payload["totals"]["total_tokens"], 17)

        service["start_session_runtime"]("work", {"pid": os.getpid()})

        text_io = self.make_io()
        self.assertEqual(main(["stats", "work", "--since", "7d"], {
            **text_io,
            "service": service,
            "now": lambda: now.timestamp(),
        }), 0)
        output = text_io["stdout"].getvalue()
        self.assertIn("Assistant stats:", output)
        self.assertIn("work*", output)
        self.assertIn("2h 05m", output)
        self.assertIn("17 tokens", output)

        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["stats", "work", "--since", "7d"], {
            **color_io,
            "service": service,
            "env": {"CLICOLOR_FORCE": "1"},
            "now": lambda: now.timestamp(),
        }), 0)
        self.assertIn("\033[", color_io["stdout"].getvalue())

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

    def test_login_claude_does_not_logout_first(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main([
            "add", "claude", "work1"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir, "CODEX_HOME": "/tmp/codex", "CLAUDE_CONFIG_DIR": "/tmp/wrong"},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        harness.calls.clear()

        login_io = self.make_io()
        self.assertEqual(main([
            "login", "work1", "--json"
        ], {
            **login_io,
            "env": {"CDX_HOME": temp_dir, "CODEX_HOME": "/tmp/codex", "CLAUDE_CONFIG_DIR": "/tmp/wrong"},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        claude_spawns = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "claude"
        ]
        self.assertEqual([call["args"] for call in claude_spawns], [["auth", "login"]])
        self.assertEqual(
            claude_spawns[0]["options"]["env"]["ANTHROPIC_CONFIG_DIR"],
            os.path.join(temp_dir, "profiles", "work1", "claude-home"),
        )
        self.assertNotIn("CODEX_HOME", claude_spawns[0]["options"]["env"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", claude_spawns[0]["options"]["env"])

    def test_login_codex_does_not_logout_first_or_touch_other_account(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        for name in ("work1", "work2"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)
        harness.calls.clear()

        service = create_session_service({"base_dir": temp_dir})
        other = service["get_session"]("work2")
        other_auth = os.path.join(other["authHome"], "auth.json")
        with open(other_auth, "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "other-token"}}, handle)

        login_io = self.make_io()
        self.assertEqual(main(["login", "work1", "--json"], {
            **login_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        codex_spawns = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "codex"
        ]
        self.assertEqual([call["args"] for call in codex_spawns], [["login"]])
        self.assertTrue(os.path.exists(other_auth))
        with open(other_auth, "r", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tokens"]["access_token"], "other-token")

    def test_login_claude_falls_back_to_setup_token(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness(claude_login_authenticates=False)

        self.assertEqual(main([
            "add", "claude", "work1"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        harness.calls.clear()

        login_io = self.make_io()
        self.assertEqual(main([
            "login", "work1", "--json"
        ], {
            **login_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        script_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        )
        self.assertEqual(_script_launch_args(script_call), ["setup-token"])
        cred_path = os.path.join(temp_dir, "profiles", "work1", "claude-home", "credentials", "default.json")
        with open(cred_path, "r", encoding="utf-8") as handle:
            credentials = json.load(handle)
        self.assertEqual(credentials["access_token"], "sk-ant-oat-test")
        self.assertFalse(os.path.exists(_script_transcript_path(script_call)))

    def test_login_claude_keeps_setup_token_transcript_when_extraction_fails(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness(
            claude_login_authenticates=False,
            claude_setup_token_text="Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=<token>\n",
        )

        self.assertEqual(main(["add", "claude", "work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        harness.calls.clear()

        with self.assertRaisesRegex(CdxError, "Transcript kept at"):
            main(["login", "work1"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })

        script_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        )
        self.assertTrue(os.path.exists(_script_transcript_path(script_call)))

    def test_claude_setup_token_extraction_strips_ansi_sequences(self):
        token = _extract_claude_oauth_token(
            "export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat-test\x1b[39m\n"
        )

        self.assertEqual(token, "sk-ant-oat-test")

    def test_claude_setup_token_extraction_skips_placeholder_hint(self):
        token = _extract_claude_oauth_token("\n".join([
            "Your OAuth token (valid for 1 year):",
            "sk-ant-oat01-real-token",
            "Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=<token>",
        ]))

        self.assertEqual(token, "sk-ant-oat01-real-token")

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
            _script_launch_args(launch_call)[:3],
            ["run", "llama3.2", "--experimental-yolo"],
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
            "Set a value: cdx set work1 --power medium --permission auto --fast on --rtk on --logics on --model MODEL --priority 80",
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
        self.assertEqual(
            _script_launch_args(launch_call)[:8],
            ["--name", "work1", "--model", "sonnet", "--effort", "high", "--permission-mode", "plan"],
        )

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

    def test_configs_lists_all_launch_settings_in_table(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "work"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["add", "claude", "personal"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["set", "work", "--power", "high", "--permission", "auto", "--fast", "off", "--rtk", "on", "--priority", "80"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        configs_io = self.make_io()
        self.assertEqual(main(["configs"], {
            **configs_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = configs_io["stdout"].getvalue()
        self.assertIn("Launch settings:", output)
        self.assertIn("SESSION", output)
        self.assertIn("PROVIDER", output)
        self.assertIn("POWER", output)
        self.assertIn("PERMISSION", output)
        self.assertIn("FAST", output)
        self.assertIn("RTK", output)
        self.assertIn("PRIORITY", output)
        self.assertIn("work", output)
        self.assertIn("codex", output)
        self.assertIn("high", output)
        self.assertIn("auto", output)
        self.assertIn("off", output)
        self.assertIn("on", output)
        self.assertIn("80", output)
        self.assertIn("personal", output)
        self.assertIn("default", output)
        self.assertIn(
            "Set a value: cdx set <name> --power medium --permission auto --fast on --rtk on --logics on --model MODEL --priority 80",
            output,
        )

    def test_configs_json_lists_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "work"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["set", "work", "--power", "medium"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        configs_io = self.make_io()
        self.assertEqual(main(["configs", "--json"], {
            **configs_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(configs_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "configs")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["sessions"][0]["name"], "work")
        self.assertEqual(payload["sessions"][0]["launch"]["power"], "medium")

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

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
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

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_with_auth_reports_progress_and_summary(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        auth_path = os.path.join(temp_dir, "profiles", "main", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')

        export_path = os.path.join(temp_dir, "secure.cdx")
        export_io = self.make_io()
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-env", "CDX_BUNDLE_PASSPHRASE",
        ], {
            **export_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)

        output = export_io["stdout"].getvalue()
        self.assertIn("Exporting 1 session(s) with auth...", output)
        self.assertIn("Collecting main...", output)
        self.assertIn("Encoding and encrypting bundle...", output)
        self.assertIn("Writing ", output)
        self.assertIn("Exported 1 session with auth to", output)
        self.assertIn(f"Path: {export_path}", output)
        self.assertIn("Auth: included and encrypted", output)
        self.assertRegex(output, r"Auth files: [1-9]\d*")
        self.assertIn("Auth data: ", output)
        self.assertIn("Bundle size: ", output)

    def test_export_import_parsers_support_equals_flags_and_session_subset(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["create_session"]("side")
        export_path = os.path.join(temp_dir, "subset.cdx")

        export_io = self.make_io()
        self.assertEqual(main([
            "export",
            export_path,
            "--sessions=side",
            "--json",
        ], {
            **export_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertEqual(export_payload["bundle"]["session_names"], ["side"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main([
            "import",
            export_path,
            "--sessions=side",
            "--json",
        ], {
            **import_io,
            "env": {"CDX_HOME": import_dir},
        }), 0)

        imported_service = create_session_service({"base_dir": import_dir})
        self.assertIsNone(imported_service["get_session"]("main"))
        self.assertEqual(imported_service["get_session"]("side")["name"], "side")

    def test_clean_reports_sessions_with_and_without_logs(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("withlog")
        service["create_session"]("nolog")
        log_path = os.path.join(temp_dir, "profiles", "withlog", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("status transcript")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "--json"], {
            **clean_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        by_name = {item["session_name"]: item for item in payload["sessions"]}
        self.assertTrue(by_name["withlog"]["cleared"])
        self.assertEqual(by_name["withlog"]["files_cleared"], 1)
        self.assertFalse(by_name["nolog"]["cleared"])
        self.assertEqual(os.path.getsize(log_path), 0)

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

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
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

    def test_import_rejects_corrupted_bundle(self):
        temp_dir = self.make_temp_dir()
        bundle_path = os.path.join(temp_dir, "corrupt.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(b"not a cdx bundle")

        with self.assertRaisesRegex(CdxError, "Invalid bundle"):
            main(["import", bundle_path, "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_import_rejects_force_and_merge_together(self):
        temp_dir = self.make_temp_dir()
        bundle_path = os.path.join(temp_dir, "backup.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(b"placeholder")

        with self.assertRaisesRegex(CdxError, "mutually exclusive"):
            main(["import", bundle_path, "--force", "--merge"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_update_parser_supports_schema_flags(self):
        temp_dir = self.make_temp_dir()
        update_io = self.make_io()

        self.assertEqual(main(["update", "--check", "--json"], {
            **update_io,
            "env": {"CDX_HOME": temp_dir},
            "version": "1.0.0",
            "fetchLatestRelease": lambda: {"latest_version": "1.0.0", "url": "https://example.test"},
        }), 0)
        payload = json.loads(update_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "update")
        self.assertTrue(payload["checked"])

        with self.assertRaisesRegex(CdxError, "cannot be combined"):
            main(["update", "--check", "--version=1.2.3"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_status_parser_rejects_small_detail_and_supports_refresh(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "Usage: cdx status"):
            main(["status", "main", "-s"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh", "--json"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertEqual(json.loads(status_io["stdout"].getvalue())["action"], "status")

    def test_repair_parser_rejects_unknown_flags(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        with self.assertRaisesRegex(CdxError, "Usage: cdx repair"):
            main(["repair", "--bad"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
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

    def test_status_text_shows_progress_but_json_stays_clean(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["launch_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertIn("Resolving status for 1 session(s)...", output)
        self.assertIn("Checking main (codex)...", output)
        self.assertIn("Checked main (1/1).", output)
        self.assertIn("Resolved 1 status row(s).", output)
        self.assertIn("Current: last launched main (just now).", output)

        json_io = self.make_io()
        self.assertEqual(main(["status", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "status")
        self.assertIsNotNone(payload["rows"][0]["last_launched_at"])
        self.assertNotIn("Resolving status", json_io["stdout"].getvalue())

    def test_status_surfaces_update_notice_at_end(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        lines = [line for line in status_io["stdout"].getvalue().splitlines() if line]
        self.assertTrue(lines[-1].startswith("Update available: cdx-manager 9.9.9"))
        self.assertIn("Run: cdx update", lines[-1])
        self.assertNotIn("https://example.invalid/release", lines[-1])

    def test_status_json_includes_update_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--json"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "update_available")
        self.assertEqual(payload["warnings"][0]["latest_version"], "9.9.9")

    def test_status_and_list_mark_active_session_with_star(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["start_session_runtime"]("main", {"pid": os.getpid()})
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertRegex(list_io["stdout"].getvalue(), r"main\*\s+enabled")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertRegex(status_io["stdout"].getvalue(), r"main\*\s+enabled")

    def test_status_cached_rows_do_not_show_session_checking_progress(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(_session):
            calls.append("fetch")
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")

        first_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **first_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Checking main (codex)...", first_io["stdout"].getvalue())
        self.assertIn("Checked main (1/1).", first_io["stdout"].getvalue())

        second_io = self.make_io()
        self.assertEqual(main(["status"], {
            **second_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertNotIn("Checking main (codex)...", second_io["stdout"].getvalue())
        self.assertNotIn("Checked main", second_io["stdout"].getvalue())
        self.assertEqual(len(calls), 1)

    def test_status_cached_claude_rows_do_not_show_checking_progress_within_refresh_ttl(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": (datetime.now().astimezone() - timedelta(minutes=2)).isoformat(),
        })

        def refresh(_session):
            raise AssertionError("Claude cache inside refresh TTL should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertNotIn("Checking claude (claude)...", output)
        self.assertIn("60%", output)

    def test_status_disabled_claude_rows_do_not_show_checking_progress(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["set_session_enabled"]("claude", False)
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        def refresh(_session):
            raise AssertionError("disabled Claude sessions should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertNotIn("Checking claude (claude)...", output)
        self.assertIn("disabled", output)
        self.assertNotIn("80%", output)
        self.assertNotIn("60%", output)
        self.assertRegex(output, r"claude\s+disabled\s+-\s+-\s+-")

    def test_status_reports_no_current_session_when_none_launched(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Current: no launched session known yet.", status_io["stdout"].getvalue())

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

    def test_status_keeps_claude_auth_after_invalid_usage_auth_when_probe_succeeds(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def refresh(_session):
            from src.claude_usage import ClaudeAuthInvalidError

            raise ClaudeAuthInvalidError("Claude usage unavailable (HTTP 401: Invalid authentication credentials)")

        status_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--json", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness(initial_auth={
                service["get_session"]("claude")["authHome"]: True,
            }).spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["code"], "claude_refresh_failed")
        self.assertEqual(payload["warnings"][0]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["status_freshness"], "stale")
        self.assertIn("local Claude auth is still valid", payload["warnings"][0]["message"])

        text_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--refresh"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness(initial_auth={
                service["get_session"]("claude")["authHome"]: True,
            }).spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn(
            "Warning: Claude quota refresh failed for claude, but local auth is still valid; cached quota may be stale.",
            text_io["stdout"].getvalue(),
        )

    def test_status_rechecks_claude_auth_before_usage_refresh(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def refresh(_session):
            raise AssertionError("logged out Claude sessions should not refresh usage")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness().spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["auth_status"], "logged_out")
        self.assertIn("logged out", status_io["stdout"].getvalue())

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
        header = next(line for line in output.splitlines() if line.startswith("SESSION"))
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
            "remaining_5h_pct": -10,
            "remaining_week_pct": 95,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["create_session"]("secondary")
        service["record_status"]("secondary", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["status"], {
            **color_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        color_output = color_io["stdout"].getvalue()
        self.assertIn("\033[", color_output)
        self.assertIn("\033[31m0%\033[0m", color_output)
        self.assertIn("\033[32m80%\033[0m", color_output)
        self.assertIn("\033[96m95%\033[0m", color_output)

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

    def test_next_uses_same_priority_recommendation_as_status(self):
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

        next_io = self.make_io()
        self.assertEqual(main(["next"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = next_io["stdout"].getvalue()
        self.assertIn("Next assistant:", output)
        self.assertIn("regular", output)
        self.assertIn("use regular first (80% OK)", output)
        self.assertIn("Run: cdx regular", output)

        json_io = self.make_io()
        self.assertEqual(main(["next", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "next")
        self.assertEqual(payload["recommended_action"], "use")
        self.assertEqual(payload["session"]["name"], "regular")
        self.assertEqual(payload["command"], "cdx regular")
        self.assertEqual(payload["selection_policy"], "status_priority")

    def test_next_reports_no_suitable_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        next_io = self.make_io()
        self.assertEqual(main(["next", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 1)
        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "no_suitable_session")

    def test_status_treats_five_percent_available_as_empty_for_priority(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("low")
        service["create_session"]("usable")
        service["record_status"]("low", {
            "remaining_5h_pct": 5,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("usable", {
            "remaining_5h_pct": 6,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = status_io["stdout"].getvalue()
        self.assertIn("low", output)
        self.assertIn("5%", output)
        self.assertIn(
            "Priority: use usable first (6% OK), next low (0% OK).",
            output,
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

    def test_status_detail_refreshes_only_named_session(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(session):
            calls.append(session["name"])
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")
        service["create_session"]("work1")
        service["create_session"]("work2")

        detail_io = self.make_io()
        self.assertEqual(main(["status", "work1", "--json", "--refresh"], {
            **detail_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(detail_io["stdout"].getvalue())
        self.assertEqual(calls, ["work1"])
        self.assertEqual(payload["session"]["session_name"], "work1")
        self.assertEqual(payload["session"]["available_pct"], 70)

    def test_status_cached_skips_provider_refresh(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(session):
            calls.append(session["name"])
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 33,
            "remaining_week_pct": 66,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--json", "--cached"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(calls, [])
        self.assertEqual(payload["rows"][0]["session_name"], "main")
        self.assertEqual(payload["rows"][0]["available_pct"], 33)

    def test_status_timeout_flag_applies_to_codex_fetch(self):
        temp_dir = self.make_temp_dir()
        with mock.patch("src.session_service.fetch_codex_rate_limits", return_value={
            "remaining_5h_pct": 80,
            "remaining_week_pct": 70,
            "updated_at": datetime.now().astimezone().isoformat(),
        }) as fetch_status:
            service = create_session_service({"base_dir": temp_dir})
            service["create_session"]("main")

            status_io = self.make_io()
            self.assertEqual(main(["status", "main", "--json", "--refresh", "--timeout", "0.5"], {
                **status_io,
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["available_pct"], 70)
        self.assertEqual(fetch_status.call_args.kwargs["timeout"], 0.5)

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
        with self.assertRaises(CdxError) as refresh_cached_ctx:
            main(["status", "--refresh", "--cached"], self.make_io())
        self.assertIn("cdx status [--json]", str(refresh_cached_ctx.exception))
        with self.assertRaises(CdxError) as timeout_ctx:
            main(["status", "--timeout", "0"], self.make_io())
        self.assertIn("--timeout SECONDS", str(timeout_ctx.exception))

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

        class ProbeError(Exception):
            def __str__(self):
                return "boom"

        def bad_spawn_sync(_command, _args, _spec):
            return {"error": ProbeError()}

        with mock.patch("src.session_service._get_global_codex_home", return_value=temp_dir):
            service["create_session"]("main")
            with self.assertRaises(CdxError) as ctx:
                main(["main"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir},
                    "service": service,
                    "spawn_sync": bad_spawn_sync,
                    "spawn": lambda argv, **kwargs: _Child(),
                })
        self.assertIn("Failed to check login status", str(ctx.exception))

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

    def test_doctor_reports_codex_auth_diagnostic_without_tokens(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        session = service["create_session"]("main")
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "secret-token"}}, handle)
        harness = _AuthHarness(initial_auth={session["authHome"]: True})

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        auth_file = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_auth_file")
        live_auth = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_live_auth")
        self.assertTrue(auth_file["detail"]["auth_json_exists"])
        self.assertTrue(auth_file["detail"]["local_tokens_present"])
        self.assertEqual(live_auth["detail"]["live_status"], "authenticated")
        self.assertNotIn("secret-token", json.dumps(payload))

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

    def test_doctor_reports_rtk_availability(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch("src.health.shutil.which", side_effect=lambda command, path=None: "/usr/bin/rtk" if command == "rtk" else None):
            report = collect_health_report(service, temp_dir, env={"PATH": "/usr/bin"})

        issue = next(item for item in report["issues"] if item["code"] == "rtk_cli")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"], "/usr/bin/rtk")

    def test_doctor_reports_logics_manager_availability(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch(
            "src.health.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            report = collect_health_report(service, temp_dir, env={"PATH": "/usr/bin"})

        issue = next(item for item in report["issues"] if item["code"] == "logics_manager_cli")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"], "/usr/bin/logics-manager")

    def test_view_delegates_to_logics_manager_from_current_cwd(self):
        temp_dir = self.make_temp_dir()
        cwd = self.make_temp_dir()
        calls = []

        def run_view(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "cwd": cwd,
                "spawn_sync": run_view,
                "checkLogicsManagerForUpdate": lambda *_args, **_kwargs: None,
            }), 0)

        self.assertEqual(calls[0][0], ["/usr/bin/logics-manager", "view"])
        self.assertEqual(calls[0][1]["cwd"], cwd)

    def test_view_ctrl_c_exits_cleanly_without_traceback(self):
        temp_dir = self.make_temp_dir()

        def interrupted(_argv, **_kwargs):
            raise KeyboardInterrupt()

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "cwd": temp_dir,
                "spawn_sync": interrupted,
                "checkLogicsManagerForUpdate": lambda *_args, **_kwargs: None,
            }), 130)

        self.assertEqual(io_obj["stdout"].getvalue(), "\n")
        self.assertEqual(io_obj["stderr"].getvalue(), "")

    def test_view_missing_logics_manager_is_actionable(self):
        temp_dir = self.make_temp_dir()

        with mock.patch("src.logics_view.shutil.which", return_value=None):
            with self.assertRaisesRegex(CdxError, "npm install -g @grifhinz/logics-manager"):
                main(["view"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir, "PATH": ""},
                })

    def test_view_json_reports_availability_without_opening_viewer(self):
        temp_dir = self.make_temp_dir()
        calls = []

        with mock.patch("src.logics_view.shutil.which", return_value=None):
            io_obj = self.make_io()
            self.assertEqual(main(["view", "--json"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": ""},
                "spawn_sync": lambda *args, **kwargs: calls.append((args, kwargs)),
            }), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "view")
        self.assertFalse(payload["viewer"]["available"])
        self.assertEqual(payload["viewer"]["command"], ["logics-manager", "view"])
        self.assertEqual(payload["viewer"]["failure"]["code"], "logics_manager_missing")
        self.assertEqual(calls, [])

    def test_view_json_includes_logics_manager_update_suggestion(self):
        temp_dir = self.make_temp_dir()

        def update_notice(*_args, **_kwargs):
            return {
                "tool": "logics-manager",
                "latest_version": "9.9.9",
                "current_version": "1.0.0",
                "update_command": "logics-manager self-update",
                "url": "https://example.invalid/logics-manager",
            }

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view", "--json"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "checkLogicsManagerForUpdate": update_notice,
            }), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["viewer"]["available"])
        self.assertEqual(payload["viewer"]["update"]["latest_version"], "9.9.9")
        self.assertEqual(payload["warnings"][0]["update_command"], "logics-manager self-update")

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
        self.assertIn("Checking notification target: main", notify_io["stdout"].getvalue())
        self.assertIn("Loading status for 1 session(s)", notify_io["stdout"].getvalue())
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
        self.assertEqual(payload["event"]["session"], "main")
        self.assertNotIn("Checking notification target", next_io["stdout"].getvalue())

    def test_notify_next_ready_ignores_currently_available_sessions(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("active")
        service["record_status"]("active", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:01:00+00:00",
        })

        next_io = self.make_io()
        self.assertEqual(main(["notify", "--next-ready", "--once", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        }), 0)

        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["event"]["ready"])
        self.assertIsNone(payload["event"]["session"])
        self.assertEqual(payload["event"]["message"], "No upcoming session reset available")

    def test_notify_schedule_next_ready_registers_os_job(self):
        temp_dir = self.make_temp_dir()
        reset = datetime.now().astimezone() + timedelta(minutes=30)
        service = {
            "base_dir": temp_dir,
            "get_status_rows": lambda **_kwargs: [{
                "session_name": "main",
                "provider": "codex",
                "enabled": True,
                "status": "enabled",
                "remaining_5h_pct": 0,
                "remaining_week_pct": 20,
                "reset_5h_at": reset.isoformat(),
                "updated_at": datetime.now().astimezone().isoformat(),
            }],
        }
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", side_effect=lambda command, _env: command == "systemd-run"):
                notify_io = self.make_io()
                self.assertEqual(main(["notify", "--next-ready", "--schedule", "--json"], {
                    **notify_io,
                    "service": service,
                    "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                    "spawn_sync": spawn_sync,
                }), 0)

        payload = json.loads(notify_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "notify")
        self.assertTrue(payload["schedule"]["scheduled"])
        self.assertEqual(payload["schedule"]["backend"], "systemd")
        self.assertEqual(payload["event"]["session"], "main")
        self.assertEqual(calls[0][0][0], "systemd-run")

    def test_ready_schedules_next_ready_notification(self):
        temp_dir = self.make_temp_dir()
        reset = datetime.now().astimezone() + timedelta(minutes=30)
        service = {
            "base_dir": temp_dir,
            "get_status_rows": lambda **_kwargs: [{
                "session_name": "main",
                "provider": "codex",
                "enabled": True,
                "status": "enabled",
                "remaining_5h_pct": 0,
                "remaining_week_pct": 20,
                "reset_5h_at": reset.isoformat(),
                "updated_at": datetime.now().astimezone().isoformat(),
            }],
        }
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil_which", side_effect=lambda command, _env: command == "systemd-run"):
                ready_io = self.make_io()
                self.assertEqual(main(["ready", "--json"], {
                    **ready_io,
                    "service": service,
                    "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                    "spawn_sync": spawn_sync,
                }), 0)

        payload = json.loads(ready_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "notify")
        self.assertTrue(payload["schedule"]["scheduled"])
        self.assertEqual(payload["event"]["session"], "main")
        self.assertEqual(calls[0][0][0], "systemd-run")

    def test_ready_rejects_notify_only_options(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx ready"):
            main(["ready", "--once"], self.make_io())

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
        self.assertEqual(payload["reason"], "highest availability suitable session")
        self.assertEqual(payload["selection_policy"], "ready_then_cooldown_then_health_then_priority_then_name")

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
        self.assertEqual(payload["error"]["code"], "invalid_reasoning_effort")

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

    def test_notify_next_ready_ignores_disabled_sessions(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("disabled")
        service["create_session"]("blocked")
        service["set_session_enabled"]("disabled", False)
        reset = datetime.now().astimezone() + timedelta(minutes=5)
        service["record_status"]("disabled", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 0,
            "reset_5h_at": (datetime.now().astimezone() - timedelta(minutes=1)).isoformat(),
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("blocked", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 80,
            "reset_5h_at": reset.isoformat(),
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        next_io = self.make_io()
        self.assertEqual(main(["notify", "--next-ready", "--once", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        }), 0)

        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["event"]["ready"])
        self.assertEqual(payload["event"]["session"], "blocked")
        self.assertEqual(payload["event"]["message"], "Waiting for blocked")

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
