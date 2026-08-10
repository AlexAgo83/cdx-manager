"""Desktop capability and toast delivery, as `cdx tray doctor` reports them.

Both of these fail silently on the platform that gates them, which is the only
reason they earn a diagnostic line: a missing Start Menu shortcut makes the
Windows notification API succeed and show nothing, and a desktop with no
StatusNotifierItem watcher lets a companion start and never appear.
"""
import os

from cli_test_support import CliTestBase

from src.tray_capability import desktop_capability, shortcut_path, toast_capability


class ToastCapabilityTest(CliTestBase):
    def test_off_windows_nothing_gates_a_toast(self):
        """Reported as "not required", not as a check that passed. Nothing was
        asked, so claiming a pass would be inventing an answer."""
        result = toast_capability(env={}, system="Darwin")
        self.assertTrue(result["present"])
        self.assertFalse(result["gated"])

    def test_a_missing_windows_shortcut_is_named_with_its_consequence(self):
        temp_dir = self.make_temp_dir()
        result = toast_capability(env={"APPDATA": temp_dir}, system="Windows")
        self.assertTrue(result["gated"])
        self.assertFalse(result["present"])
        self.assertIn("silently", result["detail"])

    def test_a_present_windows_shortcut_reads_as_ready(self):
        temp_dir = self.make_temp_dir()
        path = shortcut_path({"APPDATA": temp_dir})
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"shortcut")
        result = toast_capability(env={"APPDATA": temp_dir}, system="Windows")
        self.assertTrue(result["present"])

    def test_an_unresolvable_start_menu_is_not_reported_as_present(self):
        """No APPDATA means the location is unknown, which is not the same as
        a shortcut being there. Guessing "fine" would hide a real gap."""
        result = toast_capability(env={}, system="Windows")
        self.assertFalse(result["present"])
        self.assertIsNone(result["path"])


class DesktopCapabilityTest(CliTestBase):
    def test_macos_and_windows_always_have_a_tray(self):
        for system in ("Darwin", "Windows"):
            self.assertTrue(desktop_capability(env={}, system=system)["available"])

    def test_no_session_bus_is_not_a_desktop(self):
        result = desktop_capability(env={}, system="Linux")
        self.assertFalse(result["available"])
        self.assertIn("D-Bus", result["detail"])

    def test_a_bus_without_a_watcher_is_named_as_having_no_tray(self):
        """The interesting Linux case, and the one a real WSL session produces:
        the bus answers, and simply has no watcher on it."""
        result = desktop_capability(
            env={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
            system="Linux",
            run=lambda: 'string "org.freedesktop.DBus"\nstring "org.freedesktop.systemd1"\n',
        )
        self.assertFalse(result["available"])
        self.assertIn("no system tray", result["detail"])

    def test_a_watcher_on_the_bus_means_a_tray(self):
        result = desktop_capability(
            env={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
            system="Linux",
            run=lambda: 'string "org.kde.StatusNotifierWatcher"\n',
        )
        self.assertTrue(result["available"])

    def test_a_failed_probe_is_unknown_rather_than_absent(self):
        """`None` is a real answer. Reporting "no tray" would be a claim the
        probe never made, and it would send someone installing an extension
        they may already have."""
        def explode():
            raise OSError("dbus-send is not here")

        result = desktop_capability(
            env={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
            system="Linux",
            run=explode,
        )
        self.assertIsNone(result["available"])
