"""Desktop capability and toast delivery, as `cdx tray doctor` reports them.

Both of these fail silently on the platform that gates them, which is the only
reason they earn a diagnostic line: a missing Start Menu shortcut makes the
Windows notification API succeed and show nothing, and a desktop with no
StatusNotifierItem watcher lets a companion start and never appear.
"""
import os

from cli_test_support import CliTestBase

from src.tray_capability import desktop_capability, shortcut_path, toast_capability
from src.tray_shortcut import APP_USER_MODEL_ID, create


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


class ShortcutCreationTest(CliTestBase):
    def test_it_is_not_attempted_off_windows(self):
        result = create("/opt/cdx-tray", env={}, system="Darwin")
        self.assertFalse(result["created"])
        self.assertIn("not required", result["reason"])

    def test_a_shortcut_without_its_identifier_is_not_reported_as_created(self):
        """The whole point of the shortcut is the AppUserModelID. A file that
        exists without one is a shortcut Windows will not route a toast
        through, so calling it created would be the silent failure this exists
        to end."""
        temp_dir = self.make_temp_dir()
        result = create(
            "C:/cdx-tray.exe", env={"APPDATA": temp_dir}, system="Windows",
            run=lambda *_args: "",
        )
        self.assertFalse(result["created"])
        self.assertIn("AppUserModelID", result["reason"])

    def test_a_failure_to_write_is_reported_not_raised(self):
        """An install that otherwise worked must not fail over a shortcut. The
        companion runs either way; only its toasts would go nowhere."""
        temp_dir = self.make_temp_dir()

        def explode(*_args):
            raise OSError("powershell is not here")

        result = create("C:/cdx-tray.exe", env={"APPDATA": temp_dir}, system="Windows", run=explode)
        self.assertFalse(result["created"])
        self.assertIn("powershell", result["reason"])

    def test_a_confirmed_identifier_reads_as_created(self):
        temp_dir = self.make_temp_dir()
        result = create(
            "C:/cdx-tray.exe", env={"APPDATA": temp_dir}, system="Windows",
            run=lambda *_args: APP_USER_MODEL_ID,
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["path"], shortcut_path({"APPDATA": temp_dir}))


class WindowsAumidTest(CliTestBase):
    """Which identifier a Windows toast is sent under.

    Windows resolves an AppUserModelID through a Start Menu shortcut and drops
    an unresolvable one in silence — no error, no toast. So claiming CDX's own
    identifier before the shortcut exists would be strictly worse than a toast
    attributed to PowerShell.
    """

    def test_powershells_identifier_is_used_until_cdx_has_a_shortcut(self):
        from src.notify import windows_aumid
        temp_dir = self.make_temp_dir()
        self.assertIn("WindowsPowerShell", windows_aumid({"APPDATA": temp_dir}))

    def test_cdx_claims_its_own_identifier_once_the_shortcut_exists(self):
        from src.notify import windows_aumid
        from src.tray_shortcut import APP_USER_MODEL_ID
        temp_dir = self.make_temp_dir()
        path = shortcut_path({"APPDATA": temp_dir})
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"shortcut")
        self.assertEqual(windows_aumid({"APPDATA": temp_dir}), APP_USER_MODEL_ID)


