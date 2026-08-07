"""Shared fixtures for the cdx command test modules.

Split out of test_cli_py.py alongside src/commands/: the per-domain test
modules all subclass CliTestBase rather than restating its fixtures.
Not named test_*_py.py, so pytest does not collect it as a test module.
"""

import importlib.util
import io
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

from src.health import collect_health_report
from src.run_registry import RunRegistry

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


class CliTestBase(unittest.TestCase):
    """Fixtures shared by every command test module."""

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

    def _authenticated_codex_session(self, service, name="work"):
        session = service["create_session"](name, "codex")
        os.makedirs(session["authHome"], exist_ok=True)
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "token"}}, handle)
        service["update_auth_state"](name, lambda auth: {**auth, "status": "authenticated"})
        service["record_status"](name, {"remaining_5h_pct": 75, "remaining_week_pct": 75})
        return session

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

    def _health_report(self, service, help_text=None, cli_installed=True, **kwargs):

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

