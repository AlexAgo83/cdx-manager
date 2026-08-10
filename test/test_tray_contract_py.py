"""Tests for the tray snapshot contract and the `cdx tray` command surface.

The behaviours worth guarding here are the ones a native companion cannot fix
for itself: never fabricating a quota figure, never leaking a session name into
the closed-icon state, telling `stale` apart from `cannot refresh right now`,
and staying readable when the snapshot is newer than the reader.
"""

import json
import os
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
from src.tray_install import read_state

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
        code = main(argv, {**io_obj, "service": service, "env": {"CDX_HOME": temp_dir}})
        return code, io_obj["stdout"].getvalue()

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

    def test_companion_actions_change_nothing_and_say_so(self):
        # Each refusal names its own reason: install has no implementation yet,
        # while launch and uninstall have one and simply have nothing recorded.
        service, temp_dir = self._service()
        expected = {
            "install": "tray_companion_not_available",
            "launch": "tray_companion_not_installed",
            "uninstall": "tray_companion_not_installed",
        }
        for action, code_name in expected.items():
            code, out = self._run(["tray", action, "--json"], service, temp_dir)
            self.assertEqual(code, 0, action)
            payload = json.loads(out)
            self.assertFalse(payload["applied"], action)
            self.assertEqual(payload["warnings"][0]["code"], code_name, action)

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

    def test_an_unknown_action_is_refused(self):
        service, temp_dir = self._service()
        io_obj = self.make_io()
        with self.assertRaises(CdxError):
            main(["tray", "frobnicate"], {**io_obj, "service": service, "env": {"CDX_HOME": temp_dir}})
