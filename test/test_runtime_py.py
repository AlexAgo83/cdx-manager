import json
import os
import signal
import tempfile
import unittest
import urllib.error
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest import mock

from src import claude_usage
from src import cli
from src import notify
from src import provider_runtime
from src.errors import CdxError
from src.provider_runtime import _run_interactive_provider_command


class _Response:
    def __init__(self, headers):
        self._headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getheaders(self):
        return list(self._headers.items())


class RuntimePythonTests(unittest.TestCase):
    def format_local_reset(self, unix_seconds):
        dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).astimezone()
        return f"{dt.strftime('%b')} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"

    def test_fetch_claude_rate_limit_headers_from_success_response(self):
        headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.19",
            "anthropic-ratelimit-unified-5h-reset": "1776464880",
            "anthropic-ratelimit-unified-7d-utilization": "0.25",
            "anthropic-ratelimit-unified-7d-reset": "1777065600",
        }
        with mock.patch("urllib.request.urlopen", return_value=_Response(headers)):
            result = claude_usage.fetch_claude_rate_limit_headers("token")
        self.assertEqual(result["remaining_5h_pct"], 81)
        self.assertEqual(result["remaining_week_pct"], 75)
        self.assertEqual(result["reset_5h_at"], self.format_local_reset(1776464880))
        self.assertEqual(result["reset_week_at"], self.format_local_reset(1777065600))
        self.assertEqual(result["reset_at"], self.format_local_reset(1777065600))
        self.assertEqual(
            datetime.fromisoformat(result["updated_at"]).utcoffset(),
            datetime.now().astimezone().utcoffset(),
        )

    def test_fetch_claude_rate_limit_headers_uses_configured_model(self):
        captured = {}

        def urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _Response({
                "anthropic-ratelimit-unified-5h-utilization": "0.19",
            })

        with mock.patch("src.claude_usage.CLAUDE_STATUS_PROBE_MODEL", "test-model"):
            with mock.patch("urllib.request.urlopen", side_effect=urlopen):
                claude_usage.fetch_claude_rate_limit_headers("token")

        self.assertEqual(captured["body"]["model"], "test-model")

    def test_fetch_claude_rate_limit_headers_from_http_error_headers(self):
        headers = {
            "anthropic-ratelimit-unified-5h-utilization": "0.50",
            "anthropic-ratelimit-unified-5h-reset": "1776464880",
        }
        error = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=429,
            msg="rate limited",
            hdrs=headers,
            fp=None,
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            result = claude_usage.fetch_claude_rate_limit_headers("token")
        self.assertEqual(result["remaining_5h_pct"], 50)
        self.assertIsNone(result["remaining_week_pct"])
        self.assertEqual(result["reset_5h_at"], self.format_local_reset(1776464880))
        self.assertIsNone(result["reset_week_at"])
        self.assertEqual(result["reset_at"], self.format_local_reset(1776464880))

    def test_fetch_claude_rate_limit_headers_returns_none_on_url_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertIsNone(claude_usage.fetch_claude_rate_limit_headers("token"))

    def test_refresh_claude_session_status_without_credentials_returns_none(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            self.assertIsNone(claude_usage.refresh_claude_session_status({"authHome": temp_dir}))

    def test_refresh_claude_session_status_reads_credentials(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, ".claude")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, ".credentials.json"), "w", encoding="utf-8") as handle:
                json.dump({"claudeAiOauth": {"accessToken": "secret"}}, handle)
            with mock.patch("src.claude_usage.fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 77}) as fetch:
                result = claude_usage.refresh_claude_session_status({"authHome": temp_dir})
            fetch.assert_called_once_with("secret")
            self.assertEqual(result["remaining_5h_pct"], 77)

    def test_rotate_log_if_needed_truncates_large_file(self):
        with tempfile.TemporaryDirectory(prefix="cdx-log-") as temp_dir:
            log_path = os.path.join(temp_dir, "cdx-session.log")
            with open(log_path, "wb") as handle:
                handle.write(b"x" * cli.LOG_ROTATE_BYTES)
            cli._rotate_log_if_needed(log_path)
            self.assertEqual(os.path.getsize(log_path), 0)

    def test_enable_windows_ansi_sets_virtual_terminal_mode(self):
        set_mode_calls = []

        class FakeKernel32:
            def GetStdHandle(self, handle_id):
                return handle_id

            def GetConsoleMode(self, _handle, mode):
                mode.value = 1
                return True

            def SetConsoleMode(self, handle, mode):
                set_mode_calls.append((handle, mode))
                return True

        fake_ctypes = SimpleNamespace(
            windll=SimpleNamespace(kernel32=FakeKernel32()),
            c_ulong=lambda: SimpleNamespace(value=0),
            byref=lambda value: value,
        )

        with mock.patch("src.cli.sys.platform", "win32"):
            with mock.patch.dict("sys.modules", {"ctypes": fake_ctypes}):
                cli._enable_windows_ansi()

        self.assertEqual(set_mode_calls, [(-10, 5), (-11, 5), (-12, 5)])

    def test_configure_windows_encoding_reconfigures_streams(self):
        calls = []

        class Stream:
            def __init__(self, name):
                self.name = name

            def reconfigure(self, **kwargs):
                calls.append((self.name, kwargs))

        with mock.patch("src.cli.sys.platform", "win32"):
            with mock.patch("src.cli.sys.stdout", Stream("stdout")):
                with mock.patch("src.cli.sys.stderr", Stream("stderr")):
                    cli._configure_windows_encoding()

        self.assertEqual(calls, [
            ("stdout", {"encoding": "utf-8", "errors": "replace"}),
            ("stderr", {"encoding": "utf-8", "errors": "replace"}),
        ])

    def test_home_env_overrides_sets_windows_profile_variables(self):
        with mock.patch("src.provider_runtime.sys.platform", "win32"):
            with mock.patch(
                "src.provider_runtime.os.path.splitdrive",
                return_value=("C:", r"\Users\Test\AppData\Local\cdx\claude-home"),
            ):
                result = provider_runtime._home_env_overrides(r"C:\Users\Test\AppData\Local\cdx\claude-home")

        self.assertEqual(result["HOME"], r"C:\Users\Test\AppData\Local\cdx\claude-home")
        self.assertEqual(result["USERPROFILE"], r"C:\Users\Test\AppData\Local\cdx\claude-home")
        self.assertEqual(result["HOMEDRIVE"], "C:")
        self.assertEqual(result["HOMEPATH"], r"\Users\Test\AppData\Local\cdx\claude-home")

    def test_send_windows_notification_uses_powershell(self):
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))

        with mock.patch("sys.platform", "win32"):
            notify.send_desktop_notification("Title", "Hello 'World'", spawn_sync=spawn_sync, env={"PATH": ""})

        self.assertEqual(calls[0][0][:3], ["powershell", "-NoProfile", "-NonInteractive"])
        self.assertIn("System.Windows.Forms", calls[0][0][4])
        self.assertIn("Hello ''World''", calls[0][0][4])

    def test_run_interactive_provider_command_reports_raw_int_signal_name(self):
        session = {
            "name": "claude",
            "provider": "claude",
            "authHome": "/tmp/claude-home",
        }

        class FakeChild:
            def __init__(self, emitter):
                self.emitter = emitter
                self.returncode = 0
                self.signals = []

            def send_signal(self, sig):
                self.signals.append(sig)

            def wait(self):
                self.emitter.handlers["SIGINT"]()
                return 0

        class FakeEmitter:
            def __init__(self):
                self.handlers = {}

            def on(self, name, handler):
                self.handlers[name] = handler

            def removeListener(self, name, handler):
                if self.handlers.get(name) is handler:
                    self.handlers.pop(name, None)

        emitter = FakeEmitter()
        child = FakeChild(emitter)

        def spawn(_argv, **_kwargs):
            return child

        with self.assertRaises(CdxError) as error:
            _run_interactive_provider_command(
                session,
                "launch",
                spawn=spawn,
                signal_emitter=emitter,
            )

        self.assertEqual(str(error.exception), "claude interrupted by SIGINT for session claude")
        self.assertEqual(error.exception.exit_code, 130)
        self.assertEqual(child.signals, [signal.SIGINT])


if __name__ == "__main__":
    unittest.main()
