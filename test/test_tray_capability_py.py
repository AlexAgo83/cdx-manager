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


class PublishedLedgerFallbackTest(CliTestBase):
    """A package cannot ship the checksums for its own release.

    The tray assets are built after the tag exists, so their checksums are
    recorded afterwards and a package built at tag time ships a ledger that
    stops at the previous release. Without a fallback, `cdx tray install`
    refuses the companion for the very version the user is running — which is
    what a real install of 0.18.1 did.
    """

    def _ledger(self, directory, releases):
        import json
        path = os.path.join(directory, "ledger.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"releases": releases}, handle)
        return path

    def test_the_published_ledger_answers_when_the_local_one_cannot(self):
        import json

        from src.tray_install import expected_checksum
        scratch = self.make_temp_dir()
        local = self._ledger(scratch, {"v9.9.8": {"tray_assets": {"t": "old"}}})

        def download(url, destination):
            self.assertIn("v9.9.9", url)
            with open(destination, "w", encoding="utf-8") as handle:
                json.dump({"releases": {"v9.9.9": {"tray_assets": {"t": "fetched"}}}}, handle)

        self.assertEqual(
            expected_checksum("9.9.9", "t", ledger_path=local, download=download),
            "fetched",
        )

    def test_a_local_entry_wins_and_fetches_nothing(self):
        """The committed checksum is the stronger claim — written before the
        asset existed — so it is never traded for one fetched beside the asset."""
        from src.tray_install import expected_checksum
        scratch = self.make_temp_dir()
        local = self._ledger(scratch, {"v9.9.9": {"tray_assets": {"t": "committed"}}})

        def download(_url, _destination):
            raise AssertionError("the local entry should have answered")

        self.assertEqual(
            expected_checksum("9.9.9", "t", ledger_path=local, download=download),
            "committed",
        )

    def test_an_unreachable_published_ledger_is_still_a_refusal(self):
        from src.tray_install import expected_checksum
        scratch = self.make_temp_dir()
        local = self._ledger(scratch, {})

        def download(_url, _destination):
            raise OSError("no network")

        self.assertIsNone(
            expected_checksum("9.9.9", "t", ledger_path=local, download=download)
        )


class CompanionAlignmentTest(CliTestBase):
    """`cdx update` has to bring the companion with it.

    The companion is a separate artifact on a separate release, so it drifts
    unless something moves it. Nothing did: the user updated CDX and had to
    notice the mismatch and reinstall by hand, which is exactly what
    `item_081` AC2 says must not happen.
    """

    def _asset(self, directory):
        import hashlib
        import tarfile
        payload = os.path.join(directory, "cdx-tray")
        with open(payload, "wb") as handle:
            handle.write(b"#!/bin/sh\nexit 0\n")
        os.chmod(payload, 0o755)
        archive = os.path.join(directory, "asset.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(payload, arcname="cdx-tray")
        return archive, hashlib.sha256(open(archive, "rb").read()).hexdigest()

    def _ledger(self, directory, digest):
        import json
        path = os.path.join(directory, "ledger.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"releases": {
                "v1.0.0": {"tray_assets": {"t": digest}},
                "v2.0.0": {"tray_assets": {"t": digest}},
            }}, handle)
        return path

    def _installed(self, base_dir, scratch, version):
        import shutil

        from src.tray_install import install
        archive, digest = self._asset(scratch)
        ledger = self._ledger(scratch, digest)
        install(
            base_dir, version, target="t", ledger_path=ledger,
            download=lambda _url, dest: shutil.copyfile(archive, dest),
        )
        return archive, ledger

    def test_nothing_installed_is_not_a_failure(self):
        from src.tray_install import align_companion
        result = align_companion(self.make_temp_dir(), "2.0.0")
        self.assertFalse(result["aligned"])
        self.assertIn("no companion", result["reason"])

    def test_an_aligned_companion_is_left_alone(self):
        from src.tray_install import align_companion
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        _archive, ledger = self._installed(base, scratch, "1.0.0")
        result = align_companion(base, "1.0.0", ledger_path=ledger)
        self.assertFalse(result["aligned"])
        self.assertEqual(result["reason"], "already aligned")

    def test_a_drifted_companion_is_moved(self):
        import shutil

        from src.tray_install import align_companion, read_state
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        archive, ledger = self._installed(base, scratch, "1.0.0")
        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t",
            download=lambda _url, dest: shutil.copyfile(archive, dest),
            # The subject is the ordering, not whether this host can execute the
            # stand-in payload: a `#!/bin/sh` file is not runnable on Windows,
            # which failed the probe for a reason that has nothing to do with
            # what the test is asking.
            probe=lambda _executable: True,
            # Doubles, and not only for speed: without them this reaches the
            # lock of whatever companion is running on the machine executing
            # the suite and asks it to stop.
            stop=self.no_tray_running,
            start=self.starts,
        )
        self.assertTrue(result["aligned"], result)
        self.assertEqual(read_state(base)["cdx_version"], "2.0.0")
        self.assertFalse(result["restarted"], "nothing was running, so nothing is started")

    def test_a_failure_is_reported_and_the_old_one_kept(self):
        """The CDX update has already succeeded by then. Failing it because a
        companion could not be replaced would undo a good outcome."""
        from src.tray_install import align_companion, read_state
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        _archive, ledger = self._installed(base, scratch, "1.0.0")

        def refuse(_url, _dest):
            raise OSError("no network")

        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t", download=refuse,
            stop=self.no_tray_running, start=self.starts,
        )
        self.assertFalse(result["aligned"])
        self.assertEqual(result["previous"], "1.0.0")
        self.assertEqual(read_state(base)["cdx_version"], "1.0.0", "the working one stays")

    # --- doubles for the running companion ---------------------------------

    @staticmethod
    def no_tray_running(env=None):
        return {"stopped": False, "was_running": False, "reason": "no tray companion is running"}

    @staticmethod
    def stopped(env=None):
        return {"stopped": True, "was_running": True, "pid": 4242}

    @staticmethod
    def refuses_to_stop(env=None):
        return {"stopped": False, "was_running": True, "pid": 4242, "reason": "it did not stop in time"}

    @staticmethod
    def starts(executable, spawn=None, env=None, **_kwargs):
        return {"started": True, "pid": 4243}

    def test_a_running_companion_is_stopped_replaced_and_started_again(self):
        import shutil

        from src.tray_install import align_companion, read_state
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        archive, ledger = self._installed(base, scratch, "1.0.0")
        launched = []
        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t",
            download=lambda _url, dest: shutil.copyfile(archive, dest),
            probe=lambda _executable: True,
            stop=self.stopped,
            start=lambda executable, **kwargs: launched.append(executable) or {"started": True, "pid": 1},
        )
        self.assertTrue(result["aligned"], result)
        self.assertTrue(result["restarted"])
        self.assertEqual(read_state(base)["cdx_version"], "2.0.0")
        # Started on the replacement, not on the binary it replaced.
        self.assertEqual(launched, [read_state(base)["executable"]])

    def test_a_companion_that_will_not_stop_leaves_the_files_alone(self):
        """A user reading a tray menu is not a process to terminate over a
        version number, and a half-replaced install is worse than an old one."""
        import shutil

        from src.tray_install import align_companion, read_state
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        archive, ledger = self._installed(base, scratch, "1.0.0")
        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t",
            download=lambda _url, dest: shutil.copyfile(archive, dest),
            probe=lambda _executable: True,
            stop=self.refuses_to_stop,
            start=self.starts,
        )
        self.assertFalse(result["aligned"])
        self.assertIn("did not stop", result["reason"])
        self.assertEqual(read_state(base)["cdx_version"], "1.0.0", "nothing was replaced")

    def test_a_replacement_that_does_not_start_is_rolled_back_and_the_old_one_restarted(self):
        import shutil

        from src.tray_install import align_companion, read_state
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        archive, ledger = self._installed(base, scratch, "1.0.0")
        attempts = []

        def start(executable, **_kwargs):
            attempts.append(executable)
            # The replacement fails; whatever is tried next is the rollback.
            return {"started": len(attempts) > 1, "reason": "it exited immediately"}

        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t",
            download=lambda _url, dest: shutil.copyfile(archive, dest),
            probe=lambda _executable: True,
            stop=self.stopped,
            start=start,
        )
        self.assertFalse(result["aligned"], "a rollback is not an alignment")
        self.assertTrue(result["rolled_back"])
        self.assertTrue(result["restarted"], "the proven one is running again")
        self.assertEqual(read_state(base)["cdx_version"], "1.0.0")
        self.assertEqual(len(attempts), 2)

    def test_a_failed_update_restarts_the_companion_it_stopped(self):
        from src.tray_install import align_companion
        base, scratch = self.make_temp_dir(), self.make_temp_dir()
        _archive, ledger = self._installed(base, scratch, "1.0.0")

        def refuse(_url, _dest):
            raise OSError("no network")

        started = []
        result = align_companion(
            base, "2.0.0", ledger_path=ledger, target="t", download=refuse,
            stop=self.stopped,
            start=lambda executable, **kwargs: started.append(executable) or {"started": True},
        )
        self.assertFalse(result["aligned"])
        self.assertTrue(result["restarted"], "we stopped it, so we bring it back")
        self.assertEqual(len(started), 1)


