import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from src import provider_runtime
from src.cli import (
    _format_blocking_quota,
    _format_reset_time,
    _format_status_detail,
    _format_status_rows,
    _get_disk_cleanup_notice,
    _pad_table,
    _visible_len,
    format_json_error,
    main,
)
from src.cli_args import (
    RUN_EFFORT_VALUES,
    RUN_PERMISSION_ALIASES,
    RUN_PERMISSION_CANONICAL_VALUES,
    RUN_USAGE,
    _parse_run_args,
)
from src.cli_commands import _extract_claude_oauth_token, _format_update_all, _format_update_all_result
from src.errors import CdxError
from src.health import collect_health_report
from src.run_registry import RunRegistry
from src.session_ranking import RANKING_FACTORS
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
        if command == "codex" and args == ["--version"]:
            return {"stdout": "codex 0.145.0\n", "stderr": ""}
        if command == "claude" and args[:2] == ["auth", "status"]:
            logged_in = "true" if authed else "false"
            auth_method = "oauth" if authed else "none"
            text = f'{{"loggedIn": {logged_in}, "authMethod": "{auth_method}"}}\n'
            return {"stdout": text, "stderr": ""}
        if command == "claude" and args == ["--version"]:
            return {"stdout": "Claude Code 2.1.219\n", "stderr": ""}
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
    if args[:2] == ["-q", "-f"] and args[2:3] == ["-c"]:
        return args[3]
    return " ".join(shlex.quote(arg) for arg in args[3:])


def _script_launch_invokes(call, command):
    text = _script_launch_text(call)
    return text == command or text.startswith(f"{command} ")


def _script_launch_args(call):
    args = call["args"]
    if args[:2] == ["-q", "-f"] and args[2:3] == ["-c"]:
        return shlex.split(args[3])[1:]
    return args[4:]


