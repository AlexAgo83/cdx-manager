import importlib.util
import inspect
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from src.backup_bundle import encode_bundle, read_bundle_meta
from src.errors import CdxError
from src.session_service import create_session_service
from src.session_store import create_session_store

HAS_CRYPTOGRAPHY = importlib.util.find_spec("cryptography") is not None
CRYPTOGRAPHY_REQUIRED = "cryptography is required for encrypted auth bundle tests"


class SessionServicePythonTests(unittest.TestCase):
    def setUp(self):
        self.codex_status_patch = mock.patch("src.session_service.fetch_codex_rate_limits", return_value=None)
        self.codex_status_patch.start()

    def tearDown(self):
        self.codex_status_patch.stop()

    def make_temp_dir(self):
        return tempfile.mkdtemp(prefix="cdx-service-py-")

    def test_create_list_and_remove_sessions(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        main = service["create_session"]("main")
        service["create_session"]("work1", "claude")
        self.assertEqual(main["launch"], {"power": "medium", "fast": False})

        rows = service["format_list_rows"]()
        self.assertEqual([row["name"] for row in rows], ["main", "work1"])

        service["remove_session"]("main")
        self.assertEqual([s["name"] for s in service["list_sessions"]()], ["work1"])

    def test_session_label_set_clear_and_validation(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        updated = service["set_session_label"]("main", "  work  ")
        self.assertEqual(updated["label"], "work")
        self.assertNotIn("label", updated["launch"])
        self.assertEqual(service["format_list_rows"]()[0]["label"], "work")

        for label in ("   ", "bad\nlabel", "x" * 65):
            with self.assertRaises(CdxError):
                service["set_session_label"]("main", label)
        self.assertEqual(service["get_session"]("main")["label"], "work")

        cleared = service["clear_session_label"]("main")
        self.assertNotIn("label", cleared)
        self.assertIsNone(service["format_list_rows"]()[0].get("label"))

    def test_session_label_is_preserved_by_copy_and_rename(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["set_session_label"]("source", "client-a")

        copied = service["copy_session"]("source", "copy")["session"]
        self.assertEqual(copied["label"], "client-a")

        renamed = service["rename_session"]("copy", "renamed")
        self.assertEqual(renamed["label"], "client-a")

    def test_create_claude_session_disables_claude_commit_attribution(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        session = service["create_session"]("work1", "claude")
        settings_path = os.path.join(session["authHome"], ".claude", "settings.json")

        with open(settings_path, encoding="utf-8") as handle:
            settings = json.load(handle)
        self.assertIs(settings["includeCoAuthoredBy"], False)

    def test_create_claude_session_preserves_existing_claude_settings(self):
        temp_dir = self.make_temp_dir()
        settings_dir = os.path.join(temp_dir, "profiles", "work1", "claude-home", ".claude")
        os.makedirs(settings_dir, exist_ok=True)
        with open(os.path.join(settings_dir, "settings.json"), "w", encoding="utf-8") as handle:
            json.dump({"theme": "dark", "includeCoAuthoredBy": True}, handle)

        service = create_session_service({"base_dir": temp_dir})
        session = service["create_session"]("work1", "claude")

        with open(os.path.join(session["authHome"], ".claude", "settings.json"), encoding="utf-8") as handle:
            settings = json.load(handle)
        self.assertEqual(settings["theme"], "dark")
        self.assertIs(settings["includeCoAuthoredBy"], False)

    def test_create_session_uses_private_directory_permissions_on_unix(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        if os.name == "nt":
            self.skipTest("permission bits are not portable on Windows")

        session_root = service["get_session_root"]("main")
        auth_home = service["get_session"]("main")["authHome"]
        self.assertEqual(oct(os.stat(session_root).st_mode & 0o777), "0o700")
        self.assertEqual(oct(os.stat(auth_home).st_mode & 0o777), "0o700")

    def test_create_codex_session_seeds_global_auth(self):
        temp_dir = self.make_temp_dir()
        global_home = os.path.join(temp_dir, "global-codex-home")
        os.makedirs(global_home, exist_ok=True)
        with open(os.path.join(global_home, "auth.json"), "w", encoding="utf-8") as handle:
            handle.write("{\"tokens\": {}}\n")

        service = create_session_service({"base_dir": temp_dir})
        with mock.patch("src.session_service._get_global_codex_home", return_value=global_home):
            session = service["create_session"]("main")

        self.assertTrue(os.path.exists(os.path.join(session["authHome"], "auth.json")))

    def test_create_session_rejects_dot_path_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        for name in (".", ".."):
            with self.subTest(name=name):
                with self.assertRaisesRegex(CdxError, "cannot be . or .."):
                    service["create_session"](name)

        self.assertFalse(os.path.exists(os.path.join(temp_dir, "auth.json")))

    def test_create_antigravity_session_uses_dedicated_home(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        session = service["create_session"]("agy1", "antigravity")

        self.assertTrue(session["authHome"].endswith(os.path.join("agy1", "antigravity-home")))
        self.assertTrue(os.path.isdir(session["authHome"]))

    def test_ollama_launch_model_setting_can_be_set_and_unset(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("local", "ollama")

        updated = service["set_launch_settings"]("local", {"model": "llama3.2"})
        self.assertEqual(updated["launch"]["model"], "llama3.2")

        updated = service["set_launch_settings"]("local", {"rtk": "on"})
        self.assertTrue(updated["launch"]["rtk"])

        updated = service["unset_launch_settings"]("local", ["model", "rtk"])
        self.assertEqual(updated["launch"], {"power": "medium", "fast": False})

    def test_launch_power_rejects_undocumented_max_value(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "Unsupported power: max"):
            service["set_launch_settings"]("main", {"power": "max"})

    def test_fast_setting_is_service_tier_and_coexists_with_power(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        updated = service["set_launch_settings"]("main", {"fast": "on"})
        self.assertEqual(updated["launch"], {"power": "medium", "fast": True, "fastMode": "service_tier"})

        updated = service["set_launch_settings"]("main", {"power": "high"})
        self.assertEqual(updated["launch"], {"fast": True, "fastMode": "service_tier", "power": "high"})

        updated = service["set_launch_settings"]("main", {"fast": "on"})
        self.assertEqual(updated["launch"], {"fast": True, "fastMode": "service_tier", "power": "high"})

        updated = service["set_launch_settings"]("main", {"fast": "off"})
        self.assertEqual(updated["launch"], {"fast": False, "power": "high"})

    def test_status_rows_do_not_expose_auth_home(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        rows = service["get_status_rows"]()
        self.assertNotIn("auth_home", rows[0])

    def test_status_rows_include_auth_status(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["update_auth_state"]("main", lambda auth: {
            **auth,
            "status": "authenticated",
            "lastCheckedAt": "2026-04-15T10:00:00+00:00",
        })

        rows = service["get_status_rows"]()

        self.assertEqual(rows[0]["auth_status"], "authenticated")
        self.assertEqual(
            datetime.fromisoformat(rows[0]["auth_checked_at"]).timestamp(),
            datetime.fromisoformat("2026-04-15T10:00:00+00:00").timestamp(),
        )

    def test_status_rows_reuse_fresh_cache_unless_forced(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(_session):
            calls.append("fetch")
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")

        first_rows = service["get_status_rows"]()
        second_rows = service["get_status_rows"]()
        forced_rows = service["get_status_rows"](force_refresh=True)

        self.assertEqual(len(calls), 2)
        self.assertEqual(first_rows[0]["available_pct"], 70)
        self.assertEqual(second_rows[0]["available_pct"], 70)
        self.assertEqual(forced_rows[0]["available_pct"], 70)

    def test_status_rows_refresh_sessions_in_parallel(self):
        temp_dir = self.make_temp_dir()
        barrier = threading.Barrier(2, timeout=1)
        lock = threading.Lock()
        calls = []

        def fetch_status(session):
            with lock:
                calls.append(session["name"])
                call_index = len(calls)
            if call_index <= 2:
                barrier.wait()
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")
        service["create_session"]("work1")
        service["create_session"]("work2")

        rows = service["get_status_rows"](force_refresh=True)

        self.assertEqual(set(calls), {"main", "work1", "work2"})
        self.assertEqual({row["available_pct"] for row in rows}, {70})

    def test_status_row_refreshes_only_named_session(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(session):
            calls.append(session["name"])
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")
        service["create_session"]("work1")
        service["create_session"]("work2")

        row = service["get_status_row"]("work1", force_refresh=True)

        self.assertEqual(calls, ["work1"])
        self.assertEqual(row["session_name"], "work1")
        self.assertEqual(row["available_pct"], 70)

    def test_cached_status_rows_skip_provider_fetch(self):
        temp_dir = self.make_temp_dir()
        calls = []

        def fetch_status(session):
            calls.append(session["name"])
            return {
                "remaining_5h_pct": 80,
                "remaining_week_pct": 70,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")
        service["create_session"]("work1")
        service["record_status"]("work1", {
            "remaining_5h_pct": 25,
            "remaining_week_pct": 50,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        rows = service["get_status_rows"](force_refresh=True, cache_only=True)

        self.assertEqual(calls, [])
        by_name = {row["session_name"]: row for row in rows}
        self.assertIsNone(by_name["main"]["available_pct"])
        self.assertEqual(by_name["work1"]["available_pct"], 25)

    def test_status_timeout_env_applies_to_codex_fetch(self):
        temp_dir = self.make_temp_dir()
        with mock.patch("src.session_service.fetch_codex_rate_limits", return_value={
            "remaining_5h_pct": 80,
            "remaining_week_pct": 70,
            "updated_at": datetime.now().astimezone().isoformat(),
        }) as fetch_status:
            service = create_session_service({
                "base_dir": temp_dir,
                "env": {"CDX_STATUS_TIMEOUT_SECONDS": "0.75"},
            })
            service["create_session"]("main")

            row = service["get_status_row"]("main", force_refresh=True)

        self.assertEqual(row["available_pct"], 70)
        self.assertEqual(fetch_status.call_args.kwargs["timeout"], 0.75)

    def test_status_rows_clamp_cached_percentages(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "usage_pct": -5,
            "remaining_5h_pct": -10,
            "remaining_week_pct": 130,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        rows = service["get_status_rows"]()

        self.assertEqual(rows[0]["remaining_5h_pct"], 0)
        self.assertEqual(rows[0]["remaining_week_pct"], 100)
        self.assertEqual(rows[0]["available_pct"], 0)

    def test_remove_session_surfaces_profile_delete_failure(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        profile_root = service["get_session_root"]("main")
        self.assertTrue(os.path.exists(profile_root))

        with mock.patch("src.fs_utils.shutil.rmtree", side_effect=OSError("locked")):
            with self.assertRaisesRegex(CdxError, "failed to delete archived profile"):
                service["remove_session"]("main")

        self.assertIsNone(service["get_session"]("main"))
        quarantined = [
            name for name in os.listdir(os.path.dirname(profile_root))
            if name.startswith(".main.remove.")
        ]
        self.assertEqual(len(quarantined), 1)

    def test_remove_tree_uses_onexc_when_available(self):
        calls = []

        def fake_rmtree(path, ignore_errors=False, onexc=None):
            calls.append({
                "path": path,
                "ignore_errors": ignore_errors,
                "onexc": onexc,
            })

        temp_dir = self.make_temp_dir()
        signature = inspect.Signature([
            inspect.Parameter("path", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("ignore_errors", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("onexc", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ])
        with mock.patch("src.fs_utils.shutil.rmtree", side_effect=fake_rmtree), \
                mock.patch("src.fs_utils.inspect.signature", return_value=signature):
            from src.fs_utils import remove_tree
            remove_tree(temp_dir, ignore_errors=True)

        self.assertEqual(calls[0]["path"], temp_dir)
        self.assertIs(calls[0]["ignore_errors"], True)
        self.assertTrue(callable(calls[0]["onexc"]))

    @unittest.skipIf(sys.platform == "win32", "POSIX permission repair test")
    def test_remove_session_deletes_read_only_profile_cache(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main", "claude")
        profile_root = service["get_session_root"]("main")
        readonly_dir = os.path.join(
            profile_root,
            "claude-home",
            "go",
            "pkg",
            "mod",
            "google.golang.org",
            "protobuf@v1.36.10",
        )
        os.makedirs(readonly_dir, exist_ok=True)
        marker = os.path.join(readonly_dir, "readonly.txt")
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("cache")
        os.chmod(marker, 0o400)
        os.chmod(readonly_dir, 0o500)

        removed = service["remove_session"]("main")

        self.assertEqual(removed["name"], "main")
        self.assertIsNone(service["get_session"]("main"))
        profiles_dir = os.path.dirname(profile_root)
        self.assertFalse(os.path.exists(profile_root))
        self.assertFalse(any(name.startswith(".main.remove.") for name in os.listdir(profiles_dir)))

    def test_launch_rehydrates_state_and_missing_state_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        launched = service["launch_session"]("main")
        self.assertEqual(launched["name"], "main")
        self.assertEqual(launched["lastLaunchedAt"], launched["updatedAt"])

        service["create_session"]("work1")
        os.remove(os.path.join(temp_dir, "state", "work1.json"))
        with self.assertRaises(CdxError):
            service["launch_session"]("work1")

    def test_runtime_state_marks_active_sessions_and_clears_on_finish(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        runtime = service["start_session_runtime"]("main", {"pid": os.getpid(), "command": "codex"})
        rows = service["get_status_rows"]()
        self.assertTrue(rows[0]["active"])
        self.assertTrue(service["format_list_rows"]()[0]["active"])

        service["finish_session_runtime"]("main", runtime["runId"], {"returncode": 0})
        self.assertFalse(service["get_status_rows"]()[0]["active"])

    def test_runtime_state_cleans_stale_pid(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        service["start_session_runtime"]("main", {"pid": 999999999})

        self.assertFalse(service["get_status_rows"]()[0]["active"])
        state = create_session_store(temp_dir)["read_session_state"]("main")
        self.assertEqual(state["runtime"]["status"], "stale")

    def test_disable_keeps_session_listed_last_and_blocks_launch(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("aaa")
        service["create_session"]("zzz")
        disabled = service["set_session_enabled"]("aaa", False)
        self.assertFalse(disabled["enabled"])

        rows = service["format_list_rows"]()
        self.assertEqual([row["name"] for row in rows], ["zzz", "aaa"])
        self.assertEqual(rows[-1]["enabled_status"], "disabled")

        status_rows = service["get_status_rows"]()
        self.assertEqual(status_rows[-1]["session_name"], "aaa")
        self.assertFalse(status_rows[-1]["enabled"])
        self.assertIsNone(status_rows[-1]["available_pct"])
        self.assertIsNone(status_rows[-1]["remaining_5h_pct"])
        self.assertIsNone(status_rows[-1]["remaining_week_pct"])
        self.assertIsNone(status_rows[-1]["reset_5h_at"])
        self.assertIsNone(status_rows[-1]["reset_week_at"])

        with self.assertRaisesRegex(CdxError, "Session is disabled: aaa"):
            service["launch_session"]("aaa")

        service["set_session_enabled"]("aaa", True)
        self.assertEqual(service["launch_session"]("aaa")["name"], "aaa")

    def test_rejects_duplicates_and_unknown_providers(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        with self.assertRaises(CdxError):
            service["create_session"]("main")
        with self.assertRaises(CdxError):
            service["create_session"]("other", "invalid")

    def test_rejects_reserved_session_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        for name in ("add", "update", "context", "handoff", "ready", "next", "last", "power", "perm", "fast", "model", "disk", "reset"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(CdxError, f"Session name is reserved: {name}"):
                    service["create_session"](name)

    def test_rejects_invalid_session_name_shapes(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        with self.assertRaisesRegex(CdxError, "control characters"):
            service["create_session"]("bad\nname")
        with self.assertRaisesRegex(CdxError, "start or end with whitespace"):
            service["create_session"](" bad")
        with self.assertRaisesRegex(CdxError, "too long"):
            service["create_session"]("a" * 65)

    def test_status_rows_are_sorted_by_recency(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        service["create_session"]("main")
        service["create_session"]("work1", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 39,
            "remaining_week_pct": 70,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 16 10:10",
            "updated_at": "2026-04-15T09:00:00+00:00",
        })
        service["record_status"]("work1", {
            "remaining_5h_pct": 56,
            "remaining_week_pct": 81,
            "reset_5h_at": "Apr 17 05:00",
            "reset_week_at": "Apr 17 22:00",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[1]["session_name"], "main")

    def test_status_rows_can_be_derived_from_codex_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 39% left",
                "│                        (resets 02:21 on 16 Apr)            │",
                "│  Weekly limit:         [██████████████░░░░░░] 70% left",
                "│                        (resets 10:10 on 17 Apr)            │",
                "│  Credits:              453 credits",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["available_pct"], 39)
        self.assertEqual(rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(rows[0]["remaining_week_pct"], 70)
        self.assertEqual(rows[0]["credits"], "453")
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(rows[0]["reset_at"], "Apr 17 10:10")

    def test_codex_app_server_status_is_preferred_over_transcript_artifact(self):
        temp_dir = self.make_temp_dir()
        live_status = {
            "remaining_5h_pct": 93,
            "remaining_week_pct": 66,
            "credits": None,
            "reset_credits_available": 1,
            "reset_credits": [{"id": "reset-1", "expires_at": "2026-06-20T10:00:00+02:00"}],
            "reset_5h_at": "May 22 20:59",
            "reset_week_at": "May 27 15:51",
            "reset_at": "May 27 15:51",
            "updated_at": "2026-05-22T15:00:00+02:00",
            "raw_status_text": "{\"limitId\":\"codex\"}",
            "source_ref": "api:codex-app-server-rate-limits",
        }
        fetch_calls = []

        def fetcher(session):
            fetch_calls.append(session)
            return live_status

        service = create_session_service({"base_dir": temp_dir, "fetchCodexRateLimits": fetcher})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("│  5h limit: [████░░] 39% left\n")

        rows = service["get_status_rows"]()

        self.assertEqual(len(fetch_calls), 1)
        self.assertEqual(rows[0]["remaining_5h_pct"], 93)
        self.assertEqual(rows[0]["remaining_week_pct"], 66)
        self.assertIsNone(rows[0]["credits"])
        self.assertEqual(rows[0]["reset_credits_available"], 1)
        self.assertEqual(rows[0]["reset_credits"][0]["id"], "reset-1")
        self.assertEqual(
            service["get_session"]("main")["lastStatus"]["source_ref"],
            "api:codex-app-server-rate-limits",
        )

    def test_structured_status_from_rollout_path_is_not_low_confidence(self):
        from src.session_service import _is_low_confidence_status_source

        ref = "/home/x/.codex/sessions/2026/04/15/rollout-abc.jsonl:3"
        self.assertTrue(_is_low_confidence_status_source({"source_ref": ref}))
        self.assertFalse(_is_low_confidence_status_source({"source_ref": ref, "structured": True}))

    def test_merged_status_keeps_structured_marker_with_adopted_source_ref(self):
        from src.session_service import _is_low_confidence_status_source, _merge_status_payload

        ref = "/home/x/.codex/sessions/2026/04/15/rollout-abc.jsonl:3"
        merged = _merge_status_payload(
            {"remaining_5h_pct": 44, "source_ref": None},
            {"remaining_week_pct": 59, "source_ref": ref, "structured": True},
        )

        self.assertEqual(merged["source_ref"], ref)
        self.assertTrue(merged["structured"])
        self.assertFalse(_is_low_confidence_status_source(merged))

    def test_codex_status_can_be_derived_from_structured_rollout_rate_limits(self):
        temp_dir = self.make_temp_dir()
        global_home = os.path.join(temp_dir, "global-codex-home")
        os.makedirs(global_home, exist_ok=True)
        with open(os.path.join(global_home, "auth.json"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"tokens": {}}))

        rollout_path = os.path.join(global_home, "sessions", "2026", "04", "19", "rollout.jsonl")
        os.makedirs(os.path.dirname(rollout_path), exist_ok=True)
        with open(rollout_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-19T14:17:32.534Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": None,
                    "rate_limits": {
                        "limit_id": "codex",
                        "primary": {
                            "used_percent": 7.0,
                            "window_minutes": 300,
                            "resets_at": 1776625434,
                        },
                        "secondary": {
                            "used_percent": 32.0,
                            "window_minutes": 10080,
                            "resets_at": 1777135959,
                        },
                        "credits": None,
                        "plan_type": "plus",
                    },
                },
            }))
            handle.write("\n")

        with mock.patch("src.session_service.get_cdx_home", return_value=temp_dir):
            with mock.patch("src.session_service._get_global_codex_home", return_value=global_home):
                service = create_session_service({"base_dir": temp_dir})
                service["create_session"]("main")
                rows = service["get_status_rows"]()

        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["available_pct"], 68)
        self.assertEqual(rows[0]["remaining_5h_pct"], 93)
        self.assertEqual(rows[0]["remaining_week_pct"], 68)
        self.assertIsNone(rows[0]["credits"])
        self.assertIsNotNone(rows[0]["reset_5h_at"])
        self.assertIsNotNone(rows[0]["reset_week_at"])
        self.assertIsNotNone(rows[0]["reset_at"])

    def test_derived_codex_status_is_persisted_after_log_disappears(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 39% left",
                "│                        (resets 02:21 on 16 Apr)            │",
                "│  Weekly limit:         [██████████████░░░░░░] 70% left",
                "│                        (resets 10:10 on 17 Apr)            │",
            ]))

        first_rows = service["get_status_rows"]()
        self.assertEqual(first_rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(first_rows[0]["remaining_week_pct"], 70)

        os.remove(session_log)
        reloaded = create_session_service({"base_dir": temp_dir})
        second_rows = reloaded["get_status_rows"]()
        self.assertEqual(second_rows[0]["available_pct"], 39)
        self.assertEqual(second_rows[0]["remaining_5h_pct"], 39)
        self.assertEqual(second_rows[0]["remaining_week_pct"], 70)
        self.assertEqual(second_rows[0]["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(second_rows[0]["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(second_rows[0]["reset_at"], "Apr 17 10:10")

    def test_incomplete_cached_status_is_enriched_from_same_timestamp_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1")

        session_log = os.path.join(temp_dir, "profiles", "work1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████████] 100% left",
                "│                        (resets 04:03 on 16 Apr)",
                "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
                "│                        (resets 00:08 on 18 Apr)",
            ]))

        status_updated_at = "2026-04-15T21:03:59.270502+00:00"
        service["record_status"]("work1", {
            "usage_pct": 0,
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_at": "Apr 18 00:08",
            "updated_at": status_updated_at,
            "raw_status_text": "cached-but-incomplete",
        })
        os.utime(session_log, (
            datetime.fromisoformat(status_updated_at).timestamp(),
            datetime.fromisoformat(status_updated_at).timestamp(),
        ))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 04:03")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 18 00:08")

        reloaded = create_session_service({"base_dir": temp_dir})
        persisted = reloaded["get_session"]("work1")["lastStatus"]
        self.assertEqual(persisted["reset_5h_at"], "Apr 16 04:03")
        self.assertEqual(persisted["reset_week_at"], "Apr 18 00:08")

    def test_status_rows_can_be_derived_from_claude_artifact(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1", "claude")

        session_log = os.path.join(temp_dir, "profiles", "work1", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "0% used",
                "Current week",
                "14% used",
                "Resets Thursday, April 17",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["provider"], "claude")
        self.assertEqual(rows[0]["available_pct"], 86)
        self.assertEqual(rows[0]["remaining_5h_pct"], 100)
        self.assertEqual(rows[0]["remaining_week_pct"], 86)
        self.assertIsNone(rows[0]["reset_5h_at"])
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17")
        self.assertEqual(rows[0]["reset_at"], "Apr 17")

    def test_jsonl_payload_with_multiple_embedded_status_blocks_uses_latest_block(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        history_path = os.path.join(temp_dir, "profiles", "work2", "history.jsonl")
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        payload = "\n".join([
            "Some user text before",
            "│  5h limit:             [████████████████████] 100% left",
            "│                        (resets 04:03 on 16 Apr)",
            "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
            "│                        (resets 00:08 on 18 Apr)",
            "To continue this session, run codex resume older-session",
            "More unrelated text between blocks",
            "│  5h limit:             [████████████████░░░░] 81% left",
            "│                        (resets 03:48 on 16 Apr)",
            "│  Weekly limit:         [████████████████░░░░] 82% left",
            "│                        (resets 16:51 on 22 Apr)",
            "To continue this session, run codex resume newer-session",
        ])
        with open(history_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:05:09.350492Z",
                "payload": {"text": payload},
            }))
            handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work2")
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_log_artifact_wins_over_newer_conversational_jsonl_noise(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        session_root = os.path.join(temp_dir, "profiles", "work2")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume newer-session",
            ]))

        rollout_path = os.path.join(session_root, "sessions", "2026", "04", "15", "rollout.jsonl")
        os.makedirs(os.path.dirname(rollout_path), exist_ok=True)
        noisy_payload = "\n".join([
            "assistant recap",
            "│  5h limit:             [████████████████████] 100% left",
            "│                        (resets 04:03 on 16 Apr)",
            "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
            "│                        (resets 00:08 on 18 Apr)",
            "To continue this session, run codex resume older-session",
        ])
        with open(rollout_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:07:17.358831Z",
                "payload": {"text": noisy_payload},
            }))
            handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_latest_block_in_same_log_wins(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████░░░░░░░░] 60% left",
                "│                        (resets 01:00 on 16 Apr)",
                "│  Weekly limit:         [████████████░░░░░░░░] 60% left",
                "│                        (resets 09:00 on 18 Apr)",
                "To continue this session, run codex resume older-session",
                "noise",
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume newer-session",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["available_pct"], 81)
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")
        self.assertEqual(rows[0]["reset_at"], "Apr 22 16:51")

    def test_noisy_ansi_transcript_still_parses(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        noisy = (
            "\x1b[31mgarbage before\x1b[0m\n"
            "│  5h limit:             [████████████████░░░░] 81% left\r\n"
            "│                        (resets 03:48 on 16 Apr)\r\n"
            "\x1b]0;title\x07"
            "│  Weekly limit:         [████████████████░░░░] 82% left\r\n"
            "│                        (resets 16:51 on 22 Apr)\r\n"
            "To continue this session, run codex resume noisy-session\r\n"
            "garbage after 123%\n"
        )
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write(noisy)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_narrow_codex_status_transcript_still_parses_resets(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1")

        session_log = os.path.join(temp_dir, "profiles", "work1", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        narrow = (
            "\x1b[39;49m\x1b[K/status\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│  5h limit:             \x1b[22m[████████████████████] 100\x1b[2m │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│                        (resets 04:38 on 16 Apr)   │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│  Weekly limit:         \x1b[22m[█░░░░░░░░░░░░░░░░░░░] 6% \x1b[2m │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m│                        (resets 00:08 on 18 Apr)   │\x1b[39m\x1b[49m\x1b[0m\n"
            "\x1b[39;49m\x1b[K\x1b[2m╰───────────────────────────────────────────────────╯\x1b[39m\x1b[49m\x1b[0m\n"
            "To continue this session, run codex resume 019d9315-0549-7ab0-95fd-b36d812836db\n"
        )
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write(narrow)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work1")
        self.assertEqual(rows[0]["remaining_5h_pct"], 100)
        self.assertEqual(rows[0]["remaining_week_pct"], 6)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 04:38")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 18 00:08")

    def test_large_status_log_is_tailed(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_log = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("old noise\n" * 70000)
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_codex_status_prefers_matching_account_when_context_has_boxed_blank_lines(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work4")

        session_root = os.path.join(temp_dir, "profiles", "work4")
        with open(os.path.join(session_root, "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({
                "tokens": {
                    "id_token": (
                        "x."
                        "eyJlbWFpbCI6InByaW1hcnlAZXhhbXBsZS50ZXN0In0"
                        ".y"
                    ),
                },
            }, handle)

        log_dir = os.path.join(session_root, "log")
        os.makedirs(log_dir, exist_ok=True)
        older_log = os.path.join(log_dir, "cdx-session-older.log")
        newer_log = os.path.join(log_dir, "cdx-session-newer.log")
        older_text = "\n".join([
            "│  information on rate limits and credits                                 │",
            "│                                                                        │",
            "│  Account:              primary@example.test (Business)                 │",
            "│  Session:              older-session                                   │",
            "│                                                                        │",
            "│  5h limit:             [████████████████░░░░] 81% left                 │",
            "│  Weekly limit:         [██████████████░░░░░░] 70% left                 │",
            "│                        (resets 16:51 on 22 Apr)                        │",
            "╰────────────────────────────────────────────────────────────────────────╯",
            "To continue this session, run codex resume older-session",
        ])
        newer_text = "\n".join([
            "│  information on rate limits and credits                                 │",
            "│                                                                        │",
            "│  Account:              secondary@example.test (Business)               │",
            "│  Session:              newer-session                                   │",
            "│                                                                        │",
            "│  5h limit:             [████████████████████] 100% left                │",
            "│  Weekly limit:         [████████████████████] 100% left                │",
            "│                        (resets 11:32 on 23 Apr)                        │",
            "╰────────────────────────────────────────────────────────────────────────╯",
            "To continue this session, run codex resume newer-session",
        ])
        with open(older_log, "w", encoding="utf-8") as handle:
            handle.write(older_text)
        with open(newer_log, "w", encoding="utf-8") as handle:
            handle.write(newer_text)
        os.utime(older_log, (1000, 1000))
        os.utime(newer_log, (2000, 2000))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work4")
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 70)
        self.assertEqual(rows[0]["available_pct"], 70)
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")

    def test_direct_status_log_is_used_even_with_many_newer_history_files(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        session_root = os.path.join(temp_dir, "profiles", "main")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
            ]))

        history_dir = os.path.join(session_root, "sessions", "2026", "04", "16")
        os.makedirs(history_dir, exist_ok=True)
        for index in range(80):
            path = os.path.join(history_dir, f"noise-{index}.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": f"2026-04-16T10:{index % 60:02d}:00.000Z",
                    "payload": {"text": "conversation without status"},
                }))
                handle.write("\n")

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)

    def test_copy_session_overwrites_and_keeps_isolation(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "10% used",
                "Current week",
                "20% used",
                "Resets Thursday, April 17",
            ]))

        result = service["copy_session"]("source", "dest")
        self.assertTrue(result["overwritten"])
        copied = service["get_session"]("dest")
        self.assertEqual(copied["provider"], "claude")
        self.assertTrue(copied["authHome"].endswith(os.path.join("dest", "claude-home")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))

    def test_copy_session_preserves_destination_when_copy_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        dest_marker = os.path.join(temp_dir, "profiles", "dest", "marker.txt")
        with open(dest_marker, "w", encoding="utf-8") as handle:
            handle.write("keep")

        with mock.patch("src.session_service.shutil.copytree", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                service["copy_session"]("source", "dest")

        dest = service["get_session"]("dest")
        self.assertEqual(dest["provider"], "codex")
        self.assertTrue(os.path.exists(dest_marker))

    def test_copy_session_preserves_destination_when_store_replace_fails(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["create_session"]("dest")

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("source")
        dest_marker = os.path.join(temp_dir, "profiles", "dest", "marker.txt")
        with open(dest_marker, "w", encoding="utf-8") as handle:
            handle.write("keep")

        def write_json(file_path, value):
            if file_path.endswith(os.path.join("state", "dest.json")):
                raise OSError("state write failed")
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaises(OSError):
                service["copy_session"]("source", "dest")

        dest = service["get_session"]("dest")
        self.assertEqual(dest["provider"], "codex")
        self.assertTrue(os.path.exists(dest_marker))
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))

    def test_copy_session_rejects_reserved_destination_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source")

        with self.assertRaisesRegex(CdxError, "Session name is reserved: add"):
            service["copy_session"]("source", "add")

    def test_rename_session_moves_profile_and_state(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source", "claude")
        service["record_status"]("source", {
            "remaining_5h_pct": 90,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        source_log = os.path.join(temp_dir, "profiles", "source", "claude-home", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(source_log), exist_ok=True)
        with open(source_log, "w", encoding="utf-8") as handle:
            handle.write("Current session\n10% used\nCurrent week\n20% used\n")

        renamed = service["rename_session"]("source", "dest")
        self.assertEqual(renamed["name"], "dest")
        self.assertEqual(renamed["provider"], "claude")
        self.assertIsNone(service["get_session"]("source"))
        self.assertEqual(service["get_session"]("dest")["lastStatus"]["remaining_5h_pct"], 90)
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "profiles", "source")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "profiles", "dest", "claude-home", "log", "cdx-session.log")))
        self.assertFalse(os.path.exists(os.path.join(temp_dir, "state", "source.json")))
        self.assertTrue(os.path.exists(os.path.join(temp_dir, "state", "dest.json")))
        self.assertEqual(service["launch_session"]("dest")["name"], "dest")

    def test_rename_session_rejects_existing_and_reserved_destination_names(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("source")
        service["create_session"]("dest")

        with self.assertRaisesRegex(CdxError, "Session already exists: dest"):
            service["rename_session"]("source", "dest")
        with self.assertRaisesRegex(CdxError, "Session name is reserved: add"):
            service["rename_session"]("source", "add")

    def test_set_power_clears_stored_reasoning_effort(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_launch_settings"]("main", {"reasoning_effort": "high"})

        updated = service["set_launch_settings"]("main", {"power": "low"})

        self.assertEqual(updated["launch"]["power"], "low")
        self.assertNotIn("reasoning_effort", updated["launch"])

    def test_unset_launch_settings_allows_reasoning_effort(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_launch_settings"]("main", {"reasoning_effort": "high"})

        updated = service["unset_launch_settings"]("main", ["reasoning_effort"])

        self.assertNotIn("reasoning_effort", updated.get("launch") or {})

    def test_export_import_round_trip_without_auth(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        source["set_session_label"]("main", "work")
        source["record_status"]("main", {
            "remaining_5h_pct": 81,
            "remaining_week_pct": 82,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        bundle_path = os.path.join(source_dir, "backup.cdx")
        export_result = source["export_bundle"](bundle_path)
        self.assertEqual(export_result["session_names"], ["main"])
        self.assertFalse(export_result["include_auth"])

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        import_result = target["import_bundle"](bundle_path)
        self.assertEqual(import_result["session_names"], ["main"])
        self.assertFalse(import_result["include_auth"])
        imported = target["get_session"]("main")
        self.assertEqual(imported["provider"], "codex")
        self.assertEqual(imported["label"], "work")
        self.assertEqual(imported["lastStatus"]["remaining_5h_pct"], 81)
        self.assertTrue(os.path.exists(os.path.join(target_dir, "state", "main.json")))

    def test_force_import_without_auth_refuses_to_overwrite_existing_credentials(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        auth_path = os.path.join(target_dir, "profiles", "main", "auth.json")
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"local"}')
        plugin_marker = os.path.join(target_dir, "profiles", "main", "plugins", "ponytail", ".installed")
        os.makedirs(os.path.dirname(plugin_marker), exist_ok=True)
        with open(plugin_marker, "w", encoding="utf-8") as handle:
            handle.write("local-plugin")

        with self.assertRaisesRegex(CdxError, "bundle has no auth payloads"):
            target["import_bundle"](bundle_path, force=True)

        with open(auth_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"local"}')
        with open(plugin_marker, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "local-plugin")
        self.assertEqual(target["get_session"]("main")["name"], "main")

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_force_import_with_auth_preserves_local_plugins(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        auth_path = os.path.join(source_dir, "profiles", "main", "auth.json")
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"bundle"}')
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        marker = os.path.join(target_dir, "profiles", "main", "plugins", "ponytail", ".installed")
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("local")

        target["import_bundle"](bundle_path, passphrase="pw123", force=True)

        with open(marker, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "local")
        with open(os.path.join(target_dir, "profiles", "main", "auth.json"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"bundle"}')

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_force_import_plugin_restore_failure_rolls_back(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        auth_path = os.path.join(source_dir, "profiles", "main", "auth.json")
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"bundle"}')
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        target["set_session_label"]("main", "local")
        marker = os.path.join(target_dir, "profiles", "main", "plugins", "ponytail", ".installed")
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("local")

        with mock.patch("src.session_service.shutil.copytree", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(CdxError, "Could not restore local plugin state for session main: plugins"):
                target["import_bundle"](bundle_path, passphrase="pw123", force=True)

        self.assertEqual(target["get_session"]("main")["label"], "local")
        with open(marker, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "local")

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_force_import_preserves_plugins_only_for_selected_sessions(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        source["create_session"]("side")
        for name in ("main", "side"):
            auth_path = os.path.join(source_dir, "profiles", name, "auth.json")
            with open(auth_path, "w", encoding="utf-8") as handle:
                handle.write(f'{{"token":"bundle-{name}"}}')
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        target["create_session"]("side")
        markers = {}
        for name in ("main", "side"):
            marker = os.path.join(target_dir, "profiles", name, "plugins", "ponytail", ".installed")
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write(f"local-{name}")
            markers[name] = marker
        side_auth_path = os.path.join(target_dir, "profiles", "side", "auth.json")
        with open(side_auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"local-side"}')

        target["import_bundle"](bundle_path, passphrase="pw123", session_names=["main"], force=True)

        for name, marker in markers.items():
            with open(marker, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), f"local-{name}")
        with open(side_auth_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"local-side"}')

    def test_force_import_prevalidates_profile_files_before_touching_existing_session(self):
        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        auth_path = os.path.join(target_dir, "profiles", "main", "auth.json")
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"local"}')

        bundle_path = os.path.join(target_dir, "corrupt-profile.cdx")
        payload = {
            "schema_version": 1,
            "sessions": [{"name": "main", "provider": "codex"}],
            "states": {},
            "profiles": {"main": [{"path": "auth.json", "data_b64": "not valid base64!"}]},
        }
        with open(bundle_path, "wb") as handle:
            handle.write(encode_bundle(payload, include_auth=False))

        with self.assertRaisesRegex(CdxError, "invalid file data"):
            target["import_bundle"](bundle_path, force=True, allow_authless_force=True)

        with open(auth_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"local"}')
        self.assertEqual(target["get_session"]("main")["name"], "main")

    def test_force_import_rejects_malformed_profile_entries_before_touching_existing_session(self):
        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        auth_path = os.path.join(target_dir, "profiles", "main", "auth.json")
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"local"}')

        bundle_path = os.path.join(target_dir, "malformed-profile.cdx")
        payload = {
            "schema_version": 1,
            "sessions": [{"name": "main", "provider": "codex"}],
            "states": {},
            "profiles": {"main": [None]},
        }
        with open(bundle_path, "wb") as handle:
            handle.write(encode_bundle(payload, include_auth=False))

        with self.assertRaisesRegex(CdxError, "invalid profile entry"):
            target["import_bundle"](bundle_path, force=True, allow_authless_force=True)

        with open(auth_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"local"}')
        self.assertEqual(target["get_session"]("main")["name"], "main")

    def test_export_bundle_does_not_restrict_existing_parent_directory(self):
        if os.name == "nt":
            self.skipTest("permission bits are not portable on Windows")
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        export_dir = os.path.join(source_dir, "shared")
        os.makedirs(export_dir)
        os.chmod(export_dir, 0o755)

        bundle_path = os.path.join(export_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        self.assertEqual(oct(os.stat(export_dir).st_mode & 0o777), "0o755")
        self.assertEqual(oct(os.stat(bundle_path).st_mode & 0o777), "0o600")

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_import_round_trip_with_auth_bundle(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("claude1", "claude")
        token_path = os.path.join(source_dir, "profiles", "claude1", "claude-home", "auth.json")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')
        cache_path = os.path.join(source_dir, "profiles", "claude1", "claude-home", "cache", "skip.txt")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            handle.write("skip")

        from src.errors import CdxError
        with self.assertRaises(CdxError):
            read_bundle_meta(b"42")

        bundle_path = os.path.join(source_dir, "secure.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")
        with open(bundle_path, "rb") as handle:
            bundle_meta = read_bundle_meta(handle.read())
        self.assertEqual(bundle_meta["encryption"], "aes-256-gcm")
        self.assertNotIn("session_names", bundle_meta)
        self.assertNotIn("hmac_sha256", bundle_meta)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["import_bundle"](bundle_path, passphrase="pw123")

        imported_auth = os.path.join(target_dir, "profiles", "claude1", "claude-home", "auth.json")
        self.assertTrue(os.path.exists(imported_auth))
        with open(imported_auth, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')
        self.assertFalse(os.path.exists(os.path.join(target_dir, "profiles", "claude1", "claude-home", "cache", "skip.txt")))

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_import_accepts_legacy_auth_bundle_with_cleartext_session_names(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("legacy")
        bundle_path = os.path.join(source_dir, "legacy.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        with open(bundle_path, "rb") as handle:
            wrapper = json.loads(handle.read().decode("utf-8"))
        wrapper["session_names"] = ["legacy"]
        with open(bundle_path, "wb") as handle:
            handle.write(json.dumps(wrapper, indent=2).encode("utf-8"))

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        import_result = target["import_bundle"](bundle_path, passphrase="pw123")

        self.assertEqual(import_result["session_names"], ["legacy"])
        self.assertEqual(target["get_session"]("legacy")["name"], "legacy")

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_auth_bundle_excludes_non_auth_profile_files(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        session_root = os.path.join(source_dir, "profiles", "main")
        with open(os.path.join(session_root, "auth.json"), "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')
        with open(os.path.join(session_root, "logs_2.sqlite"), "w", encoding="utf-8") as handle:
            handle.write("large log database")

        bundle_path = os.path.join(source_dir, "secure.cdx")
        export_result = source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")
        self.assertEqual(export_result["profile_file_count"], 1)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["import_bundle"](bundle_path, passphrase="pw123")

        target_root = os.path.join(target_dir, "profiles", "main")
        self.assertTrue(os.path.exists(os.path.join(target_root, "auth.json")))
        self.assertFalse(os.path.exists(os.path.join(target_root, "logs_2.sqlite")))

    def test_import_rejects_conflicts_without_force(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "Import would overwrite existing sessions: main"):
            target["import_bundle"](bundle_path)

    def test_import_supports_subset_selection(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        source["create_session"]("side")
        bundle_path = os.path.join(source_dir, "subset.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["import_bundle"](bundle_path, session_names=["side"])

        self.assertIsNone(target["get_session"]("main"))
        self.assertEqual(target["get_session"]("side")["name"], "side")

    def test_import_rejects_dot_path_session_names(self):
        temp_dir = self.make_temp_dir()
        target_dir = os.path.join(temp_dir, "target")
        target = create_session_service({"base_dir": target_dir})
        bundle_path = os.path.join(temp_dir, "bad.cdx")
        payload = {
            "schema_version": 1,
            "sessions": [{"name": "..", "provider": "codex"}],
            "states": {},
            "profiles": {},
        }
        from src.backup_bundle import encode_bundle
        with open(bundle_path, "wb") as handle:
            handle.write(encode_bundle(payload))

        with self.assertRaisesRegex(CdxError, "cannot be . or .."):
            target["import_bundle"](bundle_path)

        self.assertFalse(os.path.exists(os.path.join(target_dir, "auth.json")))

    def test_import_rejects_missing_subset_sessions(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        bundle_path = os.path.join(source_dir, "subset.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        with self.assertRaisesRegex(CdxError, "Bundle does not contain requested sessions: missing"):
            target["import_bundle"](bundle_path, session_names=["missing"])

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_import_rejects_wrong_bundle_passphrase(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        bundle_path = os.path.join(source_dir, "secure.cdx")
        source["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        with self.assertRaisesRegex(CdxError, "Invalid bundle passphrase or corrupted bundle"):
            target["import_bundle"](bundle_path, passphrase="wrong")

    def test_import_merge_fills_missing_state_fields(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        source["record_status"]("main", {
            "remaining_5h_pct": 75,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        # Target has a local status already set.
        target["record_status"]("main", {
            "remaining_5h_pct": 90,
            "remaining_week_pct": 85,
            "updated_at": "2026-04-16T12:00:00+00:00",
        })

        target["import_bundle"](bundle_path, merge=True)

        imported = target["get_session"]("main")
        # Local status must be preserved (not overwritten by bundle).
        self.assertEqual(imported["lastStatus"]["remaining_5h_pct"], 90)
        self.assertEqual(imported["lastStatus"]["remaining_week_pct"], 85)

    def test_import_merge_preserves_local_session_state_file(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        runtime = target["start_session_runtime"]("main", {"label": "live-run"})

        target["import_bundle"](bundle_path, merge=True)

        state = target["ensure_session_state"]("main")
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["runtime"]["runId"], runtime["runId"])
        self.assertEqual(state["runtime"]["label"], "live-run")

    def test_import_merge_fills_gaps_from_bundle(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("main")
        source["record_status"]("main", {
            "remaining_5h_pct": 75,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("main")
        # Target has no status set, so bundle values should fill the gap.

        target["import_bundle"](bundle_path, merge=True)

        imported = target["get_session"]("main")
        self.assertEqual(imported["lastStatus"]["remaining_5h_pct"], 75)

    def _make_bundle_with_profile(self, name, provider, rel_path, content_str):
        import base64 as _b64

        from src.backup_bundle import encode_bundle
        payload = {
            "schema_version": 1,
            "sessions": [{"name": name, "provider": provider}],
            "states": {},
            "profiles": {
                name: [{"path": rel_path, "data_b64": _b64.b64encode(content_str.encode()).decode()}]
            },
        }
        return encode_bundle(payload)

    def test_import_merge_skips_existing_profile_files(self):
        temp_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": temp_dir})
        target["create_session"]("claude1", "claude")

        local_token_path = os.path.join(temp_dir, "profiles", "claude1", "auth.json")
        os.makedirs(os.path.dirname(local_token_path), exist_ok=True)
        with open(local_token_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"local-token"}')

        bundle_bytes = self._make_bundle_with_profile("claude1", "claude", "auth.json", '{"token":"bundle-token"}')
        bundle_path = os.path.join(temp_dir, "bundle.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(bundle_bytes)

        target["import_bundle"](bundle_path, merge=True)

        with open(local_token_path, encoding="utf-8") as handle:
            content = handle.read()
        # Existing local file must not be overwritten.
        self.assertEqual(content, '{"token":"local-token"}')

    def test_import_merge_imports_missing_profile_files(self):
        temp_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": temp_dir})
        target["create_session"]("claude1", "claude")
        # No local auth file — bundle should fill the gap.

        bundle_bytes = self._make_bundle_with_profile("claude1", "claude", "auth.json", '{"token":"bundle-token"}')
        bundle_path = os.path.join(temp_dir, "bundle.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(bundle_bytes)

        target["import_bundle"](bundle_path, merge=True)

        local_token_path = os.path.join(temp_dir, "profiles", "claude1", "auth.json")
        self.assertTrue(os.path.exists(local_token_path))
        with open(local_token_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"bundle-token"}')

    def test_import_merge_allows_new_sessions(self):
        source_dir = self.make_temp_dir()
        source = create_session_service({"base_dir": source_dir})
        source["create_session"]("alpha")
        source["create_session"]("beta")
        bundle_path = os.path.join(source_dir, "backup.cdx")
        source["export_bundle"](bundle_path)

        target_dir = self.make_temp_dir()
        target = create_session_service({"base_dir": target_dir})
        target["create_session"]("alpha")
        # beta doesn't exist locally — it should be imported normally.

        target["import_bundle"](bundle_path, merge=True)

        self.assertIsNotNone(target["get_session"]("alpha"))
        self.assertIsNotNone(target["get_session"]("beta"))

    def test_reset_date_formats_are_supported(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        from datetime import timedelta

        fixtures = [
            ("main1", [
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 21:51)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
            ], "time-only", "Apr 22 16:51"),
            ("main2", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets Thursday, April 17",
            ], None, "Apr 17"),
            ("main3", [
                "Current session",
                "12% used",
                "Current week",
                "34% used",
                "Resets April 17, 2026",
            ], None, "Apr 17"),
            ("main4", [
                "Current session",
                "12% used",
                "Resets at 5:00 AM",
                "Current week",
                "34% used",
                "Resets Thursday, April 17",
            ], "ampm-time-only", "Apr 17"),
            ("main5", [
                "Current session",
                "12% used",
                "Resets Thursday, April 17 at 5:00 AM",
                "Current week",
                "34% used",
                "Resets Thursday, April 24",
            ], "Apr 17 05:00", "Apr 24"),
        ]

        for name, lines, expected_5h, expected_week in fixtures:
            provider = "claude" if lines[0].startswith("Current session") else "codex"
            service["create_session"](name, provider if provider == "claude" else "codex")
            root = os.path.join(temp_dir, "profiles", name, "claude-home" if provider == "claude" else "")
            session_log = os.path.join(root, "log", "cdx-session.log")
            os.makedirs(os.path.dirname(session_log), exist_ok=True)
            with open(session_log, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            rows = [row for row in service["get_status_rows"]() if row["session_name"] == name]
            if expected_5h == "time-only":
                now = datetime.now().astimezone()
                candidate = datetime(now.year, now.month, now.day, 21, 51, tzinfo=now.tzinfo)
                if candidate <= now:
                    candidate = candidate + timedelta(days=1)
                expected_5h = f"{candidate.strftime('%b')} {candidate.day} 21:51"
            if expected_5h == "ampm-time-only":
                now = datetime.now().astimezone()
                candidate = datetime(now.year, now.month, now.day, 5, 0, tzinfo=now.tzinfo)
                if candidate <= now:
                    candidate = candidate + timedelta(days=1)
                expected_5h = f"{candidate.strftime('%b')} {candidate.day} 05:00"
            self.assertEqual(rows[0]["reset_5h_at"], expected_5h)
            self.assertEqual(rows[0]["reset_week_at"], expected_week)

    def test_claude_log_wins_over_newer_jsonl_noise(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude1", "claude")

        session_root = os.path.join(temp_dir, "profiles", "claude1", "claude-home")
        session_log = os.path.join(session_root, "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "Current session",
                "10% used",
                "Current week",
                "20% used",
                "Resets Thursday, April 17",
                "Extra usage",
            ]))

        rollout_path = os.path.join(session_root, "sessions", "2026", "04", "15", "rollout.jsonl")
        os.makedirs(os.path.dirname(rollout_path), exist_ok=True)
        with open(rollout_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": "2026-04-15T21:07:17.358831Z",
                "payload": {
                    "text": "\n".join([
                        "chat transcript",
                        "Current session",
                        "90% used",
                        "Current week",
                        "95% used",
                        "Resets Thursday, April 24",
                        "Extra usage",
                    ]),
                },
            }))
            handle.write("\n")

        rows = [row for row in service["get_status_rows"]() if row["session_name"] == "claude1"]
        self.assertEqual(rows[0]["remaining_5h_pct"], 90)
        self.assertEqual(rows[0]["remaining_week_pct"], 80)
        self.assertIsNone(rows[0]["reset_5h_at"])
        self.assertEqual(rows[0]["reset_week_at"], "Apr 17")
        self.assertEqual(rows[0]["reset_at"], "Apr 17")

    def test_codex_status_ignores_pasted_other_account_block(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work2")

        auth_path = os.path.join(temp_dir, "profiles", "work2", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "tokens": {
                    "id_token": "." + "eyJlbWFpbCI6ICJ0b21AZXhhbXBsZS5jb20ifQ" + ".",
                },
            }))

        session_log = os.path.join(temp_dir, "profiles", "work2", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(session_log), exist_ok=True)
        with open(session_log, "w", encoding="utf-8") as handle:
            handle.write("\n".join([
                "│  Account:              tom@example.com (Team)",
                "│  5h limit:             [████████████████░░░░] 81% left",
                "│                        (resets 03:48 on 16 Apr)",
                "│  Weekly limit:         [████████████████░░░░] 82% left",
                "│                        (resets 16:51 on 22 Apr)",
                "To continue this session, run codex resume work2-session",
                "",
                "pasted from another account:",
                "│  Account:              secondary@example.test (Business)",
                "│  5h limit:             [████████████████████] 100% left",
                "│                        (resets 04:38 on 16 Apr)",
                "│  Weekly limit:         [█░░░░░░░░░░░░░░░░░░░] 6% left",
                "│                        (resets 00:08 on 18 Apr)",
                "To continue this session, run codex resume other-session",
            ]))

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["session_name"], "work2")
        self.assertEqual(rows[0]["remaining_5h_pct"], 81)
        self.assertEqual(rows[0]["remaining_week_pct"], 82)
        self.assertEqual(rows[0]["reset_5h_at"], "Apr 16 03:48")
        self.assertEqual(rows[0]["reset_week_at"], "Apr 22 16:51")

    def test_update_session_state_does_a_locked_read_modify_write(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        store["add_session"]({"name": "main", "provider": "codex"})
        store["write_session_state"]("main", {"provider": "codex", "status": "ready", "runtime": {"status": "running"}})

        updated = store["update_session_state"]("main", lambda state: {**state, "rehydratedAt": "now"})
        self.assertEqual(updated["rehydratedAt"], "now")
        self.assertEqual(updated["runtime"], {"status": "running"})

        # Returning None means "no write": the state on disk is untouched.
        store["update_session_state"]("main", lambda state: None)
        self.assertEqual(store["read_session_state"]("main")["rehydratedAt"], "now")

    def test_launch_history_skips_torn_jsonl_lines(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        store["append_launch_history"]({"session_name": "main", "started_at": "one"})
        history_path = os.path.join(temp_dir, "state", "launch_history.jsonl")
        with open(history_path, "a", encoding="utf-8") as handle:
            handle.write('{"session_name": "broken"\n')
        store["append_launch_history"]({"session_name": "side", "started_at": "two"})

        entries = store["list_launch_history"](limit=0)

        self.assertEqual([entry["session_name"] for entry in entries], ["side", "main"])

    def test_status_rows_skip_session_removed_during_refresh(self):
        temp_dir = self.make_temp_dir()
        removed = {"done": False}

        def fetch_status(session, **_kwargs):
            if session["name"] == "main" and not removed["done"]:
                removed["done"] = True
                service["remove_session"]("main")
                return {"remaining_5h_pct": 80, "remaining_week_pct": 80}
            return None

        service = create_session_service({
            "base_dir": temp_dir,
            "fetchCodexRateLimits": fetch_status,
        })
        service["create_session"]("main")

        rows = service["get_status_rows"](force_refresh=True)

        self.assertEqual(rows, [])

    def test_concurrent_launch_setting_writes_keep_both_settings(self):
        import threading

        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        threads = [
            threading.Thread(target=service["set_launch_settings"], args=("main", {"model": "opus"})),
            threading.Thread(target=service["set_launch_settings"], args=("main", {"permission": "review"})),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        launch = service["get_session"]("main").get("launch") or {}
        self.assertEqual(launch.get("model"), "opus")
        self.assertEqual(launch.get("permission"), "review")

    def test_corrupted_sessions_json_raises(self):
        temp_dir = self.make_temp_dir()
        store_file = os.path.join(temp_dir, "sessions.json")
        os.makedirs(temp_dir, exist_ok=True)
        with open(store_file, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        store = create_session_store(temp_dir)
        with self.assertRaisesRegex(CdxError, "Corrupt JSON file"):
            store["list_sessions"]()

    def test_corrupted_state_file_fails_launch(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        state_path = os.path.join(temp_dir, "state", "main.json")
        with open(state_path, "w", encoding="utf-8") as handle:
            handle.write("{bad json")
        with self.assertRaisesRegex(CdxError, "Corrupt JSON file"):
            service["launch_session"]("main")

    def test_session_store_add_rolls_back_state_when_registry_save_fails(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        session = {
            "name": "main",
            "provider": "codex",
        }

        def write_json(file_path, value):
            if file_path.endswith("sessions.json"):
                raise OSError("registry write failed")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaisesRegex(OSError, "registry write failed"):
                store["add_session"](session)

        self.assertFalse(os.path.exists(os.path.join(temp_dir, "state", "main.json")))
        self.assertEqual(store["list_sessions"](), [])

    def test_session_store_remove_restores_state_when_registry_save_fails(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        session = {"name": "main", "provider": "codex"}
        store["add_session"](session)
        store["write_session_state"]("main", {"provider": "codex", "status": "custom"})

        def write_json(file_path, value):
            if file_path.endswith("sessions.json"):
                raise OSError("registry write failed")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaisesRegex(OSError, "registry write failed"):
                store["remove_session"]("main")

        self.assertEqual(store["get_session"]("main"), session)
        self.assertEqual(store["read_session_state"]("main")["status"], "custom")

    def test_session_store_rename_restores_state_path_when_registry_save_fails(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        session = {"name": "source", "provider": "codex"}
        store["add_session"](session)
        store["write_session_state"]("source", {"provider": "codex", "status": "custom"})

        def write_json(file_path, value):
            if file_path.endswith("sessions.json"):
                raise OSError("registry write failed")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaisesRegex(OSError, "registry write failed"):
                store["rename_session"]("source", "dest", lambda item: {**item, "name": "dest"})

        self.assertEqual(store["get_session"]("source"), session)
        self.assertIsNone(store["get_session"]("dest"))
        self.assertEqual(store["read_session_state"]("source")["status"], "custom")
        self.assertIsNone(store["read_session_state"]("dest"))

    def test_session_store_replace_restores_state_when_registry_save_fails(self):
        temp_dir = self.make_temp_dir()
        store = create_session_store(temp_dir)
        original = {"name": "main", "provider": "codex"}
        replacement = {"name": "main", "provider": "claude"}
        store["add_session"](original)
        store["write_session_state"]("main", {"provider": "codex", "status": "custom"})

        def write_json(file_path, value):
            if file_path.endswith("sessions.json"):
                raise OSError("registry write failed")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")

        with mock.patch("src.session_store._write_json", side_effect=write_json):
            with self.assertRaisesRegex(OSError, "registry write failed"):
                store["replace_session"]("main", replacement)

        self.assertEqual(store["get_session"]("main"), original)
        self.assertEqual(store["read_session_state"]("main")["status"], "custom")

    def test_session_store_uses_windows_file_locking_when_requested(self):
        temp_dir = self.make_temp_dir()
        calls = []
        fake_msvcrt = SimpleNamespace(
            LK_LOCK=1,
            LK_UNLCK=2,
            locking=lambda fd, mode, length: calls.append((fd, mode, length)),
        )

        with mock.patch("sys.platform", "win32"):
            with mock.patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
                store = create_session_store(temp_dir)
                store["list_sessions"]()

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1:], (1, 1))
        self.assertEqual(calls[1][1:], (2, 1))


if __name__ == "__main__":
    unittest.main()
