"""`cdx tray` subcommands that write state: install, terminal, sort, plugin,
alerts, and the event spool a companion reads through `cdx`."""
import json
from unittest import mock

from cli_test_support import CliTestBase

from src.cli import main
from src.errors import CdxError
from src.session_service import create_session_service
from src.tray_events import publish
from src.tray_install import TrayInstallError

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