class InstallStartupTest(CliTestBase):
    """What `install` does beyond installing, and what it refuses to do quietly.

    The criterion originally forbade startup outright. The objection behind it
    was silence — an install that adds a login item nobody asked for — so a
    prompt keeps the objection answered and drops the second command.
    """

    def test_a_non_interactive_install_does_not_acquire_a_login_item(self):
        """A script must not gain a startup entry by running an install."""
        from src.tray_autostart import status
        home = self.make_temp_dir()
        self.assertFalse(status(env={"HOME": home}, system="Darwin")["enabled"])

    def test_yes_answers_the_prompt_without_one(self):
        from src.tray_autostart import enable, status
        home = self.make_temp_dir()
        enable("/opt/CDX.app", env={"HOME": home}, system="Darwin")
        self.assertTrue(status(env={"HOME": home}, system="Darwin")["enabled"])

    def test_off_removes_what_it_wrote_and_nothing_else(self):
        import os

        from src.tray_autostart import artifact_path, disable, enable
        home = self.make_temp_dir()
        enable("/opt/CDX.app", env={"HOME": home}, system="Darwin")
        bystander = os.path.join(os.path.dirname(artifact_path(env={"HOME": home}, system="Darwin")), "other.plist")
        with open(bystander, "w", encoding="utf-8") as handle:
            handle.write("not ours")
        disable(env={"HOME": home}, system="Darwin")
        self.assertFalse(os.path.exists(artifact_path(env={"HOME": home}, system="Darwin")))
        self.assertTrue(os.path.exists(bystander), "a file CDX never wrote survives")