def _script_transcript_path(call):
    args = call["args"]
    if args[:2] == ["-q", "-f"] and args[2:3] == ["-c"]:
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

    def test_update_all_format_is_scannable_and_colored(self):
        plan = {
            "items": [{"name": "codex", "version": "1.0.0", "latest_version": "1.1.0", "status": "update_available"}],
            "setup": {"rtk_missing_sessions": ["main"], "ponytail": [{"session": "main", "status": "up_to_date"}]},
            "steps": [{"name": "codex"}],
        }
        plain = _format_update_all(plan)
        colored = _format_update_all(plan, use_color=True)
        self.assertIn("Inventory only", plain)
        self.assertIn("CURRENT", plain)
        self.assertIn("Session setup", plain)
        self.assertIn("1 action(s) ready", plain)
        self.assertIn("\033[", colored)

    def test_update_all_failure_includes_its_reason(self):
        text = _format_update_all_result({"name": "Claude Code", "command": ["brew", "upgrade", "--cask", "claude-code@latest"], "returncode": 1, "stderr": "network unavailable"})
        self.assertIn("exit 1", text)
        self.assertIn("network unavailable", text)
        self.assertIn("claude-code@latest", text)
        self.assertIn("blocked by marketplace", _format_update_all_result({"name": "install", "skipped": True, "blocked_by": "marketplace"}))

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
                "reset_credits_available": 1,
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

        self.assertIn("Recommended: use loggedin first", output)
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
        # Ties break on session name ascending ("agy" before "local"). The old
        # recommendation ranking sorted names descending as a side effect of
        # reversing the whole sort tuple, disagreeing with the headless
        # ranking; the unified rule keeps the ascending order.
        self.assertRegex(lines[1], r"\bantigravity\s+enabled\s+n/a\b")
        self.assertRegex(lines[2], r"\bollama\s+enabled\s+n/a\b")

    def test_status_small_hides_metadata_columns(self):
        rows = [
            {
                "session_name": "main",
                "label": "work",
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
        self.assertIn("RESETS", header)
        self.assertNotIn("LABEL", header)
        self.assertNotIn("PROV.", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        self.assertNotIn("UPDATED", header)
        self.assertIn("Recommended:", output)
        self.assertIn("Current:", output)
        self.assertNotIn("Tip:", output)

    def test_status_full_shows_label_column_only_when_present(self):
        rows = [
            {
                "session_name": "main",
                "label": "work",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 80,
                "remaining_5h_pct": 80,
                "remaining_week_pct": 80,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "side",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 70,
                "remaining_5h_pct": 70,
                "remaining_week_pct": 70,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ]

        output = _format_status_rows(rows)
        self.assertIn("LABEL", output.splitlines()[0])
        self.assertRegex(output, r"\bmain\s+work\s+enabled\b")
        self.assertRegex(output, r"\bside\s+-\s+enabled\b")

        no_label = _format_status_rows([{**row, "label": None} for row in rows])
        self.assertNotIn("LABEL", no_label.splitlines()[0])

    def test_status_detail_shows_banked_reset_expiry(self):
        output = _format_status_detail({
            "session_name": "main",
            "provider": "codex",
            "reset_credits_available": 1,
            "reset_credits": [{"expires_at": "2099-07-20T10:00:00+00:00"}],
        })

        self.assertIn("Bonus resets: 1", output)
        self.assertIn("Reset expiry:", output)

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
        self.assertIn("cdx update [all] [--check] [--yes] [--json] [--version TAG]", help_io["stdout"].getvalue())
        self.assertIn("cdx ready [--refresh] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx doctor [--severity OK|WARN|FAIL[,OK|WARN|FAIL...]] [--check-provider-flags] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx next [--json] [--refresh]", help_io["stdout"].getvalue())
        self.assertIn("cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b>", help_io["stdout"].getvalue())
        self.assertIn("cdx stats [name]", help_io["stdout"].getvalue())
        self.assertIn("cdx disk [profiles] [--candidates] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx clean profiles (--tmp|--old-logs DAYS) [--yes] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx reset <name> [--yes] [--json]", help_io["stdout"].getvalue())
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
        self.assertIn("--kind assistant|code-review", help_io["stdout"].getvalue())

        self.assertEqual(main(["-v"], version_io), 0)
        self.assertRegex(version_io["stdout"].getvalue().strip(), r"^\d+\.\d+\.\d+$")

    def test_disk_reports_cdx_home_size(self):
        temp_dir = self.make_temp_dir()
        disk_io = self.make_io()

        self.assertEqual(main(["disk"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1536\t{temp_dir}\n",
        }), 0)

        self.assertEqual(disk_io["stdout"].getvalue().splitlines(), [
            "CDX home",
            f"Path:  {temp_dir}",
            "Total: 1.5 MB",
        ])

    def test_disk_json_reports_cdx_home_size(self):
        temp_dir = self.make_temp_dir()
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"2048\t{temp_dir}\n",
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "disk")
        self.assertEqual(payload["disk"]["target"], "home")
        self.assertEqual(payload["disk"]["path"], temp_dir)
        self.assertEqual(payload["disk"]["bytes"], 2097152)
        self.assertEqual(payload["disk"]["size"], "2 MB")

    def test_disk_profiles_reports_profiles_size(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        os.makedirs(profiles_dir)
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"4096\t{profiles_dir}\n",
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        self.assertEqual(payload["disk"]["target"], "profiles")
        self.assertEqual(payload["disk"]["path"], profiles_dir)
        self.assertEqual(payload["disk"]["bytes"], 4194304)
        self.assertEqual(payload["disk"]["size"], "4 MB")

    def test_disk_profiles_prints_profile_breakdown(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        main_dir = os.path.join(profiles_dir, "main")
        work_dir = os.path.join(profiles_dir, "work")
        os.makedirs(main_dir)
        os.makedirs(work_dir)
        sizes = {
            profiles_dir: "4096",
            main_dir: "3072",
            work_dir: "1024",
        }
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"{sizes[argv[2]]}\t{argv[2]}\n",
        }), 0)

        output = disk_io["stdout"].getvalue()
        self.assertIn("CDX profiles", output)
        self.assertIn(f"Path:  {profiles_dir}", output)
        self.assertIn("Total: 4 MB", output)
        self.assertIn("PROFILE  SIZE  SHARE", output)
        self.assertRegex(output, r"main\s+3 MB\s+75\.0%")
        self.assertRegex(output, r"work\s+1 MB\s+25\.0%")

    def test_disk_profiles_reports_progress_on_interactive_stderr(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        profile_dir = os.path.join(profiles_dir, "main")
        os.makedirs(profile_dir)
        disk_io = {**self.make_io(), "stderr": _TtyStream()}

        self.assertEqual(main(["disk", "profiles"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1\t{argv[2]}\n",
        }), 0)

        progress = disk_io["stderr"].getvalue()
        self.assertIn("Measuring CDX profiles disk usage", progress)
        self.assertIn("Measuring profile main (1/1)", progress)

    def test_disk_json_keeps_interactive_stderr_empty(self):
        temp_dir = self.make_temp_dir()
        disk_io = {**self.make_io(), "stderr": _TtyStream()}

        self.assertEqual(main(["disk", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1\t{argv[2]}\n",
        }), 0)

        self.assertEqual(disk_io["stderr"].getvalue(), "")

    def test_disk_candidates_rejects_home_before_scanning(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx disk"):
            main(["disk", "--candidates"], {
                **self.make_io(),
                "env": {"CDX_HOME": self.make_temp_dir()},
                "diskUsageRunner": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not scan")),
            })

    def test_disk_profiles_candidates_report_cleanup_evidence(self):
        temp_dir = self.make_temp_dir()
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        clone_dir = os.path.join(profile_dir, ".tmp", "plugins-clone-test")
        log_dir = os.path.join(profile_dir, "log")
        os.makedirs(marketplace_dir)
        os.makedirs(clone_dir)
        os.makedirs(log_dir)
        for path in (
            os.path.join(marketplace_dir, "cache.bin"),
            os.path.join(clone_dir, "clone.bin"),
            os.path.join(log_dir, "old.log"),
        ):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)
        os.utime(os.path.join(log_dir, "old.log"), (1000, 1000))

        disk_io = self.make_io()
        self.assertEqual(main(["disk", "profiles", "--candidates", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        candidates = payload["disk"]["candidates"]
        self.assertEqual({item["kind"] for item in candidates}, {"tmp-marketplaces", "tmp-plugin-clone", "old-logs-30d"})
        old_logs = next(item for item in candidates if item["kind"] == "old-logs-30d")
        self.assertEqual(old_logs["risk"], "review")
        self.assertEqual(old_logs["evidence"]["file_count"], 1)

    def test_disk_profiles_candidates_prints_aligned_report(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        with open(os.path.join(marketplace_dir, "cache.bin"), "wb") as handle:
            handle.write(b"x")
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles", "--candidates"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1024\t{argv[2]}\n",
        }), 0)

        output = disk_io["stdout"].getvalue()
        self.assertRegex(output, r"PROFILE\s+SIZE\s+SHARE\s+RECLAIMABLE")
        self.assertIn("Cleanup candidates", output)
        self.assertIn("SIZE  TYPE", output)
        self.assertIn("RISK  EVIDENCE", output)
        self.assertRegex(output, r"1 MB\s+tmp-marketplaces\s+safe\s+temporary marketplace cache/staging")

    def test_clean_profiles_tmp_removes_temporary_candidates(self):
        temp_dir = self.make_temp_dir()
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        backup_dir = os.path.join(profile_dir, ".tmp", "plugins-backup-test")
        os.makedirs(marketplace_dir)
        os.makedirs(backup_dir)
        for path in (
            os.path.join(marketplace_dir, "cache.bin"),
            os.path.join(backup_dir, "backup.bin"),
        ):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--tmp", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "clean.profiles")
        self.assertFalse(os.path.exists(marketplace_dir))
        self.assertFalse(os.path.exists(backup_dir))
        self.assertEqual(payload["profiles"][0]["profile"], "main")

    def test_clean_profiles_tmp_reports_removal_failure(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        with open(os.path.join(marketplace_dir, "cache.bin"), "wb") as handle:
            handle.write(b"x")

        with mock.patch("src.cli_commands.shutil.rmtree", side_effect=OSError("permission denied")):
            with self.assertRaisesRegex(CdxError, "Failed to remove cleanup candidate"):
                main(["clean", "profiles", "--tmp", "--yes"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir},
                })

    def test_clean_profiles_old_logs_removes_only_old_log_files(self):
        temp_dir = self.make_temp_dir()
        log_dir = os.path.join(temp_dir, "profiles", "main", "log")
        os.makedirs(log_dir)
        old_log = os.path.join(log_dir, "old.log")
        new_log = os.path.join(log_dir, "new.log")
        for path in (old_log, new_log):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)
        os.utime(old_log, (1000, 1000))
        os.utime(new_log, (1000 + 29 * 86400, 1000 + 29 * 86400))

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--old-logs", "30d", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["profiles"][0]["removed_count"], 1)
        self.assertFalse(os.path.exists(old_log))
        self.assertTrue(os.path.exists(new_log))

    def test_clean_profiles_bare_prints_usage(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx clean profiles"):
            main(["clean", "profiles"], {
                **self.make_io(),
                "env": {"CDX_HOME": self.make_temp_dir()},
            })

    def test_clean_old_logs_equals_routes_to_profiles_cleanup(self):
        temp_dir = self.make_temp_dir()
        old_log = os.path.join(temp_dir, "profiles", "main", "log", "old.log")
        os.makedirs(os.path.dirname(old_log))
        with open(old_log, "wb") as handle:
            handle.write(b"x")
        os.utime(old_log, (1000, 1000))

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "--old-logs=30", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "clean.profiles")
        self.assertFalse(os.path.exists(old_log))

    def test_clean_profiles_old_logs_reports_removal_failure(self):
        temp_dir = self.make_temp_dir()
        old_log = os.path.join(temp_dir, "profiles", "main", "log", "old.log")
        os.makedirs(os.path.dirname(old_log))
        with open(old_log, "wb") as handle:
            handle.write(b"x")
        os.utime(old_log, (1000, 1000))

        real_remove = os.remove

        def remove(path):
            if path == old_log:
                raise OSError("permission denied")
            return real_remove(path)

        with mock.patch("src.cli_commands.os.remove", side_effect=remove):
            with self.assertRaisesRegex(CdxError, "Failed to remove old log"):
                main(["clean", "profiles", "--old-logs", "30d", "--yes"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir},
                    "now": lambda: 1000 + 31 * 86400,
                })

    def test_clean_profiles_without_cleanup_flags_is_profiles_usage(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("profiles")
        log_path = os.path.join(temp_dir, "profiles", "profiles", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("session transcript")

        with self.assertRaisesRegex(CdxError, "Usage: cdx clean profiles"):
            main(["clean", "profiles", "--yes", "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
            })
        self.assertGreater(os.path.getsize(log_path), 0)

    def test_clean_profiles_requires_confirmation_before_deleting(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        cache_path = os.path.join(marketplace_dir, "cache.bin")
        with open(cache_path, "wb") as handle:
            handle.write(b"x")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--tmp", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "confirmProfileCleanup": lambda _action: False,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertTrue(payload["cancelled"])
        self.assertTrue(os.path.exists(cache_path))

    def test_clean_profiles_requires_yes_in_non_interactive_mode(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces"))

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal or --yes"):
            main(["clean", "profiles", "--tmp"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "stdin": {"isTTY": False},
            })

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

    def test_main_screen_surfaces_disk_cleanup_notice(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkDiskCleanup": lambda _service, _options: {
                "tool": "cdx-disk",
                "code": "disk_cleanup_available",
                "message": "Disk cleanup available: 2 GB reclaimable. Inspect: cdx disk profiles --candidates",
                "reclaimable_bytes": 2 * 1024 * 1024 * 1024,
            },
        }), 0)

        self.assertIn("Disk cleanup available: 2 GB reclaimable", list_io["stdout"].getvalue())

    def test_main_screen_json_includes_disk_cleanup_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkDiskCleanup": lambda _service, _options: {
                "tool": "cdx-disk",
                "code": "disk_cleanup_available",
                "message": "Disk cleanup available: 2 GB reclaimable. Inspect: cdx disk profiles --candidates",
                "reclaimable_bytes": 2 * 1024 * 1024 * 1024,
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "disk_cleanup_available")
        self.assertEqual(payload["warnings"][0]["reclaimable_bytes"], 2 * 1024 * 1024 * 1024)

    def test_disk_cleanup_notice_checks_daily(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        sizes = {
            temp_dir: str(11 * 1024 * 1024),
            profile_dir: str(3 * 1024 * 1024),
            marketplace_dir: str(2 * 1024 * 1024),
        }

        def runner(argv, **kwargs):
            return f"{sizes.get(argv[2], '1')}\t{argv[2]}\n"

        options = {
            "diskUsageRunner": runner,
            "now": lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        first = _get_disk_cleanup_notice(service, options)
        second = _get_disk_cleanup_notice(service, options)

        self.assertIsNotNone(first)
        self.assertEqual(first["code"], "disk_cleanup_available")
        self.assertIn("cdx clean profiles --tmp", first["message"])
        self.assertIsNone(second)

    def test_reset_consumes_banked_codex_reset_and_refreshes_status(self):
        temp_dir = self.make_temp_dir()
        status = {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 40,
            "reset_credits_available": 1,
            "reset_credits": [{"id": "reset-1"}],
            "updated_at": "2026-07-12T10:00:00+02:00",
            "source_ref": "api:codex-app-server-rate-limits",
        }
        service = create_session_service({"base_dir": temp_dir, "fetchCodexRateLimits": lambda _session: status})
        service["create_session"]("main")
        calls = []

        def consume(session, key, credit_id=None):
            calls.append((session["name"], key, credit_id))
            return {"ok": True, "outcome": "reset"}

        reset_io = self.make_io()
        self.assertEqual(main(["reset", "main", "--yes", "--json"], {
            **reset_io,
            "env": {"CDX_HOME": temp_dir},
            "service": service,
            "consumeCodexReset": consume,
            "resetIdempotencyKey": "attempt-1",
        }), 0)

        payload = json.loads(reset_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "reset")
        self.assertEqual(payload["outcome"], "reset")
        self.assertEqual(calls, [("main", "attempt-1", "reset-1")])

    def test_reset_requires_confirmation_in_non_interactive_mode(self):
        temp_dir = self.make_temp_dir()
        status = {"reset_credits_available": 1, "updated_at": "2026-07-12T10:00:00+02:00"}
        service = create_session_service({"base_dir": temp_dir, "fetchCodexRateLimits": lambda _session: status})
        service["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal or --yes"):
            main(["reset", "main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
                "stdin": {"isTTY": False},
            })

    def test_reset_rejects_when_no_banked_reset_is_available(self):
        temp_dir = self.make_temp_dir()
        status = {"reset_credits_available": 0, "updated_at": "2026-07-12T10:00:00+02:00"}
        service = create_session_service({"base_dir": temp_dir, "fetchCodexRateLimits": lambda _session: status})
        service["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "No banked Codex reset"):
            main(["reset", "main", "--yes"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
            })

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

    def test_memory_commands_support_current_global_project_and_list(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        other = os.path.join(temp_dir, "other")
        os.makedirs(workspace)
        os.makedirs(other)

        current_io = self.make_io()
        self.assertEqual(main(["memory", "append", "Current note", "--json"], {
            **current_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        current_payload = json.loads(current_io["stdout"].getvalue())
        self.assertEqual(current_payload["action"], "memory.append")
        self.assertEqual(current_payload["memory"]["scope"], "current")

        global_io = self.make_io()
        self.assertEqual(main(["memory", "--global", "append", "Global note", "--json"], {
            **global_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        self.assertEqual(json.loads(global_io["stdout"].getvalue())["memory"]["scope"], "global")

        project_io = self.make_io()
        self.assertEqual(main(["memory", "--project", "client A", "append", "Project note", "--json"], {
            **project_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        project_payload = json.loads(project_io["stdout"].getvalue())
        self.assertEqual(project_payload["memory"]["project"], "client A")
        self.assertEqual(project_payload["memory"]["project_kind"], "name")

        path_io = self.make_io()
        self.assertEqual(main(["memory", "--project", workspace, "path", "--json"], {
            **path_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        path_payload = json.loads(path_io["stdout"].getvalue())
        self.assertEqual(path_payload["memory"]["project_kind"], "path")
        self.assertEqual(path_payload["memory"]["path"], current_payload["memory"]["path"])

        list_io = self.make_io()
        self.assertEqual(main(["memory", "list", "--json"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        list_payload = json.loads(list_io["stdout"].getvalue())
        scopes = [entry["scope"] for entry in list_payload["memories"]]
        self.assertEqual(scopes, ["global", "project", "current"])
        self.assertEqual(list_payload["memories"][1]["project"], "client A")

    def test_memory_rejects_empty_append_and_conflicting_scope_flags(self):
        temp_dir = self.make_temp_dir()
        with self.assertRaisesRegex(CdxError, "Memory append requires text"):
            main(["memory", "append", "  "], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })
        with self.assertRaisesRegex(CdxError, "Usage: cdx memory"):
            main(["memory", "--global", "--project", "A", "path"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

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

    def test_unset_reasoning_effort_is_supported(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_launch_settings"]("main", {"reasoning_effort": "high"})

        unset_io = self.make_io()
        self.assertEqual(main(["unset", "main", "--reasoning-effort", "--json"], {
            **unset_io,
            "service": service,
        }), 0)

        self.assertNotIn("reasoning_effort", json.loads(unset_io["stdout"].getvalue())["launch"])

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

    def test_set_rejects_conflicting_target_selectors_and_flag_values(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        # --sessions and --provider are mutually exclusive target scopes.
        with self.assertRaises(CdxError):
            main(["set", "--sessions", "main", "--provider", "codex", "--model", "opus"],
                 {**self.make_io(), "service": service})
        with self.assertRaises(CdxError):
            main(["unset", "--sessions", "main", "--provider", "codex", "--model"],
                 {**self.make_io(), "service": service})

        # A known flag can't be swallowed as another flag's value.
        with self.assertRaises(CdxError):
            main(["set", "main", "--model", "--json"], {**self.make_io(), "service": service})
        launch = service["get_session"]("main").get("launch") or {}
        self.assertIsNone(launch.get("model"))

    def test_subcommand_dash_h_is_not_hijacked_by_top_level_help(self):
        io_obj = self.make_io()
        with self.assertRaises(CdxError) as caught:
            main(["history", "-h"], {**io_obj, "service": create_session_service({"base_dir": self.make_temp_dir()})})
        self.assertNotIn("Usage: cdx --help", str(caught.exception))

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

        with self.assertRaisesRegex(CdxError, "Usage: cdx stats"):
            main(["stats", "--since", "7d", "--from", "2026-05-28"], {
                **self.make_io(),
                "service": service,
                "now": lambda: now.timestamp(),
            })

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

        # Claude login now mints a long-lived setup-token (wrapped via script); no logout first.
        self.assertEqual(
            [call["args"] for call in harness.calls
             if call["kind"] == "spawn" and call["command"] == "claude" and "logout" in call["args"]],
            [],
        )
        setup_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
            and _script_launch_args(call) == ["setup-token"]
        )
        self.assertEqual(
            setup_call["options"]["env"]["ANTHROPIC_CONFIG_DIR"],
            os.path.join(temp_dir, "profiles", "work1", "claude-home"),
        )
        self.assertNotIn("CODEX_HOME", setup_call["options"]["env"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", setup_call["options"]["env"])

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
        with open(other_auth, encoding="utf-8") as handle:
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
        with open(cred_path, encoding="utf-8") as handle:
            credentials = json.load(handle)
        self.assertEqual(credentials["access_token"], "sk-ant-oat-test")
        if os.name != "nt":
            self.assertEqual(oct(os.stat(cred_path).st_mode & 0o777), "0o600")
            self.assertEqual(oct(os.stat(os.path.dirname(cred_path)).st_mode & 0o777), "0o700")
        self.assertFalse(os.path.exists(_script_transcript_path(script_call)))

    def test_login_claude_setup_token_flag_skips_login(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness(claude_login_authenticates=True)

        self.assertEqual(main([
            "add", "claude", "work1"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        harness.calls.clear()

        self.assertEqual(main([
            "login", "work1", "--setup-token", "--json"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        script_launches = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        ]
        self.assertEqual([_script_launch_args(call) for call in script_launches], [["setup-token"]])
        cred_path = os.path.join(temp_dir, "profiles", "work1", "claude-home", "credentials", "default.json")
        with open(cred_path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["access_token"], "sk-ant-oat-test")

    def test_login_claude_removes_setup_token_transcript_when_extraction_fails(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness(
            claude_login_authenticates=False,
            claude_setup_token_text="Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=<token>\n",
        )

        with self.assertRaisesRegex(CdxError, "Run claude setup-token manually"):
            main(["add", "claude", "work1"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })

        script_call = next(
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        )
        # The transcript may hold the cleartext token; it must never be kept.
        self.assertFalse(os.path.exists(_script_transcript_path(script_call)))

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

    def test_config_unknown_session_suggests_configs_and_add(self):
        temp_dir = self.make_temp_dir()
        io_obj = self.make_io()

        with self.assertRaisesRegex(CdxError, "Unknown session: configs\\. Run cdx configs") as ctx:
            main(["config", "configs"], {**io_obj, "env": {"CDX_HOME": temp_dir}})

        self.assertIn("cdx add configs", str(ctx.exception))
        payload = json.loads(format_json_error(ctx.exception))
        self.assertEqual(payload["error"]["code"], "unknown_session")
        self.assertIn("Run cdx configs", payload["error"]["message"])

    def test_config_usage_errors_remain_unchanged(self):
        for args in (["config"], ["config", "one", "two"]):
            with self.subTest(args=args):
                with self.assertRaisesRegex(CdxError, "Usage: cdx config <name> \\[--json\\]"):
                    main(args, self.make_io())

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
        self.assertEqual(main(["clean", "main", "--yes", "--json"], {
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
        with open(imported_auth, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_and_import_accept_passphrase_from_stdin(self):
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
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-stdin", "--json",
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "read_stdin": lambda: "pw123\n",
        }), 0)

        import_dir = self.make_temp_dir()
        self.assertEqual(main([
            "import", export_path, "--passphrase-stdin", "--json",
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": import_dir},
            "read_stdin": lambda: "pw123\n",
        }), 0)
        imported_auth = os.path.join(import_dir, "profiles", "claude1", "claude-home", "auth.json")
        with open(imported_auth, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')

    def test_export_rejects_conflicting_passphrase_sources(self):
        with self.assertRaisesRegex(CdxError, "mutually exclusive"):
            main([
                "export", "x.cdx", "--include-auth",
                "--passphrase-env", "VAR", "--passphrase-stdin", "--json",
            ], {**self.make_io(), "env": {}})

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
        self.assertEqual(main(["clean", "--yes", "--json"], {
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

    def test_clean_logs_requires_confirmation_before_truncating(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        log_path = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("transcript")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "main", "--json"], {
            **clean_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "confirmClean": lambda _target: False,
        }), 0)

        self.assertTrue(json.loads(clean_io["stdout"].getvalue())["cancelled"])
        self.assertGreater(os.path.getsize(log_path), 0)

    def test_export_with_auth_rejects_non_interactive_without_passphrase_env(self):
        temp_dir = self.make_temp_dir()
        create_session_service({"base_dir": temp_dir})["create_session"]("main")
        io_obj = self.make_io()
        io_obj["stdin"] = {"isTTY": False}

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal"):
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

    def test_status_uses_sync_refresh_function(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1", "claude")

        def refresh(_session):
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
        self.assertIn("Recommended: use work1 first (60% OK).", output)

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

    def test_status_keeps_claude_auth_when_probe_times_out(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def timeout_probe(_command, _args, _spec):
            raise subprocess.TimeoutExpired("claude", 15)

        status_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--json", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": timeout_probe,
            "refreshClaudeSessionStatus": lambda _session: None,
        }), 0)

        self.assertEqual(service["get_session"]("claude")["auth"]["status"], "authenticated")
        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["code"], "claude_auth_probe_failed")
        self.assertIn("timed out", payload["warnings"][0]["message"])

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
            "Recommended: use regular first (80% OK), next credit (95% OK).",
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
            "Recommended: use usable first (6% OK), next low (0% OK).",
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
            "Recommended: use work1 first (6% OK), next claude (0% OK, 5H resets first).",
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
            "Recommended: use work1 first (6% OK), next credit (0% OK, WEEK resets first).",
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
            "Recommended: use work1 first (6% OK), refresh claude next (0% OK, 5H reset passed).",
            status_io["stdout"].getvalue(),
        )

    def test_status_json_global_and_detail_contract(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_session_label"]("main", "work")
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
        self.assertEqual(rows[0]["label"], "work")
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
        self.assertEqual(row["label"], "work")
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

    def test_doctor_filters_severity_in_json_and_text(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        os.remove(os.path.join(temp_dir, "state", "main.json"))

        json_io = self.make_io()
        self.assertEqual(main(["doctor", "--severity=warn,fail", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        report = payload["report"]
        self.assertEqual(report["severity"], "WARN,FAIL")
        self.assertTrue(report["issues"])
        self.assertTrue(all(issue["status"] in {"WARN", "FAIL"} for issue in report["issues"]))
        self.assertEqual(report["summary"]["ok"], 0)
        self.assertEqual(report["summary"]["fail"], 1)

        text_io = self.make_io()
        self.assertEqual(main(["doctor", "--severity", "fail"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        text = text_io["stdout"].getvalue()
        self.assertIn("missing_state", text)
        self.assertNotIn("\nWARN", text)
        self.assertIn("Summary: 0 OK, 0 WARN, 1 FAIL", text)

    def test_doctor_rejects_invalid_or_repeated_severity(self):
        for args in (
            ["doctor", "--severity"],
            ["doctor", "--severity=info"],
            ["doctor", "--severity", "warn", "--severity", "fail"],
        ):
            with self.subTest(args=args):
                with self.assertRaisesRegex(CdxError, "Usage: cdx doctor"):
                    main(args, self.make_io())

    def test_doctor_severity_allows_empty_matches(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        io_obj = self.make_io()

        self.assertEqual(main(["doctor", "--severity", "FAIL", "--json"], {
            **io_obj,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        report = json.loads(io_obj["stdout"].getvalue())["report"]
        self.assertEqual(report["severity"], "FAIL")
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["summary"], {"ok": 0, "warn": 0, "fail": 0, "repairable": 0})

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

    def test_doctor_treats_shared_codex_business_account_id_as_ambiguous(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        first = service["create_session"]("worka")
        second = service["create_session"]("workb")
        for session, email in ((first, "paul@example.com"), (second, "romaric@example.com")):
            with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
                json.dump({"tokens": {"refresh_token": "secret-token", "account_id": "acct-business-123456789"}}, handle)
            log_dir = os.path.join(session["authHome"], "log")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "cdx-session.log"), "w", encoding="utf-8") as handle:
                handle.write(f"Account: {email} (Business)\n")
        harness = _AuthHarness()

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        issue = next(item for item in payload["report"]["issues"] if item["code"] == "codex_shared_account_id")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"]["account_id"], "acct-b...6789")
        self.assertEqual(issue["detail"]["observed_identities"], ["paul@example.com", "romaric@example.com"])
        self.assertIn("not a user identity", issue["message"])
        self.assertNotIn("secret-token", json.dumps(payload))

    def test_doctor_reports_recent_codex_stale_auth_logs(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        session = service["create_session"]("main")
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"refresh_token": "secret-token"}}, handle)
        log_dir = os.path.join(session["authHome"], "log")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "cdx-session.log"), "w", encoding="utf-8") as handle:
            handle.write("HTTP 401 token_expired: authentication token is expired\n")

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness().spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        issue = next(item for item in payload["report"]["issues"] if item["code"] == "codex_stale_auth_logs")
        self.assertEqual(issue["status"], "WARN")
        self.assertEqual(issue["detail"]["markers"], ["token_expired", "authentication token is expired", "http 401"])
        self.assertIn("cdx login main", issue["message"])
        self.assertNotIn("secret-token", json.dumps(payload))

    def test_doctor_reports_codex_auth_probe_timeout_as_degraded(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        def timeout_probe(_command, _args, _spec):
            raise subprocess.TimeoutExpired("codex", 15)

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": timeout_probe,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        live_auth = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_live_auth")
        self.assertEqual(live_auth["detail"]["live_status"], "degraded")
        self.assertIn("Auth probe timed out", live_auth["detail"]["live_error"])

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

    def test_doctor_reports_provider_cli_versions_and_capability_hints(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }
        harness = _AuthHarness()

        with mock.patch(
            "src.health.shutil.which",
            side_effect=lambda command, path=None: f"/usr/bin/{command}" if command in {"codex", "claude"} else None,
        ):
            report = collect_health_report(
                service,
                temp_dir,
                env={"PATH": "/usr/bin"},
                spawn_sync=harness.spawn_sync,
            )

        codex = next(item for item in report["issues"] if item["code"] == "codex_cli_version")
        claude = next(item for item in report["issues"] if item["code"] == "claude_cli_version")
        self.assertEqual(codex["detail"]["version"], "0.145.0")
        self.assertIn("provider_memory_import_surfaces_may_exist_in_recent_codex", codex["detail"]["capabilities"])
        self.assertEqual(claude["detail"]["version"], "2.1.219")
        self.assertIn("project_memory_and_stream_json_diagnostics_may_exist_in_recent_claude_code", claude["detail"]["capabilities"])

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
            }), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
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
            with mock.patch("src.notify.shutil.which", side_effect=lambda command, path=None: command == "systemd-run"):
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
            with mock.patch("src.notify.shutil.which", side_effect=lambda command, path=None: command == "systemd-run"):
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

    def test_ready_without_upcoming_reset_returns_unscheduled_result(self):
        temp_dir = self.make_temp_dir()
        service = {
            "base_dir": temp_dir,
            "get_status_rows": lambda **_kwargs: [],
        }

        json_io = self.make_io()
        self.assertEqual(main(["ready", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["schedule"]["scheduled"])
        self.assertEqual(payload["schedule"]["backend"], "none")
        self.assertEqual(payload["event"]["message"], "No upcoming session reset available")

        text_io = self.make_io()
        self.assertEqual(main(["ready"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("No upcoming session reset available", text_io["stdout"].getvalue())

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

    def _authenticated_codex_session(self, service, name="work"):
        session = service["create_session"](name, "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["update_auth_state"](name, lambda auth: {**auth, "status": "authenticated"})
        service["record_status"](name, {"remaining_5h_pct": 75, "remaining_week_pct": 75})
        return session

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

    def test_empty_power_blames_the_flag_that_was_passed(self):
        target = self.make_temp_dir()
        with self.assertRaises(CdxError) as caught:
            _parse_run_args(["main", "--cwd", target, "--prompt", "x", "--power", "", "--json"])

        self.assertEqual(caught.exception.arguments, ("--power",))

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

    def _finished_run_with_output(self, service, text, run_id="tail-run"):
        registry = RunRegistry(service["base_dir"])
        stdout_path = os.path.join(self.make_temp_dir(), "run.stdout.log")
        with open(stdout_path, "wb") as handle:
            handle.write(text)
        registry.start(
            run_id, kind="assistant", session="work", provider="codex",
            model=None, cwd=".", artifacts={"stdout_path": stdout_path},
        )
        return run_id, stdout_path

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

    def test_every_validator_shares_one_accepted_value_definition(self):
        # Not equality but identity: equality would still pass if someone
        # reintroduced a second literal that happened to match today. These
        # names must all resolve to the one definition config.py owns.
        from src import config, provider_runtime, session_service

        for shared in (
            RUN_EFFORT_VALUES,
            provider_runtime.REASONING_EFFORT_VALUES,
            session_service.LAUNCH_POWER_VALUES,
            session_service.LAUNCH_REASONING_EFFORT_VALUES,
        ):
            self.assertIs(shared, config.REASONING_EFFORT_VALUES)

        self.assertIs(RUN_PERMISSION_CANONICAL_VALUES, config.PERMISSION_VALUES)
        self.assertIs(session_service.LAUNCH_PERMISSION_VALUES, config.PERMISSION_VALUES)
        self.assertIs(RUN_PERMISSION_ALIASES, config.PERMISSION_ALIASES)

    def test_no_module_restates_an_accepted_value_set(self):
        # The guard that keeps the deduplication from silently regressing: a
        # fresh copy of one of these sets anywhere in src/ fails here, named.
        import pathlib
        import re

        duplicates = []
        for path in sorted(pathlib.Path("src").glob("*.py")):
            if path.name == "config.py":
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                literal = re.match(r'^[A-Z_]{4,}\s*=\s*([\{\(].*[\}\)])\s*$', line.strip())
                if not literal:
                    continue
                values = set(re.findall(r'"([^"]+)"', literal.group(1)))
                if values in (set(RUN_EFFORT_VALUES), set(RUN_PERMISSION_CANONICAL_VALUES)):
                    duplicates.append(f"{path}:{number} {line.strip()}")
        self.assertEqual(duplicates, [], "accepted-value set restated instead of imported from config")

    def test_set_and_run_accept_the_same_values(self):
        from src import config
        from src.session_service import _normalize_launch_settings

        # A value accepted by one command must be accepted by the other; the
        # asymmetry this replaces rejected `cdx set --permission workspace-write`
        # while `cdx run --permission workspace-write` worked.
        target = self.make_temp_dir()
        for permission in config.PERMISSION_INPUT_VALUES:
            expected = config.normalize_permission(permission)
            self.assertEqual(
                _parse_run_args(["main", "--cwd", target, "--prompt", "x",
                                 "--permission", permission, "--json"])["permission"],
                expected,
            )
            self.assertEqual(
                _normalize_launch_settings({"permission": permission})["permission"],
                expected,
            )

        for effort in config.REASONING_EFFORT_VALUES:
            _parse_run_args(["main", "--cwd", target, "--prompt", "x",
                             "--reasoning-effort", effort, "--json"])
            _normalize_launch_settings({"power": effort})
            _normalize_launch_settings({"reasoning_effort": effort})

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

    def _health_report(self, service, help_text=None, cli_installed=True, **kwargs):
        from src.health import collect_health_report

        def spawn_sync(_command, args, _options):
            if args == ["--help"] and help_text is not None:
                return {"stdout": help_text, "stderr": ""}
            return {"stdout": "", "stderr": ""}

        # Whether a provider CLI is installed is a property of the machine, not
        # of the behavior under test. Left unpatched these tests pass on a
        # developer box with codex installed and fail on CI, which is exactly
        # what they did.
        which = (lambda command, path=None: f"/usr/bin/{command}") if cli_installed else (
            lambda command, path=None: None
        )
        with mock.patch("src.health.shutil.which", side_effect=which):
            return collect_health_report(
                service, service["base_dir"], env=os.environ, spawn_sync=spawn_sync, **kwargs
            )

    def _flag_issue(self, report, provider):
        return next(i for i in report["issues"] if i["code"] == f"{provider}_permission_flags")

    def test_provider_flag_check_confirms_a_complete_mapping(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(
            service,
            help_text="-s <sandbox> -a <approval> --dangerously-bypass-approvals-and-sandbox -c <cfg>",
            check_provider_flags=True,
        )

        self.assertEqual(self._flag_issue(report, "codex")["status"], "OK")

    def test_provider_flag_check_fails_on_a_flag_the_cli_lacks(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        # The issue #8 condition: a mapped flag the provider CLI never had.
        with mock.patch.dict(
            provider_runtime.LAUNCH_PERMISSION_ARGS[provider_runtime.PROVIDER_CODEX],
            {"full": ["--experimental-yolo"]},
        ):
            report = self._health_report(
                service,
                help_text="-s -a --dangerously-bypass-approvals-and-sandbox -c",
                check_provider_flags=True,
            )

        issue = self._flag_issue(report, "codex")
        self.assertEqual(issue["status"], "FAIL")
        self.assertEqual(issue["detail"]["missing"], {"full": ["--experimental-yolo"]})

    def test_provider_flag_check_is_indeterminate_without_the_cli(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service, cli_installed=False, check_provider_flags=True)

        # Not a failure, and emphatically not a pass: "could not check" is the
        # state issue #8 lived in for months.
        self.assertEqual(self._flag_issue(report, "codex")["status"], "WARN")

    def test_provider_flag_check_is_indeterminate_on_unreadable_help(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service, help_text="", check_provider_flags=True)

        self.assertEqual(self._flag_issue(report, "codex")["status"], "WARN")

    def test_provider_with_no_mapping_reads_as_deliberate(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("local", "ollama")

        report = self._health_report(service, help_text="run", check_provider_flags=True)

        # ollama maps nothing on purpose; that must not look like an
        # unverified mapping.
        issue = self._flag_issue(report, "ollama")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"]["mapped"], {})

    def test_provider_flag_check_absence_is_reported_not_omitted(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service)

        codes = [i["code"] for i in report["issues"]]
        self.assertNotIn("codex_permission_flags", codes)
        # A check that did not run must say so; silently omitting it would let
        # a green doctor imply the mappings were verified.
        unchecked = next(i for i in report["issues"] if i["code"] == "provider_permission_flags_unchecked")
        self.assertEqual(unchecked["status"], "WARN")

    def _ranked(self, rows, **kwargs):
        from src.session_ranking import rank_sessions

        ordered, decision = rank_sessions(rows, 1_000_000, lambda _row: None, **kwargs)
        return [row["session_name"] for row in ordered], decision

    def _row(self, name, **overrides):
        return {
            "session_name": name, "provider": "codex", "enabled": True,
            "auth_status": "authenticated", "available_pct": 50, "credits": None,
            "priority": 0, "reasoning_effort": "medium", **overrides,
        }

    def test_priority_orders_two_otherwise_equal_sessions(self):
        names, decision = self._ranked([
            self._row("plain"),
            self._row("preferred", priority=90),
        ])

        self.assertEqual(names[0], "preferred")
        self.assertEqual(decision, "priority")

    def test_priority_does_not_promote_a_session_that_cannot_serve(self):
        names, _ = self._ranked([
            self._row("usable", available_pct=40),
            self._row("empty", available_pct=0, priority=99),
        ])

        # Priority says which usable session to prefer. It does not make an
        # exhausted session the right place to send work.
        self.assertEqual(names[0], "usable")

    def test_every_selector_agrees_on_the_best_session(self):
        from src.status_view import recommend_priority_rows

        rows = [self._row("beta", available_pct=30), self._row("alpha", available_pct=80, priority=10)]

        ranked, _ = self._ranked(rows)
        self.assertEqual(recommend_priority_rows(rows)[0]["session_name"], ranked[0])

    def test_require_ready_rejects_an_unknown_auth_state(self):
        names, _ = self._ranked(
            [self._row("unknown", auth_status="unknown"), self._row("known")],
            require_ready=True,
        )

        # `cdx run --provider` asks for readiness so it does not hand work to a
        # session that will fail at launch; unknown is not ready.
        self.assertEqual(names, ["known"])

    def test_recommendation_still_surfaces_unknown_auth_sessions(self):
        names, _ = self._ranked([self._row("unknown", auth_status="unknown")])

        # Without require_ready (cdx next, cdx status) an unverified session is
        # still worth showing; it is only excluded from being run.
        self.assertEqual(names, ["unknown"])

    def test_logged_out_sessions_are_never_candidates(self):
        names, _ = self._ranked([
            self._row("out", auth_status="logged_out", available_pct=99),
            self._row("in", available_pct=10),
        ])

        # `cdx select` without --require-ready used to be able to return one.
        self.assertEqual(names, ["in"])

    def test_lower_reasoning_effort_wins_a_tie(self):
        names, decision = self._ranked([
            self._row("strong", reasoning_effort="xhigh"),
            self._row("cheap", reasoning_effort="low"),
        ])

        # Deliberate cost preference, kept from the headless ranking where it
        # was implied by an un-negated sort term.
        self.assertEqual(names[0], "cheap")
        self.assertEqual(decision, "reasoning_effort")

    def test_single_candidate_reports_no_deciding_factor(self):
        _names, decision = self._ranked([self._row("only")])

        self.assertIsNone(decision)

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

    def test_every_version_declaration_agrees(self):
        import pathlib
        import re

        from src.cli import VERSION

        root = pathlib.Path(".")
        declared = (root / "VERSION").read_text().strip()
        package_json = json.loads((root / "package.json").read_text())["version"]
        pyproject = re.search(
            r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M
        ).group(1)
        badge = re.search(r"badge/version-v([0-9][^-]*)-", (root / "README.md").read_text()).group(1)

        # cli.py used to restate the version as a fourth copy and drifted a
        # release behind, so `cdx --version` reported a release it was not.
        self.assertEqual(VERSION, declared)
        self.assertEqual(package_json, declared)
        self.assertEqual(pyproject, declared)
        self.assertEqual(badge, declared)

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

    def test_bin_cdx_delegates_to_cli_entry(self):
        with open("bin/cdx", encoding="utf-8") as handle:
            text = handle.read()

        self.assertIn("from src.cli import cli_entry", text)
        self.assertIn("cli_entry()", text)
        self.assertNotIn("format_json_error", text)
        self.assertNotIn("except CdxError", text)

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