class WindowsAutostartTest(CliTestBase):
    """The Windows autostart branch, exercised on every platform.

    On Windows the artifact is the HKCU Run key rather than a file, so the
    behaviour cannot be covered by the file-based path the other platforms take
    — and it went through CI unexercised until a Windows runner failed on it.
    Driving it through the injected runner covers it everywhere, and without
    writing to any real registry.
    """

    def _registry(self):
        keys = {}

        class Result:
            def __init__(self, returncode):
                self.returncode = returncode

        def run(argv, **_kwargs):
            action, name = argv[1], argv[argv.index("/v") + 1]
            if action == "add":
                keys[name] = argv[-2]
                return Result(0)
            if action == "delete":
                return Result(0 if keys.pop(name, None) is not None else 1)
            return Result(0 if name in keys else 1)

        return run, keys

    def test_it_is_off_until_asked_then_reversible(self):
        from src.tray_autostart import disable, enable, status
        run, keys = self._registry()
        env = {"APPDATA": self.make_temp_dir()}

        self.assertFalse(status(env=env, system="Windows", run=run)["enabled"])
        enable(r"C:\cdx-tray.exe", env=env, system="Windows", run=run)
        self.assertTrue(status(env=env, system="Windows", run=run)["enabled"])
        # Idempotent: asking twice is not an error and not a second entry.
        enable(r"C:\cdx-tray.exe", env=env, system="Windows", run=run)
        self.assertEqual(len(keys), 1)
        disable(env=env, system="Windows", run=run)
        self.assertFalse(status(env=env, system="Windows", run=run)["enabled"])

    def test_the_artifact_names_the_registry_value_it_writes(self):
        """Reported so a user can find and remove it by hand, which a path they
        cannot see would not allow."""
        from src.tray_autostart import status
        run, _keys = self._registry()
        artifact = status(env={}, system="Windows", run=run)["artifact"]
        self.assertIn("CurrentVersion\\Run", artifact)
        self.assertTrue(artifact.endswith("CDXTray"))


class ReleaseTargetAgreementTest(CliTestBase):
    """The targets CDX asks for must be the ones the release actually builds.

    This is the test that would have caught it: CDX asked for
    x86_64-pc-windows-gnu while the workflow builds on windows-latest with the
    default MSVC toolchain, so no checksum was ever published under the name
    CDX looked for. Every Windows install refused, correctly and uselessly —
    the guard worked, the name was wrong.
    """

    def _workflow_targets(self):
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        text = open(
            os.path.join(root, ".github", "workflows", "build-tray-assets.yml"),
            encoding="utf-8",
        ).read()
        return set(re.findall(r"^\s*-\s*target:\s*(\S+)", text, re.MULTILINE))

    def test_every_target_cdx_installs_is_one_the_release_builds(self):
        from src.tray_install import TARGETS
        built = self._workflow_targets()
        self.assertTrue(built, "the workflow should declare a target matrix")
        for key, target in TARGETS.items():
            with self.subTest(platform=key):
                self.assertIn(target, built, f"{target} is asked for but never built")


class ArchiveShapeTest(CliTestBase):
    """Archives written as `tar -C dir .` carry a `.` member for the directory.

    That is what the release workflow produces, and rejecting it as an escape
    refused every published asset while the archive was perfectly safe. The
    guard still has to refuse a real escape.
    """

    def _archive(self, directory, arcnames):
        """An archive whose first member is the directory itself, as `tar -C dir .`
        writes it — a directory entry, not a file called `.`."""
        import tarfile
        payload = os.path.join(directory, "cdx-tray")
        with open(payload, "wb") as handle:
            handle.write(b"#!/bin/sh\n")
        archive = os.path.join(directory, "asset.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for name in arcnames:
                if name.endswith("."):
                    info = tarfile.TarInfo(name)
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    tar.addfile(info)
                else:
                    tar.add(payload, arcname=name)
        return archive

    def test_the_destination_itself_is_not_an_escape(self):
        from src.tray_install import _extract
        scratch = self.make_temp_dir()
        destination = self.make_temp_dir()
        archive = self._archive(scratch, [".", "./cdx-tray"])
        names = _extract(archive, destination)
        self.assertIn("./cdx-tray", names)

    def test_a_real_escape_is_still_refused(self):
        from src.tray_install import TrayInstallError, _extract
        scratch = self.make_temp_dir()
        destination = self.make_temp_dir()
        archive = self._archive(scratch, ["../escaped"])
        with self.assertRaises(TrayInstallError):
            _extract(archive, destination)
