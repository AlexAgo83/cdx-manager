import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from src.cli import main
from src.errors import CdxError
from src.session_service import create_session_service


class _Stream:
    def __init__(self):
        self._buffer = io.StringIO()

    def write(self, value):
        self._buffer.write(value)

    def getvalue(self):
        return self._buffer.getvalue()


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

    def test_help_and_version_flags(self):
        help_io = self.make_io()
        version_io = self.make_io()

        self.assertEqual(main(["--help"], help_io), 0)
        self.assertIn("Usage:", help_io["stdout"].getvalue())

        self.assertEqual(main(["-v"], version_io), 0)
        self.assertRegex(version_io["stdout"].getvalue().strip(), r"^\d+\.\d+\.\d+$")

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
        rows = json.loads(global_io["stdout"].getvalue())
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
        row = json.loads(detail_io["stdout"].getvalue())
        self.assertEqual(row["session_name"], "main")
        self.assertEqual(row["available_pct"], 39)
        self.assertEqual(row["credits"], 453)
        self.assertEqual(row["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(row["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(row["reset_at"], "Apr 17 10:10")

    def test_invalid_status_syntax_raises_usage_error(self):
        with self.assertRaises(CdxError) as ctx:
            main(["status", "main", "extra"], self.make_io())
        self.assertIn("Usage: cdx status [name] [--json]", str(ctx.exception))

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
        self.assertEqual(json.loads(io_obj["stdout"].getvalue()), [])

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


if __name__ == "__main__":
    unittest.main()
