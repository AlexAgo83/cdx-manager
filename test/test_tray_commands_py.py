"""`cdx tray` subcommands that write state: install, terminal, sort, plugin,
alerts, and the event spool a companion reads through `cdx`."""
import json
import os
from pathlib import Path
from unittest import mock

from cli_test_support import CliTestBase

from src.cli import main
from src.errors import CdxError
from src.session_service import create_session_service
from src.tray_events import publish
from src.tray_install import TrayInstallError
from src.tray_instance import lock_path
from src.tray_restart import stop_path

INSTALLED = {"target": "darwin-arm64", "cdx_version": "0.0.0", "executable": "/opt/cdx-tray", "sha256": "0" * 64}


class TrayCommandsTest(CliTestBase):
    def setUp(self):
        super().setUp()
        self.temp_dir = self.make_temp_dir()
        self.service = create_session_service({"base_dir": self.temp_dir})

    def run_tray(self, *argv, **ctx):
        io_obj = self.make_io()
        io_obj["stdin"] = {"isTTY": False}
        code = main(["tray", *argv], {**io_obj, "service": self.service, "env": {"CDX_HOME": self.temp_dir}, **ctx})
        out = io_obj["stdout"].getvalue()
        return code, json.loads(out) if "--json" in argv else out

    def install(self, *argv, spawn=None, autostart=None):
        with mock.patch("src.commands.tray.current_target", return_value="darwin-arm64"), \
                mock.patch("src.commands.tray.install", return_value=INSTALLED), \
                mock.patch("src.commands.tray.autostart_enable", autostart or mock.Mock()):
            return self.run_tray("install", "--json", *argv, spawn_detached=spawn or mock.Mock())

    def stop_env(self):
        return {
            "CDX_HOME": self.temp_dir,
            "TMPDIR": self.temp_dir,
            "LOCALAPPDATA": self.temp_dir,
            "XDG_RUNTIME_DIR": self.temp_dir,
        }

    def write_companion_pid(self, env, pid):
        path = Path(lock_path(env=env))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(pid), encoding="utf-8")

    def test_stop_running_companion(self):
        env = self.stop_env()
        self.write_companion_pid(env, os.getpid())

        def exit_after_request(pid, **kwargs):
            self.assertEqual(pid, os.getpid())
            self.assertEqual(Path(stop_path(env=env)).read_text(encoding="utf-8"), "stop")
            Path(lock_path(env=env)).unlink()
            return True

        with mock.patch("src.tray_restart.wait_for_exit", side_effect=exit_after_request):
            code, payload = self.run_tray("stop", "--json", env=env)
        self.assertEqual(code, 0)
        self.assertEqual(payload["action"], "tray.stop")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["was_running"])
        self.assertTrue(payload["stopped"])
        self.assertTrue(payload["applied"])
        self.assertEqual(payload["pid"], os.getpid())
        self.assertFalse(Path(stop_path(env=env)).exists())
        self.assertFalse(self.run_tray("stop", "--json", env=env)[1]["was_running"])

    def test_stop_already_stopped_companion(self):
        env = self.stop_env()
        code, payload = self.run_tray("stop", "--json", env=env)
        self.assertEqual(code, 0)
        self.assertFalse(payload["was_running"])
        self.assertFalse(payload["stopped"])
        self.assertFalse(payload["applied"])
        self.assertIn("No running", self.run_tray("stop", env=env)[1])
        self.assertFalse(Path(stop_path(env=env)).exists())

    def test_stop_stale_pid(self):
        env = self.stop_env()
        self.write_companion_pid(env, 999999999)
        Path(stop_path(env=env)).write_text("stop", encoding="utf-8")
        with mock.patch("src.tray_instance._is_alive", return_value=False), \
                mock.patch("src.tray_restart.request_stop") as request:
            code, payload = self.run_tray("stop", "--json", env=env)
        self.assertEqual(code, 0)
        self.assertFalse(payload["was_running"])
        self.assertFalse(payload["stopped"])
        request.assert_not_called()
        self.assertFalse(Path(stop_path(env=env)).exists())

    def test_stop_timeout_reports_running_companion(self):
        env = self.stop_env()
        self.write_companion_pid(env, os.getpid())
        with mock.patch("src.tray_restart.wait_for_exit", return_value=False):
            code, payload = self.run_tray("stop", "--json", env=env)
        self.assertEqual(code, 0)
        self.assertTrue(payload["was_running"])
        self.assertFalse(payload["stopped"])
        self.assertIn("did not stop", payload["reason"])
        self.assertEqual(payload["warnings"][0]["code"], "tray_companion_stop_pending")
        self.assertFalse(Path(stop_path(env=env)).exists())

    def test_stop_text_reports_success(self):
        with mock.patch("src.commands.tray.stop_running_companion", return_value={
            "was_running": True, "stopped": True, "pid": 123,
        }) as stop:
            code, output = self.run_tray("stop")
        self.assertEqual(code, 0)
        self.assertIn("Stopped the tray companion (pid 123)", output)
        stop.assert_called_once_with(env={"CDX_HOME": self.temp_dir})

    def test_stop_rejects_extra_arguments(self):
        for args in (("extra",), ("--unknown",)):
            with self.subTest(args=args), \
                    mock.patch("src.commands.tray.stop_running_companion") as stop, \
                    self.assertRaises(CdxError):
                self.run_tray("stop", *args)
            stop.assert_not_called()

    def test_install_refuses_without_a_published_companion(self):
        with mock.patch("src.commands.tray.current_target", return_value=None):
            code, payload = self.run_tray("install", "--json")
        self.assertEqual(code, 0)
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["warnings"][0]["code"], "tray_companion_not_available")

    def test_install_error_is_a_failure_not_a_crash(self):
        with mock.patch("src.commands.tray.current_target", return_value="darwin-arm64"), \
                mock.patch("src.commands.tray.install", side_effect=TrayInstallError("checksum mismatch")), \
                self.assertRaisesRegex(CdxError, "checksum mismatch"):
            self.run_tray("install")

    def test_non_interactive_install_starts_it_and_asks_nothing_else(self):
        spawn = mock.Mock()
        code, payload = self.install(spawn=spawn)
        self.assertEqual(code, 0)
        spawn.assert_called_once()
        self.assertTrue(payload["started"])
        self.assertFalse(payload["autostart"])
        self.assertFalse(payload["alerts"])

    def test_a_companion_that_fails_to_start_stays_installed(self):
        code, payload = self.install(spawn=mock.Mock(side_effect=OSError("no display")))
        self.assertEqual(code, 0)
        self.assertTrue(payload["applied"])
        self.assertFalse(payload["started"])

    def test_yes_enables_autostart_and_alerts_for_hookable_sessions(self):
        self.service["create_session"]("claw", "claude")
        self.service["create_session"]("local", "ollama")
        autostart = mock.Mock()
        code, payload = self.install("--yes", autostart=autostart)
        self.assertEqual(code, 0)
        autostart.assert_called_once()
        self.assertTrue(payload["autostart"])
        self.assertEqual(payload["alerts_sessions"], ["claw"])

    def test_no_flags_win_over_yes(self):
        autostart = mock.Mock()
        code, payload = self.install("--yes", "--no-autostart", "--no-alerts", autostart=autostart)
        autostart.assert_not_called()
        self.assertFalse(payload["autostart"])
        self.assertFalse(payload["alerts"])

    def test_terminal_refuses_a_command_and_stores_nothing(self):
        code, payload = self.run_tray("terminal", "set", "iTerm; rm -rf ~", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(payload["warnings"][0]["code"], "tray_terminal_invalid")
        self.assertIsNone(self.run_tray("terminal", "--json")[1]["terminal"])

    def test_terminal_set_then_clear(self):
        self.assertEqual(self.run_tray("terminal", "set", "Ghostty", "--json")[1]["terminal"], "Ghostty")
        payload = self.run_tray("terminal", "clear", "--json")[1]
        self.assertIsNone(payload["terminal"])
        self.assertTrue(payload["applied"])

    def test_sort_round_trip_and_refusal(self):
        self.assertEqual(self.run_tray("sort", "--json")[1]["sort"], "capacity")
        self.assertEqual(self.run_tray("sort", "set", "recent", "--json")[1]["sort"], "recent")
        with self.assertRaises(CdxError):
            self.run_tray("sort", "set", "random")

    def test_plugin_unknown_is_refused(self):
        code, payload = self.run_tray("plugin", "enable", "nope", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(payload["warnings"][0]["code"], "tray_plugin_unknown")

    def test_plugin_enable_then_disable(self):
        with mock.patch("src.logics_view.resolve_logics_manager", return_value=None):
            self.assertEqual(self.run_tray("plugin", "enable", "logics", "--json")[1]["enabled"], ["logics"])
            self.assertEqual(self.run_tray("plugin", "disable", "logics", "--json")[1]["enabled"], [])

    def test_alerts_mute_and_unmute(self):
        self.assertFalse(self.run_tray("alerts", "off", "--json")[1]["enabled"])
        self.assertTrue(self.run_tray("alerts", "on", "--json")[1]["enabled"])

    def test_events_are_read_then_acknowledged(self):
        # Nothing is spooled until a companion has said it is listening.
        self.assertFalse(publish(self.temp_dir, "work", "Turn finished"))
        self.run_tray("heartbeat", "--json")
        self.assertTrue(publish(self.temp_dir, "work", "Turn finished", event_id="e1"))
        events = self.run_tray("events", "--json")[1]["events"]
        self.assertEqual([event["id"] for event in events], ["e1"])
        self.assertEqual(self.run_tray("ack", "e1", "--json")[1]["acknowledged"], 1)
        self.assertEqual(self.run_tray("events", "--json")[1]["events"], [])
        self.assertIn("No pending", self.run_tray("events")[1])

    def test_ack_needs_an_id(self):
        with self.assertRaises(CdxError):
            self.run_tray("ack")
