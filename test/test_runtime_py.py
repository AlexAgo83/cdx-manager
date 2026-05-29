import json
import os
import io
import signal
import tempfile
import unittest
import urllib.error
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest import mock

from src import claude_usage
from src import cli
from src import codex_usage
from src import notify
from src import provider_runtime
from src import run_usage
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


class _FakeStdin:
    def __init__(self):
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        pass


class _FakeProcess:
    def __init__(self, stdout_lines):
        self.stdin = _FakeStdin()
        self.stdout = iter(stdout_lines)
        self.stderr = iter([])
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


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

    def test_fetch_claude_rate_limit_headers_clamps_remaining_percentages(self):
        headers = {
            "anthropic-ratelimit-unified-5h-utilization": "1.10",
            "anthropic-ratelimit-unified-7d-utilization": "-0.20",
        }
        with mock.patch("urllib.request.urlopen", return_value=_Response(headers)):
            result = claude_usage.fetch_claude_rate_limit_headers("token")
        self.assertEqual(result["remaining_5h_pct"], 0)
        self.assertEqual(result["remaining_week_pct"], 100)

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

    def test_fetch_claude_rate_limit_headers_raises_on_http_error_without_usage_headers(self):
        body = json.dumps({"error": {"message": "subscription inactive"}}).encode("utf-8")
        error = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=403,
            msg="forbidden",
            hdrs={},
            fp=io.BytesIO(body),
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(CdxError, "Claude usage unavailable .*subscription inactive"):
                claude_usage.fetch_claude_rate_limit_headers("token")

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

    def test_refresh_claude_session_status_prefers_cli_credentials_over_setup_token(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cli_cred_dir = os.path.join(temp_dir, ".claude")
            setup_cred_dir = os.path.join(temp_dir, "credentials")
            os.makedirs(cli_cred_dir, exist_ok=True)
            os.makedirs(setup_cred_dir, exist_ok=True)
            with open(os.path.join(cli_cred_dir, ".credentials.json"), "w", encoding="utf-8") as handle:
                json.dump({"claudeAiOauth": {"accessToken": "fresh-cli"}}, handle)
            with open(os.path.join(setup_cred_dir, "default.json"), "w", encoding="utf-8") as handle:
                json.dump({"type": "oauth_token", "access_token": "<token>\x1b[39m"}, handle)

            with mock.patch("src.claude_usage.fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 77}) as fetch:
                result = claude_usage.refresh_claude_session_status({"authHome": temp_dir})

            fetch.assert_called_once_with("fresh-cli")
            self.assertEqual(result["remaining_5h_pct"], 77)

    def test_refresh_claude_session_status_reads_anthropic_credentials(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, "credentials")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, "default.json"), "w", encoding="utf-8") as handle:
                json.dump({"type": "oauth_token", "access_token": "secret"}, handle)
            with mock.patch("src.claude_usage.fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 77}) as fetch:
                result = claude_usage.refresh_claude_session_status({"authHome": temp_dir})
            fetch.assert_called_once_with("secret")
            self.assertEqual(result["remaining_5h_pct"], 77)

    def test_refresh_claude_session_status_refreshes_cli_credentials_before_reading(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, ".claude")
            cred_path = os.path.join(cred_dir, ".credentials.json")
            os.makedirs(cred_dir, exist_ok=True)
            with open(cred_path, "w", encoding="utf-8") as handle:
                json.dump({"claudeAiOauth": {"accessToken": "stale"}}, handle)

            def auth_refresher(auth_home):
                self.assertEqual(auth_home, temp_dir)
                with open(cred_path, "w", encoding="utf-8") as handle:
                    json.dump({"claudeAiOauth": {"accessToken": "fresh"}}, handle)

            with mock.patch("src.claude_usage.fetch_claude_rate_limit_headers", return_value={"remaining_5h_pct": 77}) as fetch:
                result = claude_usage.refresh_claude_session_status(
                    {"authHome": temp_dir},
                    auth_refresher=auth_refresher,
                )

            fetch.assert_called_once_with("fresh")
            self.assertEqual(result["remaining_5h_pct"], 77)

    def test_claude_cli_credential_refresh_ignores_missing_cli(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            def missing_cli(*_args, **_kwargs):
                raise FileNotFoundError("claude")

            claude_usage._refresh_claude_cli_credentials(temp_dir, runner=missing_cli)

    def test_claude_cli_credential_refresh_uses_home_without_config_dir(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        claude_usage._refresh_claude_cli_credentials("/tmp/claude-home", runner=runner, env={})

        self.assertEqual(calls[0][0], ["claude", "auth", "status"])
        self.assertEqual(calls[0][1]["env"]["HOME"], "/tmp/claude-home")
        self.assertEqual(calls[0][1]["env"]["ANTHROPIC_CONFIG_DIR"], "/tmp/claude-home")
        self.assertNotIn("CLAUDE_CONFIG_DIR", calls[0][1]["env"])

    def test_normalize_codex_rate_limit_snapshot(self):
        result = codex_usage.normalize_codex_rate_limit_snapshot({
            "limitId": "codex",
            "primary": {"usedPercent": 7, "windowDurationMins": 300, "resetsAt": 1779476398},
            "secondary": {"usedPercent": 34, "windowDurationMins": 10080, "resetsAt": 1779889892},
            "credits": {"hasCredits": False, "unlimited": False, "balance": "0"},
            "planType": "plus",
        })

        self.assertEqual(result["remaining_5h_pct"], 93)
        self.assertEqual(result["remaining_week_pct"], 66)
        self.assertIsNone(result["credits"])
        self.assertEqual(result["reset_5h_at"], self.format_local_reset(1779476398))
        self.assertEqual(result["reset_week_at"], self.format_local_reset(1779889892))
        self.assertEqual(result["source_ref"], "api:codex-app-server-rate-limits")

    def test_fetch_codex_rate_limits_reads_app_server_jsonrpc(self):
        process = _FakeProcess([
            json.dumps({"id": 1, "result": {"codexHome": "/tmp/codex"}}) + "\n",
            json.dumps({"method": "remoteControl/status/changed", "params": {"status": "disabled"}}) + "\n",
            json.dumps({
                "id": 2,
                "result": {
                    "rateLimitsByLimitId": {
                        "codex": {
                            "limitId": "codex",
                            "primary": {"usedPercent": 12, "windowDurationMins": 300},
                            "secondary": {"usedPercent": 40, "windowDurationMins": 10080},
                        }
                    }
                },
            }) + "\n",
        ])
        captured = {}

        def popen_factory(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return process

        result = codex_usage.fetch_codex_rate_limits(
            {"authHome": "/tmp/codex-home"},
            popen_factory=popen_factory,
        )

        self.assertEqual(captured["argv"], ["codex", "app-server", "--listen", "stdio://"])
        self.assertEqual(captured["env"]["CODEX_HOME"], "/tmp/codex-home")
        self.assertEqual(result["remaining_5h_pct"], 88)
        self.assertEqual(result["remaining_week_pct"], 60)
        self.assertTrue(process.terminated)
        self.assertIn('"method":"initialize"', process.stdin.writes[0])
        self.assertIn('"method":"account/rateLimits/read"', process.stdin.writes[1])

    def test_fetch_codex_rate_limit_diagnostic_reports_failures(self):
        self.assertEqual(
            codex_usage.fetch_codex_rate_limit_diagnostic({})["reason"],
            "missing_auth_home",
        )

        def missing_cli(_argv, **_kwargs):
            raise FileNotFoundError("codex")

        diagnostic = codex_usage.fetch_codex_rate_limit_diagnostic(
            {"authHome": "/tmp/codex-home"},
            popen_factory=missing_cli,
        )
        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["reason"], "codex_cli_not_found")

        process = _FakeProcess([
            json.dumps({"id": 1, "error": {"message": "nope"}}) + "\n",
        ])
        diagnostic = codex_usage.fetch_codex_rate_limit_diagnostic(
            {"authHome": "/tmp/codex-home"},
            popen_factory=lambda _argv, **_kwargs: process,
        )
        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["reason"], "initialize_failed")

    def test_fetch_codex_rate_limit_diagnostic_reports_missing_rate_limits(self):
        process = _FakeProcess([
            json.dumps({"id": 1, "result": {"codexHome": "/tmp/codex"}}) + "\n",
            json.dumps({"id": 2, "result": {}}) + "\n",
        ])

        diagnostic = codex_usage.fetch_codex_rate_limit_diagnostic(
            {"authHome": "/tmp/codex-home"},
            popen_factory=lambda _argv, **_kwargs: process,
        )

        self.assertFalse(diagnostic["ok"])
        self.assertEqual(diagnostic["reason"], "missing_rate_limits")

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
        self.assertEqual(result["ANTHROPIC_CONFIG_DIR"], r"C:\Users\Test\AppData\Local\cdx\claude-home")
        self.assertNotIn("CLAUDE_CONFIG_DIR", result)
        self.assertEqual(result["CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS"], "1")
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

    def test_probe_provider_auth_uses_resolved_command_path(self):
        session = {
            "name": "main",
            "provider": "codex",
            "authHome": "/tmp/codex-home",
        }
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(stdout="Logged in using ChatGPT\n", stderr="")

        with mock.patch("src.provider_runtime.shutil.which", return_value="C:/nvm4w/nodejs/codex.cmd"):
            with mock.patch("src.provider_runtime.subprocess.run", side_effect=fake_run):
                self.assertTrue(provider_runtime._probe_provider_auth(session, env_override={"PATH": "C:/nvm4w/nodejs"}))

        self.assertEqual(calls[0][0][0], "C:/nvm4w/nodejs/codex.cmd")

    def test_probe_provider_auth_short_circuits_when_codex_auth_file_has_tokens(self):
        with tempfile.TemporaryDirectory(prefix="cdx-codex-") as temp_dir:
            with open(os.path.join(temp_dir, "auth.json"), "w", encoding="utf-8") as handle:
                handle.write("{\"tokens\": {\"access_token\": \"codex-access-token\"}}\n")

            session = {
                "name": "main",
                "provider": "codex",
                "authHome": temp_dir,
            }

            with mock.patch("src.provider_runtime.subprocess.run", side_effect=AssertionError("should not probe")):
                self.assertTrue(provider_runtime._probe_provider_auth(session))

    def test_probe_provider_auth_does_not_trust_empty_codex_auth_file(self):
        with tempfile.TemporaryDirectory(prefix="cdx-codex-") as temp_dir:
            with open(os.path.join(temp_dir, "auth.json"), "w", encoding="utf-8") as handle:
                handle.write("{\"tokens\": {}}\n")

            session = {
                "name": "main",
                "provider": "codex",
                "authHome": temp_dir,
            }

            def fake_run(_argv, **_kwargs):
                return SimpleNamespace(stdout="Not logged in\n", stderr="")

            with mock.patch("src.provider_runtime.subprocess.run", side_effect=fake_run):
                self.assertFalse(provider_runtime._probe_provider_auth(session))

    def test_claude_login_uses_profile_email_hint_when_available(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            with open(os.path.join(temp_dir, ".claude.json"), "w", encoding="utf-8") as handle:
                json.dump({"oauthAccount": {"emailAddress": "user@example.com"}}, handle)

            spec = provider_runtime._build_auth_action_spec({
                "name": "work",
                "provider": "claude",
                "authHome": temp_dir,
            }, "login")

        self.assertEqual(spec["args"], ["auth", "login", "--email", "user@example.com"])

    def test_claude_auth_probe_uses_anthropic_oauth_token_when_available(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, "credentials")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, "default.json"), "w", encoding="utf-8") as handle:
                json.dump({"type": "oauth_token", "access_token": "secret"}, handle)

            spec = provider_runtime._build_login_status_spec({
                "name": "work",
                "provider": "claude",
                "authHome": temp_dir,
            })

        self.assertEqual(spec["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "secret")
        self.assertEqual(spec["env"]["ANTHROPIC_PROFILE"], "default")

    def test_probe_provider_auth_short_circuits_when_claude_cli_oauth_token_exists(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, ".claude")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, ".credentials.json"), "w", encoding="utf-8") as handle:
                json.dump({"claudeAiOauth": {"accessToken": "secret"}}, handle)

            session = {
                "name": "work",
                "provider": "claude",
                "authHome": temp_dir,
            }

            with mock.patch("src.provider_runtime.subprocess.run", side_effect=AssertionError("should not probe")):
                self.assertTrue(provider_runtime._probe_provider_auth(session))

    def test_probe_provider_auth_does_not_trust_invalid_claude_setup_token(self):
        with tempfile.TemporaryDirectory(prefix="cdx-claude-") as temp_dir:
            cred_dir = os.path.join(temp_dir, "credentials")
            os.makedirs(cred_dir, exist_ok=True)
            with open(os.path.join(cred_dir, "default.json"), "w", encoding="utf-8") as handle:
                json.dump({"type": "oauth_token", "access_token": "<token>\x1b[39m"}, handle)

            session = {
                "name": "work",
                "provider": "claude",
                "authHome": temp_dir,
            }

            def fake_run(*_args, **_kwargs):
                return SimpleNamespace(stdout='{"loggedIn": false}\n', stderr="")

            with mock.patch("src.provider_runtime.subprocess.run", side_effect=fake_run):
                self.assertFalse(provider_runtime._probe_provider_auth(session))

    def test_build_launch_spec_validates_initial_prompt(self):
        session = {
            "name": "main",
            "provider": "codex",
            "authHome": "/tmp/codex-home",
        }

        with self.assertRaisesRegex(CdxError, "must be a string"):
            provider_runtime._build_launch_spec(session, initial_prompt=object())
        with self.assertRaisesRegex(CdxError, "exceeds maximum"):
            provider_runtime._build_launch_spec(session, initial_prompt="x" * 32769)

        spec = provider_runtime._build_launch_spec(session, initial_prompt="resume")
        self.assertIn("resume", spec["fallback"]["args"])

    def test_build_launch_spec_uses_fast_as_low_effort_without_power(self):
        codex = {
            "name": "main",
            "provider": "codex",
            "authHome": "/tmp/codex-home",
            "launch": {"fast": True},
        }
        claude = {
            "name": "claude",
            "provider": "claude",
            "authHome": "/tmp/claude-home",
            "launch": {"fast": True},
        }

        codex_spec = provider_runtime._build_launch_spec(codex)
        claude_spec = provider_runtime._build_launch_spec(claude)

        self.assertIn('model_reasoning_effort="low"', codex_spec["fallback"]["args"])
        self.assertIn("--effort", claude_spec["fallback"]["args"])
        self.assertIn("low", claude_spec["fallback"]["args"])

    def test_build_launch_spec_supports_antigravity(self):
        session = {
            "name": "agy1",
            "provider": "antigravity",
            "authHome": "/tmp/agy-home",
            "launch": {"permission": "full"},
        }

        spec = provider_runtime._build_launch_spec(session, cwd="/tmp/repo", initial_prompt="resume this")

        self.assertEqual(spec["fallback"]["command"], "agy")
        self.assertEqual(spec["fallback"]["args"], ["--dangerously-skip-permissions", "--prompt-interactive", "resume this"])
        self.assertEqual(spec["fallback"]["options"]["cwd"], "/tmp/repo")
        self.assertEqual(spec["fallback"]["options"]["env"]["HOME"], "/tmp/agy-home")

    def test_build_launch_spec_maps_antigravity_review_to_sandbox(self):
        session = {
            "name": "agy1",
            "provider": "antigravity",
            "authHome": "/tmp/agy-home",
            "launch": {"permission": "review"},
        }

        spec = provider_runtime._build_launch_spec(session, cwd="/tmp/repo")

        self.assertEqual(spec["fallback"]["command"], "agy")
        self.assertEqual(spec["fallback"]["args"], ["--sandbox"])

    def test_build_launch_spec_supports_ollama(self):
        session = {
            "name": "local",
            "provider": "ollama",
            "authHome": "/tmp/ollama-home",
            "launch": {"model": "llama3.2", "power": "xhigh", "permission": "full"},
        }

        spec = provider_runtime._build_launch_spec(session, cwd="/tmp/repo", initial_prompt="hello")

        self.assertEqual(spec["fallback"]["command"], "ollama")
        self.assertEqual(
            spec["fallback"]["args"],
            ["run", "llama3.2", "--think", "high", "--experimental-yolo", "hello"],
        )
        self.assertEqual(spec["fallback"]["options"]["cwd"], "/tmp/repo")
        self.assertEqual(spec["fallback"]["options"]["env"]["OLLAMA_NOHISTORY"], "1")

    def test_linux_launch_spec_uses_util_linux_script_command_form(self):
        session = {
            "name": "claude",
            "provider": "claude",
            "authHome": "/tmp/claude-home",
        }

        with mock.patch("src.provider_runtime.sys.platform", "linux"):
            spec = provider_runtime._build_launch_spec(session, cwd="/tmp/repo", initial_prompt="resume this")

        self.assertEqual(spec["command"], "script")
        self.assertEqual(spec["args"][:3], ["-q", "-F", "-c"])
        self.assertIn("claude --name claude 'resume this'", spec["args"][3])
        self.assertTrue(spec["args"][4].endswith(".log"))

    def test_build_headless_launch_spec_uses_codex_exec_json(self):
        session = {
            "name": "main",
            "provider": "codex",
            "authHome": "/tmp/codex-home",
            "launch": {"model": "gpt-test", "power": "high", "permission": "auto"},
        }

        spec = provider_runtime._build_headless_launch_spec(session, cwd="/tmp/repo", initial_prompt="do it")

        self.assertEqual(spec["command"], "codex")
        self.assertEqual(spec["args"][:4], ["exec", "--json", "-C", "/tmp/repo"])
        self.assertIn("-m", spec["args"])
        self.assertIn("gpt-test", spec["args"])
        self.assertIn('model_reasoning_effort="high"', spec["args"])
        self.assertIn("-s", spec["args"])
        self.assertIn("workspace-write", spec["args"])
        self.assertIn('approval_policy="never"', spec["args"])
        self.assertIn("do it", spec["args"])
        self.assertEqual(spec["options"]["env"]["CODEX_HOME"], "/tmp/codex-home")

    def test_build_headless_launch_spec_uses_claude_print_json(self):
        session = {
            "name": "claude",
            "provider": "claude",
            "authHome": "/tmp/claude-home",
            "launch": {"model": "sonnet", "power": "low", "permission": "review"},
        }

        spec = provider_runtime._build_headless_launch_spec(session, cwd="/tmp/repo", initial_prompt="do it")

        self.assertEqual(spec["command"], "claude")
        self.assertEqual(spec["args"][:3], ["--print", "--output-format", "json"])
        self.assertIn("--model", spec["args"])
        self.assertIn("sonnet", spec["args"])
        self.assertIn("--permission-mode", spec["args"])
        self.assertIn("plan", spec["args"])
        self.assertIn("do it", spec["args"])
        self.assertEqual(spec["options"]["cwd"], "/tmp/repo")
        self.assertEqual(spec["options"]["env"]["HOME"], "/tmp/claude-home")

    def test_run_usage_extracts_claude_json_usage(self):
        with tempfile.TemporaryDirectory(prefix="cdx-usage-") as temp_dir:
            path = os.path.join(temp_dir, "stdout.log")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "result": "done",
                    "usage": {
                        "input_tokens": 12,
                        "cache_creation_input_tokens": 3,
                        "cache_read_input_tokens": 5,
                        "output_tokens": 7,
                    },
                }, handle)

            self.assertEqual(run_usage.extract_run_usage("claude", path), {
                "input_tokens": 20,
                "output_tokens": 7,
                "reasoning_tokens": None,
                "total_tokens": 27,
            })

    def test_run_usage_extracts_latest_jsonl_usage(self):
        with tempfile.TemporaryDirectory(prefix="cdx-usage-") as temp_dir:
            path = os.path.join(temp_dir, "stdout.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "started"}) + "\n")
                handle.write(json.dumps({
                    "type": "usage",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 4,
                        "output_tokens_details": {"reasoning_tokens": 2},
                        "total_tokens": 14,
                    },
                }) + "\n")

            self.assertEqual(run_usage.extract_run_usage("codex", path), {
                "input_tokens": 10,
                "output_tokens": 4,
                "reasoning_tokens": 2,
                "total_tokens": 14,
            })


if __name__ == "__main__":
    unittest.main()
