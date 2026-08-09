"""Tests for login, logout, reset, notify.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta
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
from src.cli_commands import _extract_claude_oauth_token
from src.errors import CdxError
from src.session_service import create_session_service


class AuthCommandTests(CliTestBase):

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

    def test_ready_reports_the_session_whose_reset_is_due(self):
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

        next_io = self.make_io()
        self.assertEqual(main(["ready", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": spawn_sync,
        }), 0)
        payload = json.loads(next_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["event"]["ready"])
        self.assertEqual(payload["event"]["session"], "main")

    def test_notify_no_longer_exposes_the_quota_reset_surface(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        io = self.make_io()
        # `cdx notify` now belongs to agent notifications: the old flags must not
        # reach the quota flow, and the hook target must never fail its caller.
        self.assertEqual(main(["notify", "main", "--at-reset", "--once"], {
            **io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": lambda *_a, **_k: subprocess.CompletedProcess([], 0, "", ""),
        }), 0)
        self.assertNotIn("reset is due", io["stdout"].getvalue())

    def test_ready_ignores_currently_available_sessions(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("active")
        service["record_status"]("active", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:01:00+00:00",
        })

        next_io = self.make_io()
        self.assertEqual(main(["ready", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        }), 0)

        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["event"]["ready"])
        self.assertIsNone(payload["event"]["session"])
        self.assertEqual(payload["event"]["message"], "No upcoming session reset available")

    def test_ready_registers_an_os_job(self):
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
                self.assertEqual(main(["ready", "--json"], {
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

    def test_logged_out_sessions_are_never_candidates(self):
        names, _ = self._ranked([
            self._row("out", auth_status="logged_out", available_pct=99),
            self._row("in", available_pct=10),
        ])

        # `cdx select` without --require-ready used to be able to return one.
        self.assertEqual(names, ["in"])

    def test_ready_ignores_disabled_sessions(self):
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
        self.assertEqual(main(["ready", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
        }), 0)

        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["event"]["ready"])
        self.assertEqual(payload["event"]["session"], "blocked")
        self.assertEqual(payload["event"]["message"], "Waiting for blocked")