class CompanionStopTest(CliTestBase):
    """Asking a running companion to stop, and never insisting.

    The channel is a file the companion polls, chosen over a signal because it
    behaves identically on the three platforms. Everything here is about the
    cases where it does not work.
    """

    def _env(self):
        return {"TMPDIR": self.make_temp_dir(), "LOCALAPPDATA": self.make_temp_dir()}

    def test_nothing_running_is_not_a_failure(self):
        from src.tray_restart import stop_running_companion
        result = stop_running_companion(env=self._env())
        self.assertFalse(result["was_running"])
        self.assertFalse(result["stopped"])

    def test_a_stop_request_is_written_beside_the_lock(self):
        import os

        from src.tray_instance import lock_path
        from src.tray_restart import request_stop, stop_path
        env = self._env()
        self.assertTrue(request_stop(env=env))
        self.assertTrue(os.path.exists(stop_path(env=env)))
        self.assertEqual(os.path.dirname(stop_path(env=env)), os.path.dirname(lock_path(env=env)))

    def test_a_companion_that_stops_is_reported_as_stopped(self):
        import os

        from src.tray_instance import lock_path
        from src.tray_restart import stop_path, stop_running_companion
        env = self._env()
        path = lock_path(env=env)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))

        alive = iter([True, True, False])
        result = stop_running_companion(
            env=env, sleep=lambda _s: None, alive=lambda _pid: next(alive),
        )
        self.assertTrue(result["stopped"])
        self.assertEqual(result["pid"], os.getpid())
        # The request is withdrawn once honoured, or the replacement started a
        # moment later reads it and quits before drawing anything.
        self.assertFalse(os.path.exists(stop_path(env=env)))

    def test_a_companion_that_ignores_the_request_is_left_alone(self):
        import os

        from src.tray_instance import lock_path
        from src.tray_restart import stop_path, stop_running_companion
        env = self._env()
        path = lock_path(env=env)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # A pid that is genuinely alive, because the instance check reads the
        # real process table: a made-up number reads as a stale lock instead.
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))

        result = stop_running_companion(
            env=env, timeout=0.0, sleep=lambda _s: None, alive=lambda _pid: True,
        )
        self.assertFalse(result["stopped"])
        self.assertTrue(result["was_running"])
        self.assertIn("menu", result["reason"], "it says why, and what to do")
        # Withdrawn, so it does not stop the tray later at a moment nobody
        # connected to an update.
        self.assertFalse(os.path.exists(stop_path(env=env)))

    def test_a_stale_lock_is_not_a_running_companion(self):
        import os

        from src.tray_instance import lock_path
        from src.tray_restart import stop_running_companion
        env = self._env()
        path = lock_path(env=env)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("999999999")
        result = stop_running_companion(env=env, sleep=lambda _s: None)
        self.assertFalse(result["was_running"])

    def test_a_launch_that_never_registers_is_not_a_start(self):
        """Spawning is not evidence. A binary that exits immediately leaves a
        successful spawn and no tray."""
        from src.tray_restart import start_companion
        result = start_companion(
            "/nowhere/cdx-tray",
            spawn=lambda _command: None,
            verify=lambda env=None: {"pid": None},
            settle=lambda _s: None,
        )
        self.assertFalse(result["started"])
        self.assertIn("never registered", result["reason"])

    def test_a_launch_that_registers_is_a_start(self):
        from src.tray_restart import start_companion
        result = start_companion(
            "/nowhere/cdx-tray",
            spawn=lambda _command: None,
            verify=lambda env=None: {"pid": 77},
            settle=lambda _s: None,
        )
        self.assertTrue(result["started"])
        self.assertEqual(result["pid"], 77)

    def test_a_launch_that_cannot_spawn_says_so(self):
        from src.tray_restart import start_companion

        def refuse(_command):
            raise OSError("permission denied")

        result = start_companion("/nowhere/cdx-tray", spawn=refuse, settle=lambda _s: None)
        self.assertFalse(result["started"])
        self.assertIn("permission denied", result["reason"])
