"""Tests for the tray snapshot contract and the `cdx tray` command surface.

The behaviours worth guarding here are the ones a native companion cannot fix
for itself: never fabricating a quota figure, never leaking a session name into
the closed-icon state, telling `stale` apart from `cannot refresh right now`,
and staying readable when the snapshot is newer than the reader.
"""

import hashlib
import json
import os
import shutil
import tarfile
from datetime import datetime, timedelta, timezone

from cli_test_support import CliTestBase

from src.cli import main
from src.errors import CdxError
from src.session_service import create_session_service
from src.tray_contract import (
    AUTH_LOCKED,
    FRESH,
    ICON_CRITICAL,
    ICON_LOW,
    ICON_OK,
    ICON_UNKNOWN,
    SCHEMA_MAJOR,
    SCHEMA_NAME,
    STALE,
    UNKNOWN,
    build_snapshot,
    icon_state_for_pct,
    read_snapshot,
    session_freshness,
)
from src.tray_install import (
    TrayInstallError,
    install,
    interrupted_update,
    read_state,
    uninstall,
    update,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _row(name="work", provider="codex", available_pct=80, age_seconds=0, active=False, **extra):
    updated_at = None if age_seconds is None else (NOW - timedelta(seconds=age_seconds)).isoformat()
    return {
        "session_name": name,
        "provider": provider,
        "available_pct": available_pct,
        "updated_at": updated_at,
        "active": active,
        "enabled": True,
        **extra,
    }


class TrayContractTest(CliTestBase):
    def test_icon_thresholds_and_unknown(self):
        self.assertEqual(icon_state_for_pct(80), ICON_OK)
        self.assertEqual(icon_state_for_pct(25), ICON_OK)
        self.assertEqual(icon_state_for_pct(24), ICON_LOW)
        self.assertEqual(icon_state_for_pct(5), ICON_LOW)
        self.assertEqual(icon_state_for_pct(4), ICON_CRITICAL)
        self.assertEqual(icon_state_for_pct(None), ICON_UNKNOWN)

    def test_freshness_uses_the_provider_ttl(self):
        # Codex caches for 300s, Claude for 600s: the same age is fresh for one
        # and stale for the other, which is why one global TTL would lie.
        self.assertEqual(session_freshness(_row(provider="codex", age_seconds=299), NOW)[0], FRESH)
        self.assertEqual(session_freshness(_row(provider="codex", age_seconds=301), NOW)[0], STALE)
        self.assertEqual(session_freshness(_row(provider="claude", age_seconds=301), NOW)[0], FRESH)

    def test_a_running_session_reports_auth_locked_not_stale(self):
        row = _row(provider="codex", age_seconds=3600, active=True)
        self.assertEqual(session_freshness(row, NOW)[0], AUTH_LOCKED)

    def test_a_session_that_never_reported_is_unknown_not_zero(self):
        state, age = session_freshness(_row(age_seconds=None), NOW)
        self.assertEqual(state, UNKNOWN)
        self.assertIsNone(age)
        session = build_snapshot([_row(available_pct=None, age_seconds=None)], NOW, "9.9.9")["sessions"][0]
        self.assertIsNone(session["available_pct"])
        self.assertEqual(session["state"], ICON_UNKNOWN)

    def test_icon_takes_the_most_urgent_session_and_leaks_nothing(self):
        snapshot = build_snapshot(
            [_row(name="roomy", available_pct=90), _row(name="empty", available_pct=2)],
            NOW,
            "9.9.9",
        )
        self.assertEqual(snapshot["icon"]["state"], ICON_CRITICAL)
        self.assertEqual(snapshot["icon"]["session_count"], 2)
        self.assertNotIn("empty", json.dumps(snapshot["icon"]))
        self.assertNotIn("2", json.dumps(snapshot["icon"]["state"]))

    def test_the_tooltip_says_the_state_in_words_and_never_a_session_name(self):
        # Two rules meet here. req_035 AC3 forbids exposing accounts before the
        # menu is opened; req_038 AC4 wants the tooltip to name the limiting
        # source and its reset. A tooltip appears on hover, with no click, and
        # shows up in a screen share, so it gets the words and not the name.
        snapshot = build_snapshot(
            [
                _row(name="secret-account", available_pct=3, reset_at="Aug 11 09:00", active=True,
                     age_seconds=9999),
                _row(name="other", available_pct=80),
            ],
            NOW,
            "9.9.9",
        )
        tooltip = snapshot["icon"]["tooltip"]
        self.assertIn("capacity critical", tooltip)
        self.assertIn("3% left", tooltip)
        self.assertIn("resets Aug 11 09:00", tooltip)
        self.assertNotIn("secret-account", tooltip)
        self.assertNotIn("other", tooltip)

    def test_the_tooltip_carries_every_state_the_glyph_does(self):
        # The accessibility path: nothing may depend on telling two shapes
        # apart, so each state is spelled out.
        for pct, word in ((90, "capacity ok"), (10, "capacity low"), (1, "capacity critical")):
            snapshot = build_snapshot([_row(available_pct=pct)], NOW, "9.9.9")
            self.assertIn(word, snapshot["icon"]["tooltip"])
        never = build_snapshot([_row(available_pct=None, age_seconds=None)], NOW, "9.9.9")
        self.assertIn("capacity unknown", never["icon"]["tooltip"])
        self.assertIn("never reported", never["icon"]["tooltip"])
        self.assertIn("no enabled sessions", build_snapshot([], NOW, "9.9.9")["icon"]["tooltip"])

    def test_the_tooltip_says_when_a_refresh_cannot_help(self):
        snapshot = build_snapshot(
            [_row(available_pct=40, active=True, age_seconds=9999)], NOW, "9.9.9"
        )
        self.assertIn("cannot refresh while a session runs", snapshot["icon"]["tooltip"])

    def test_a_known_state_outranks_an_unknown_one(self):
        # One never-reporting session must not blank an icon that has real news.
        snapshot = build_snapshot(
            [_row(name="silent", available_pct=None, age_seconds=None), _row(name="low", available_pct=10)],
            NOW,
            "9.9.9",
        )
        self.assertEqual(snapshot["icon"]["state"], ICON_LOW)

    def test_no_sessions_is_a_state_not_an_error(self):
        snapshot = build_snapshot([], NOW, "9.9.9")
        self.assertEqual(snapshot["icon"]["state"], ICON_UNKNOWN)
        self.assertEqual(snapshot["icon"]["reason"], "no_sessions")
        self.assertEqual(snapshot["sessions"], [])

    def test_disabled_sessions_are_left_out(self):
        snapshot = build_snapshot([_row(name="off", available_pct=1, enabled=False)], NOW, "9.9.9")
        self.assertEqual(snapshot["sessions"], [])

    def test_a_newer_snapshot_still_reads_with_one_hint(self):
        payload = build_snapshot([_row()], NOW, "9.9.9")
        payload["schema"] = {**payload["schema"], "major": SCHEMA_MAJOR + 1}
        payload["future_field"] = "ignored"
        result = read_snapshot(payload)
        self.assertTrue(result["ok"])
        self.assertIn("Update CDX", result["update_hint"])
        self.assertEqual(len(result["snapshot"]["sessions"]), 1)
        self.assertNotIn("future_field", result["snapshot"])

    def test_a_current_snapshot_reads_without_a_hint(self):
        result = read_snapshot(build_snapshot([_row()], NOW, "9.9.9"))
        self.assertTrue(result["ok"])
        self.assertIsNone(result["update_hint"])

    def test_foreign_payloads_are_rejected_rather_than_guessed(self):
        for payload in ({}, None, {"schema": {"name": "something.else", "major": 1}}, {"schema": {"name": SCHEMA_NAME}}):
            result = read_snapshot(payload)
            self.assertFalse(result["ok"], payload)
            self.assertEqual(result["reason"], "not_a_cdx_tray_snapshot")


class TrayCommandTest(CliTestBase):
    def _service(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        return service, temp_dir

    def _run(self, argv, service, temp_dir):
        io_obj = self.make_io()
        code = main(argv, {
            **io_obj, "service": service, "env": {"CDX_HOME": temp_dir},
            "spawn_sync": self._fake_registry(),
        })
        return code, io_obj["stdout"].getvalue()

    def _fake_registry(self):
        """A stand-in for `reg`, so a test never writes to the real machine.

        On Windows the autostart artifact *is* the HKCU Run key, so a test that
        called through would add a startup entry to whoever ran it — and leak
        that state into the next test. The seam exists in `tray_autostart`;
        this is what fills it.
        """
        keys = {}

        class Result:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stdout = ""
                self.stderr = ""

        def run(argv, **_kwargs):
            if not argv or argv[0] != "reg":
                return Result(0)
            action, value = argv[1], argv[-1]
            name = argv[argv.index("/v") + 1] if "/v" in argv else ""
            if action == "add":
                keys[name] = value
                return Result(0)
            if action == "delete":
                return Result(0 if keys.pop(name, None) is not None else 1)
            return Result(0 if name in keys else 1)

        return run


    def test_help_lists_every_action(self):
        service, temp_dir = self._service()
        code, out = self._run(["tray"], service, temp_dir)
        self.assertEqual(code, 0)
        for action in ("status", "install", "launch", "uninstall"):
            self.assertIn(action, out)

    def test_status_json_is_a_versioned_snapshot(self):
        service, temp_dir = self._service()
        service["create_session"]("work")
        service["record_status"]("work", {"remaining_5h_pct": 80, "remaining_week_pct": 60})
        code, out = self._run(["tray", "status", "--json"], service, temp_dir)
        self.assertEqual(code, 0)
        snapshot = json.loads(out)["snapshot"]
        self.assertEqual(snapshot["schema"]["name"], SCHEMA_NAME)
        self.assertEqual(snapshot["schema"]["major"], SCHEMA_MAJOR)
        self.assertEqual([s["name"] for s in snapshot["sessions"]], ["work"])
        self.assertIn("refresh", snapshot["actions"])
        self.assertIn("open_terminal", snapshot["actions"])

    def test_status_does_not_probe_providers_by_default(self):
        # The whole refresh policy in one assertion: a tray poll must reach the
        # cache, never a live provider probe that would contend on the auth lock.
        service, temp_dir = self._service()
        service["create_session"]("work")
        seen = {}
        original = service["get_status_rows"]

        def spy(**kwargs):
            seen.update(kwargs)
            return original(**kwargs)

        service["get_status_rows"] = spy
        self._run(["tray", "status", "--json"], service, temp_dir)
        self.assertTrue(seen["cache_only"])
        self.assertFalse(seen["force_refresh"])

        seen.clear()
        self._run(["tray", "status", "--json", "--refresh"], service, temp_dir)
        self.assertFalse(seen["cache_only"])
        self.assertTrue(seen["force_refresh"])

    def test_launch_and_uninstall_refuse_when_nothing_is_recorded(self):
        service, temp_dir = self._service()
        for action in ("launch", "uninstall"):
            code, out = self._run(["tray", action, "--json"], service, temp_dir)
            self.assertEqual(code, 0, action)
            payload = json.loads(out)
            self.assertFalse(payload["applied"], action)
            self.assertEqual(
                payload["warnings"][0]["code"], "tray_companion_not_installed", action
            )

    def test_launch_starts_the_companion_it_was_pointed_at(self):
        service, temp_dir = self._service()
        companion = os.path.join(temp_dir, "cdx-tray")
        with open(companion, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
        started = []
        io_obj = self.make_io()
        code = main(["tray", "launch", "--json"], {
            **io_obj,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CDX_TRAY_BIN": companion},
            "spawn_detached": started.append,
        })
        self.assertEqual(code, 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["executable"], companion)
        self.assertEqual(payload["source"], "override")
        self.assertEqual(started, [[companion]])

    def test_launch_names_a_companion_that_vanished(self):
        # A recorded path that no longer exists is a different problem from
        # never having installed, and the remedy differs too.
        service, temp_dir = self._service()
        io_obj = self.make_io()
        code = main(["tray", "launch", "--json"], {
            **io_obj,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CDX_TRAY_BIN": os.path.join(temp_dir, "gone")},
            "spawn_detached": lambda command: self.fail("must not spawn a missing file"),
        })
        self.assertEqual(code, 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "tray_companion_missing")

    def test_a_damaged_install_record_reads_as_absent(self):
        # The record drives deletion, so a half-understood one must not be used.
        service, temp_dir = self._service()
        os.makedirs(os.path.join(temp_dir, "tray"), exist_ok=True)
        with open(os.path.join(temp_dir, "tray", "install.json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(read_state(temp_dir))
        code, out = self._run(["tray", "uninstall", "--json"], service, temp_dir)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["warnings"][0]["code"], "tray_companion_not_installed")

    def _asset(self, directory, name="cdx-tray", body=b"#!/bin/sh\n", extra=None):
        """A tar.gz shaped like a real release asset, and its checksum."""
        payload = os.path.join(directory, name)
        with open(payload, "wb") as handle:
            handle.write(body)
        archive = os.path.join(directory, "asset.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(payload, arcname=name)
            for member_name, member_path in (extra or []):
                tar.add(member_path, arcname=member_name)
        return archive, hashlib.sha256(open(archive, "rb").read()).hexdigest()

    def _ledger(self, directory, version, target, digest):
        path = os.path.join(directory, "ledger.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"releases": {f"v{version}": {"tray_assets": {target: digest}}}}, handle)
        return path

    def test_install_verifies_the_checksum_before_unpacking(self):
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        archive, digest = self._asset(scratch)
        ledger = self._ledger(scratch, "9.9.9", "test-target", digest)
        state = install(
            base_dir, "9.9.9",
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
        )
        self.assertEqual(state["sha256"], digest)
        self.assertTrue(os.path.isfile(state["executable"]))
        self.assertTrue(os.access(state["executable"], os.X_OK))

    def test_install_prefers_the_bundle_over_the_binary_inside_it(self):
        """The macOS asset holds both, and only the bundle carries the identity.

        Launching the inner binary would lose `Info.plist`, so `LSUIElement` and
        the signed identity the notification grant is bound to go with it. The
        archive here lists the inner binary first, which is the order that would
        make an ordered scan pick the wrong one.
        """
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        bundle = os.path.join(scratch, "CDX.app", "Contents", "MacOS")
        os.makedirs(bundle)
        inner = os.path.join(bundle, "cdx-tray")
        with open(inner, "wb") as handle:
            handle.write(b"#!/bin/sh\n")
        archive = os.path.join(scratch, "bundle.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(inner, arcname="CDX.app/Contents/MacOS/cdx-tray")
            tar.add(os.path.join(scratch, "CDX.app"), arcname="CDX.app", recursive=False)
        digest = hashlib.sha256(open(archive, "rb").read()).hexdigest()
        ledger = self._ledger(scratch, "9.9.9", "test-target", digest)

        state = install(
            base_dir, "9.9.9",
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
        )
        self.assertTrue(state["executable"].endswith("CDX.app"), state["executable"])
        self.assertTrue(os.path.isdir(state["executable"]))

    def test_install_ignores_an_appledouble_companion_file(self):
        """`._CDX.app` is metadata, not a bundle, and it sorts first.

        macOS tar stores extended attributes as a `._name` member beside the
        real one, and a signed bundle has plenty. BSD tar hides them on listing
        because it merges them back, so the archive looks clean while any other
        reader sees `._CDX.app` — which ends in `.app` and is a few hundred
        bytes of metadata. Installing that leaves nothing runnable.
        """
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        bundle = os.path.join(scratch, "CDX.app", "Contents", "MacOS")
        os.makedirs(bundle)
        with open(os.path.join(bundle, "cdx-tray"), "wb") as handle:
            handle.write(b"#!/bin/sh\n")
        double = os.path.join(scratch, "._CDX.app")
        with open(double, "wb") as handle:
            handle.write(b"\x00\x05\x16\x07")

        archive = os.path.join(scratch, "double.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(double, arcname="._CDX.app")
            tar.add(os.path.join(scratch, "CDX.app"), arcname="CDX.app", recursive=True)
        digest = hashlib.sha256(open(archive, "rb").read()).hexdigest()
        ledger = self._ledger(scratch, "9.9.9", "test-target", digest)

        state = install(
            base_dir, "9.9.9",
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
        )
        self.assertTrue(os.path.isdir(state["executable"]), state["executable"])
        self.assertFalse(os.path.basename(state["executable"]).startswith("._"))

    def test_install_refuses_a_mismatched_checksum_and_writes_nothing(self):
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        archive, _digest = self._asset(scratch)
        ledger = self._ledger(scratch, "9.9.9", "test-target", "0" * 64)
        with self.assertRaises(TrayInstallError) as caught:
            install(
                base_dir, "9.9.9",
                download=lambda url, dest: shutil.copyfile(archive, dest),
                ledger_path=ledger, target="test-target",
            )
        self.assertIn("Checksum mismatch", str(caught.exception))
        self.assertIsNone(read_state(base_dir))

    def test_install_refuses_an_asset_nothing_vouches_for(self):
        # No published checksum is exactly the case the gate exists for.
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        ledger = self._ledger(scratch, "0.0.1", "other-target", "0" * 64)
        with self.assertRaises(TrayInstallError) as caught:
            install(base_dir, "9.9.9", ledger_path=ledger, target="test-target")
        self.assertIn("No published checksum", str(caught.exception))

    def test_install_refuses_an_archive_that_escapes_its_directory(self):
        # A verified checksum says the asset is the published one, not that the
        # published one is well behaved.
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        outside = os.path.join(scratch, "escape")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("nope")
        archive = os.path.join(scratch, "asset.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(outside, arcname="../escaped")
        digest = hashlib.sha256(open(archive, "rb").read()).hexdigest()
        ledger = self._ledger(scratch, "9.9.9", "test-target", digest)
        with self.assertRaises(TrayInstallError) as caught:
            install(
                base_dir, "9.9.9",
                download=lambda url, dest: shutil.copyfile(archive, dest),
                ledger_path=ledger, target="test-target",
            )
        self.assertIn("outside its install directory", str(caught.exception))
        self.assertIsNone(read_state(base_dir))

    def _installed(self, base_dir, scratch, version="9.9.9", body=b"#!/bin/sh\n"):
        archive, digest = self._asset(scratch, body=body)
        ledger = self._ledger(scratch, version, "test-target", digest)
        state = install(
            base_dir, version,
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
        )
        return state, ledger, archive

    def test_update_replaces_only_after_the_replacement_starts(self):
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        old, _ledger, _archive = self._installed(base_dir, scratch)

        newer = self.make_temp_dir()
        archive, digest = self._asset(newer, body=b"#!/bin/sh\n# v2\n")
        ledger = self._ledger(newer, "9.9.10", "test-target", digest)
        started = []
        result = update(
            base_dir, "9.9.10",
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
            probe=lambda executable: started.append(executable) or True,
        )
        self.assertEqual(result["replaced"], old["cdx_version"])
        self.assertEqual(read_state(base_dir)["cdx_version"], "9.9.10")
        self.assertTrue(os.path.isfile(read_state(base_dir)["executable"]))
        # The probe ran against the staged copy, before the swap.
        self.assertEqual(len(started), 1)
        self.assertFalse(interrupted_update(base_dir), "nothing left staged")

    def test_a_replacement_that_cannot_start_leaves_the_working_one(self):
        # The whole reason for staging: a bad asset costs an error message, not
        # a tray the user can no longer start.
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        old, _ledger, _archive = self._installed(base_dir, scratch)

        newer = self.make_temp_dir()
        archive, digest = self._asset(newer, body=b"broken\n")
        ledger = self._ledger(newer, "9.9.10", "test-target", digest)
        with self.assertRaises(TrayInstallError) as caught:
            update(
                base_dir, "9.9.10",
                download=lambda url, dest: shutil.copyfile(archive, dest),
                ledger_path=ledger, target="test-target",
                probe=lambda executable: False,
            )
        self.assertIn("did not start", str(caught.exception))
        still = read_state(base_dir)
        self.assertEqual(still["cdx_version"], old["cdx_version"])
        self.assertTrue(os.path.isfile(still["executable"]), "the working one survives")
        self.assertFalse(interrupted_update(base_dir), "the failed staging is cleaned up")

    def test_update_refuses_when_nothing_is_installed(self):
        with self.assertRaises(TrayInstallError) as caught:
            update(self.make_temp_dir(), "9.9.9", target="test-target")
        self.assertIn("nothing to update", str(caught.exception))

    def test_uninstall_removes_only_what_install_recorded(self):
        scratch = self.make_temp_dir()
        base_dir = self.make_temp_dir()
        archive, digest = self._asset(scratch)
        ledger = self._ledger(scratch, "9.9.9", "test-target", digest)
        state = install(
            base_dir, "9.9.9",
            download=lambda url, dest: shutil.copyfile(archive, dest),
            ledger_path=ledger, target="test-target",
        )
        bystander = os.path.join(base_dir, "tray", "not-ours.txt")
        with open(bystander, "w", encoding="utf-8") as handle:
            handle.write("keep me")

        result = uninstall(base_dir)
        self.assertEqual(result["removed"], state["paths"])
        self.assertFalse(os.path.exists(state["executable"]))
        self.assertIsNone(read_state(base_dir))
        # A file CDX never recorded survives, which is the whole contract.
        self.assertTrue(os.path.exists(bystander))

    def test_autostart_is_off_until_asked_and_reversible(self):
        # req_038 AC1 in one test: installing never enables startup, on and off
        # are explicit and idempotent, and the state is read back from the
        # platform rather than from what CDX last intended.
        service, temp_dir = self._service()
        home = self.make_temp_dir()
        env = {"HOME": home, "CDX_HOME": temp_dir, "CDX_TRAY_BIN": "/usr/bin/true"}
        # One registry for the whole test: on Windows the artifact is the HKCU
        # Run key, so calling through would add a startup entry to whoever ran
        # the suite and carry it into the next test.
        registry = self._fake_registry()

        def run(*argv):
            io_obj = self.make_io()
            main(["tray", *argv, "--json"], {
                **io_obj, "service": service, "env": env, "spawn_sync": registry,
            })
            return json.loads(io_obj["stdout"].getvalue())

        # The artifact is a file on macOS and Linux and a registry value on
        # Windows, so only `enabled` means the same thing everywhere. Asserting
        # a path exists is a claim about two of the three platforms, and the
        # Windows one reported its Run key — which `os.path.exists` will always
        # call absent. `enabled` is what the user acts on; the artifact is what
        # they are told to look at.
        self.assertFalse(run("autostart")["enabled"], "nothing enables it on its own")
        self.assertTrue(run("autostart", "on")["enabled"])
        artifact = run("autostart")["artifact"]
        self.assertTrue(artifact, "the state has to name what it wrote")
        if not artifact.startswith("HKCU"):
            self.assertTrue(os.path.exists(artifact))
        # Idempotent: asking twice is not an error and not a second entry.
        self.assertTrue(run("autostart", "on")["enabled"])
        self.assertFalse(run("autostart", "off")["enabled"])
        if not artifact.startswith("HKCU"):
            self.assertFalse(os.path.exists(artifact))
        # Off again on something already off is success, not a failure.
        self.assertFalse(run("autostart", "off")["enabled"])

    def test_autostart_on_refuses_without_a_companion(self):
        service, temp_dir = self._service()
        io_obj = self.make_io()
        code = main(["tray", "autostart", "on", "--json"], {
            **io_obj, "service": service,
            "env": {"HOME": self.make_temp_dir(), "CDX_HOME": temp_dir},
        })
        self.assertEqual(code, 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "tray_companion_not_installed")

    def test_doctor_reports_every_state_without_changing_any(self):
        service, temp_dir = self._service()
        home = self.make_temp_dir()
        io_obj = self.make_io()
        code = main(["tray", "doctor", "--json"], {
            **io_obj, "service": service,
            # TMPDIR too: the lock lives there, and without it doctor reads the
            # machine's real one — so the suite failed on any host where the
            # companion happened to be running.
            "env": {"HOME": home, "CDX_HOME": temp_dir, "TMPDIR": home},
            "spawn_sync": self._fake_registry(),
        })
        self.assertEqual(code, 0)
        checks = {c["check"]: c for c in json.loads(io_obj["stdout"].getvalue())["checks"]}
        self.assertEqual(
            set(checks),
            {"companion", "executable", "cdx_version", "target", "running", "autostart", "update",
             "desktop", "toasts", "alerts", "companion_cdx", "hook_store"},
        )
        self.assertEqual(checks["companion"]["state"], "absent")
        self.assertEqual(checks["running"]["state"], "no")
        self.assertEqual(checks["autostart"]["state"], "off")
        # It reads; it never fixes. Nothing it reported as absent got created.
        self.assertIsNone(read_state(temp_dir))

    def test_an_unknown_action_is_refused(self):
        service, temp_dir = self._service()
        io_obj = self.make_io()
        with self.assertRaises(CdxError):
            main(["tray", "frobnicate"], {**io_obj, "service": service, "env": {"CDX_HOME": temp_dir}})
