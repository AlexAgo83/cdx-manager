"""Tests for status, next, config, configs, last, history, stats.

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
    _format_blocking_quota,
    _format_reset_time,
    _format_status_detail,
    _format_status_rows,
    format_json_error,
    main,
)
from src.errors import CdxError
from src.session_service import create_session_service


class StatusCommandTests(CliTestBase):

    def test_reset_time_formatting_uses_countdown(self):
        now = datetime.now().astimezone()
        future = now + timedelta(hours=2, minutes=30)
        soon = now + timedelta(seconds=90)
        later = now + timedelta(days=2)
        later_with_hours = now + timedelta(days=2, hours=3)
        past = now - timedelta(hours=1, minutes=5)

        with mock.patch("src.status_view._now_timestamp", return_value=now.timestamp()):
            self.assertEqual(_format_reset_time(future.isoformat()), "in 2h 31m")
            self.assertEqual(_format_reset_time(soon.isoformat()), "in 2m")
            self.assertEqual(_format_reset_time(later.isoformat()), "in 2d")
            self.assertEqual(_format_reset_time(later_with_hours.isoformat()), "in 2d 3h")
            self.assertEqual(_format_reset_time(past.isoformat()), "passed 1h ago")

    def test_status_table_is_sorted_by_priority_availability(self):
        output = _format_status_rows([
            {
                "session_name": "blocked",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 0,
                "remaining_5h_pct": 0,
                "remaining_week_pct": 80,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "available",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 42,
                "remaining_5h_pct": 42,
                "remaining_week_pct": 90,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "credit",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 95,
                "remaining_5h_pct": 95,
                "remaining_week_pct": 95,
                "credits": 453,
                "reset_credits_available": 1,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        lines = output.splitlines()
        self.assertIn("AUTH", lines[0])
        self.assertIn("logged", lines[1])
        self.assertTrue(lines[1].startswith("available"))
        self.assertTrue(lines[2].startswith("credit"))
        self.assertTrue(lines[3].startswith("blocked"))

    def test_status_table_formats_credits_with_two_decimals(self):
        output = _format_status_rows([
            {
                "session_name": "credit",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 95,
                "remaining_5h_pct": 95,
                "remaining_week_pct": 95,
                "credits": "453.456",
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        self.assertRegex(output.splitlines()[1], r"\b453\.46\b")
        self.assertNotIn("453.456", output)

    def test_status_hides_empty_reset_columns_without_touching_active_signals(self):
        rows = [{"session_name": "work", "provider": "codex", "enabled": True, "reset_credits_available": "0", "reset_5h_at": None, "reset_week_at": None}]
        header = _format_status_rows(rows).splitlines()[0]
        self.assertNotIn("RESETS", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        rows[0]["reset_credits_available"] = "2"
        self.assertIn("RESETS", _format_status_rows(rows).splitlines()[0])

    def test_status_priority_skips_logged_out_sessions(self):
        output = _format_status_rows([
            {
                "session_name": "loggedout",
                "provider": "claude",
                "auth_status": "logged_out",
                "available_pct": 100,
                "remaining_5h_pct": 100,
                "remaining_week_pct": 100,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "loggedin",
                "provider": "claude",
                "auth_status": "authenticated",
                "available_pct": 50,
                "remaining_5h_pct": 50,
                "remaining_week_pct": 50,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        self.assertIn("Recommended: use loggedin first", output)
        self.assertNotIn("use loggedout", output)

    def test_status_auth_is_not_applicable_for_local_providers(self):
        output = _format_status_rows([
            {
                "session_name": "local",
                "provider": "ollama",
                "auth_status": "authenticated",
                "available_pct": None,
                "remaining_5h_pct": None,
                "remaining_week_pct": None,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "agy",
                "provider": "antigravity",
                "auth_status": "authenticated",
                "available_pct": None,
                "remaining_5h_pct": None,
                "remaining_week_pct": None,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ])

        lines = output.splitlines()
        # Ties break on session name ascending ("agy" before "local"). The old
        # recommendation ranking sorted names descending as a side effect of
        # reversing the whole sort tuple, disagreeing with the headless
        # ranking; the unified rule keeps the ascending order.
        self.assertRegex(lines[1], r"\bantigravity\s+enabled\s+n/a\b")
        self.assertRegex(lines[2], r"\bollama\s+enabled\s+n/a\b")

    def test_status_small_hides_metadata_columns(self):
        rows = [
            {
                "session_name": "main",
                "label": "work",
                "provider": "codex",
                "available_pct": 6,
                "remaining_5h_pct": 100,
                "remaining_week_pct": 6,
                "credits": 453,
                "reset_5h_at": "Apr 16 05:44",
                "reset_week_at": "Apr 18 00:08",
                "updated_at": "2026-04-15T10:00:00+00:00",
            },
            {
                "session_name": "claude",
                "provider": "claude",
                "available_pct": 0,
                "remaining_5h_pct": 0,
                "remaining_week_pct": 75,
                "credits": None,
                "reset_5h_at": "Apr 16 02:00",
                "reset_week_at": "Apr 21 14:00",
                "updated_at": "2026-04-15T10:00:00+00:00",
            },
        ]

        output = _format_status_rows(rows, small=True)
        header = output.splitlines()[0]
        self.assertIn("SESSION", header)
        self.assertIn("OK", header)
        self.assertIn("5H", header)
        self.assertIn("WEEK", header)
        self.assertIn("RESET 5H", header)
        self.assertIn("RESET WEEK", header)
        self.assertNotIn("RESETS", header)
        self.assertNotIn("LABEL", header)
        self.assertNotIn("PROV.", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        self.assertNotIn("UPDATED", header)
        self.assertIn("Recommended:", output)
        self.assertIn("Current:", output)
        self.assertNotIn("Tip:", output)

    def test_status_full_shows_label_column_only_when_present(self):
        rows = [
            {
                "session_name": "main",
                "label": "work",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 80,
                "remaining_5h_pct": 80,
                "remaining_week_pct": 80,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
            {
                "session_name": "side",
                "provider": "codex",
                "auth_status": "authenticated",
                "available_pct": 70,
                "remaining_5h_pct": 70,
                "remaining_week_pct": 70,
                "credits": None,
                "reset_5h_at": None,
                "reset_week_at": None,
                "updated_at": None,
            },
        ]

        output = _format_status_rows(rows)
        self.assertIn("LABEL", output.splitlines()[0])
        self.assertRegex(output, r"\bmain\s+work\s+enabled\b")
        self.assertRegex(output, r"\bside\s+-\s+enabled\b")

        no_label = _format_status_rows([{**row, "label": None} for row in rows])
        self.assertNotIn("LABEL", no_label.splitlines()[0])

    def test_status_detail_shows_banked_reset_expiry(self):
        output = _format_status_detail({
            "session_name": "main",
            "provider": "codex",
            "reset_credits_available": 1,
            "reset_credits": [{"expires_at": "2099-07-20T10:00:00+00:00"}],
        })

        self.assertIn("Bonus resets: 1", output)
        self.assertIn("Reset expiry:", output)

    def test_blocking_quota_formatting_identifies_lowest_limit(self):
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
        }), "-")
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 99,
            "remaining_week_pct": 0,
        }), "WEEK")
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
        }), "5H")
        self.assertEqual(_format_blocking_quota({
            "remaining_5h_pct": 0,
            "remaining_week_pct": 0,
        }), "5H+WEEK")

    def test_last_launches_most_recent_existing_session(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        for name in ("first", "second"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main(["first"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["second"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        last_io = self.make_io()
        self.assertEqual(main(["last"], {
            **last_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        output = last_io["stdout"].getvalue()
        self.assertIn("Launching last session: second", output)
        self.assertIn("Launching codex session second", output)
        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertTrue(
            _script_transcript_path(launch_call).startswith(os.path.join(temp_dir, "profiles", "second", "log", "cdx-session-"))
        )

    def test_last_skips_removed_sessions_and_supports_json(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        for name in ("first", "second"):
            self.assertEqual(main(["add", name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)
            self.assertEqual(main([name], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main(["rmv", "second", "--force"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        last_io = self.make_io()
        self.assertEqual(main(["last", "--json"], {
            **last_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(last_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "launch")
        self.assertEqual(payload["session"]["name"], "first")

    def test_last_requires_launch_history(self):
        temp_dir = self.make_temp_dir()

        with self.assertRaisesRegex(CdxError, "No launch history yet"):
            main(["last"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_history_summary_filters_by_period(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        service["create_session"]("personal")
        now = datetime(2026, 5, 28, 12, 0, 0).astimezone()
        recent = now - timedelta(days=2)
        old = now - timedelta(days=10)
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 120000,
            "started_at": recent.isoformat(),
            "ended_at": (recent + timedelta(minutes=2)).isoformat(),
        })
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 300000,
            "started_at": old.isoformat(),
            "ended_at": (old + timedelta(minutes=5)).isoformat(),
        })
        service["record_launch_history"]("personal", {
            "status": "failed",
            "duration_ms": 60000,
            "started_at": recent.isoformat(),
            "ended_at": (recent + timedelta(minutes=1)).isoformat(),
        })

        summary_io = self.make_io()
        self.assertEqual(main(["history", "--summary", "--since", "7d", "--json"], {
            **summary_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: now.timestamp(),
        }), 0)
        payload = json.loads(summary_io["stdout"].getvalue())
        rows = {row["session_name"]: row for row in payload["summary"]}
        self.assertEqual(set(rows), {"work", "personal"})
        self.assertEqual(rows["work"]["duration_ms"], 120000)
        self.assertEqual(rows["personal"]["failures"], 1)
        self.assertIsNotNone(payload["period"]["from"])
        self.assertIsNone(payload["period"]["to"])

        text_io = self.make_io()
        self.assertEqual(main(["history", "--summary", "--from", recent.date().isoformat(), "--to", now.date().isoformat()], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: now.timestamp(),
        }), 0)
        output = text_io["stdout"].getvalue()
        self.assertIn("Period:", output)
        self.assertIn("work", output)
        self.assertNotIn("5m00s", output)

    def test_stats_aggregates_known_usage_by_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        service["create_session"]("personal")
        now = datetime(2026, 5, 28, 12, 0, 0).astimezone()
        recent = now - timedelta(days=1)
        old = now - timedelta(days=9)
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 7500000,
            "started_at": recent.isoformat(),
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 7,
                "output_tokens": 4,
                "reasoning_tokens": 2,
                "total_tokens": 14,
            },
        })
        service["record_launch_history"]("work", {
            "status": "failed",
            "duration_ms": 30000,
            "started_at": recent.isoformat(),
            "usage": {
                "input_tokens": 3,
                "output_tokens": 0,
                "total_tokens": 3,
            },
        })
        service["record_launch_history"]("work", {
            "status": "success",
            "duration_ms": 60000,
            "started_at": old.isoformat(),
            "usage": {"total_tokens": 99},
        })
        service["record_launch_history"]("personal", {
            "status": "success",
            "duration_ms": 1000,
            "started_at": recent.isoformat(),
        })

        stats_io = self.make_io()
        self.assertEqual(main(["stats", "--since", "7d", "--json"], {
            **stats_io,
            "service": service,
            "now": lambda: now.timestamp(),
        }), 0)

        payload = json.loads(stats_io["stdout"].getvalue())
        rows = {row["session_name"]: row for row in payload["stats"]}
        self.assertEqual(rows["work"]["launches"], 2)
        self.assertEqual(rows["work"]["failures"], 1)
        # These fixtures are legacy-shaped: a fused `cached_input_tokens` and
        # no creation/read split. Such records are excluded from every total
        # rather than displayed -- they are fictitious, not merely old -- and
        # counted so the exclusion is visible.
        self.assertEqual(rows["work"]["usage_runs"], 0)
        self.assertEqual(rows["work"]["unvouched_runs"], 2)
        self.assertEqual(rows["work"]["total_tokens"], 0)
        self.assertEqual(rows["personal"]["usage_runs"], 0)
        self.assertEqual(payload["totals"]["total_tokens"], 0)
        self.assertEqual(payload["totals"]["unvouched_runs"], 2)

        service["start_session_runtime"]("work", {"pid": os.getpid()})

        text_io = self.make_io()
        self.assertEqual(main(["stats", "work", "--since", "7d"], {
            **text_io,
            "service": service,
            "now": lambda: now.timestamp(),
        }), 0)
        output = text_io["stdout"].getvalue()
        self.assertIn("Assistant stats:", output)
        self.assertIn("work*", output)
        self.assertIn("2h 05m", output)
        self.assertIn("0 tokens", output)

        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["stats", "work", "--since", "7d"], {
            **color_io,
            "service": service,
            "env": {"CLICOLOR_FORCE": "1"},
            "now": lambda: now.timestamp(),
        }), 0)
        self.assertIn("\033[", color_io["stdout"].getvalue())

        with self.assertRaisesRegex(CdxError, "Usage: cdx stats"):
            main(["stats", "--since", "7d", "--from", "2026-05-28"], {
                **self.make_io(),
                "service": service,
                "now": lambda: now.timestamp(),
            })

    def test_configs_lists_all_launch_settings_in_table(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "work"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["add", "claude", "personal"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["set", "work", "--power", "high", "--permission", "auto", "--fast", "off", "--rtk", "on", "--priority", "80"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        configs_io = self.make_io()
        self.assertEqual(main(["configs"], {
            **configs_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = configs_io["stdout"].getvalue()
        self.assertIn("Launch settings:", output)
        self.assertIn("SESSION", output)
        self.assertIn("PROVIDER", output)
        self.assertIn("POWER", output)
        self.assertIn("PERMISSION", output)
        self.assertIn("FAST", output)
        self.assertIn("RTK", output)
        self.assertIn("ALERTS", output)
        self.assertIn("PRIORITY", output)
        self.assertIn("work", output)
        self.assertIn("codex", output)
        self.assertIn("high", output)
        self.assertIn("auto", output)
        self.assertIn("off", output)
        self.assertIn("on", output)
        self.assertIn("80", output)
        self.assertIn("personal", output)
        self.assertIn("default", output)
        self.assertIn(
            "Set a value: cdx set <name> --power medium --permission auto --fast on --rtk on --logics on --notify on --notify-preview on --model MODEL --priority 80",
            output,
        )

    def test_configs_json_lists_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "work"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        self.assertEqual(main(["set", "work", "--power", "medium"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        configs_io = self.make_io()
        self.assertEqual(main(["configs", "--json"], {
            **configs_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(configs_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "configs")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["sessions"][0]["name"], "work")
        self.assertEqual(payload["sessions"][0]["launch"]["power"], "medium")

    def test_config_unknown_session_suggests_configs_and_add(self):
        temp_dir = self.make_temp_dir()
        io_obj = self.make_io()

        with self.assertRaisesRegex(CdxError, "Unknown session: configs\\. Run cdx configs") as ctx:
            main(["config", "configs"], {**io_obj, "env": {"CDX_HOME": temp_dir}})

        self.assertIn("cdx add configs", str(ctx.exception))
        payload = json.loads(format_json_error(ctx.exception))
        self.assertEqual(payload["error"]["code"], "unknown_session")
        self.assertIn("Run cdx configs", payload["error"]["message"])

    def test_config_usage_errors_remain_unchanged(self):
        for args in (["config"], ["config", "one", "two"]):
            with self.subTest(args=args):
                with self.assertRaisesRegex(CdxError, "Usage: cdx config <name> \\[--json\\]"):
                    main(args, self.make_io())

    def test_status_parser_rejects_small_detail_and_supports_refresh(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        with self.assertRaisesRegex(CdxError, "Usage: cdx status"):
            main(["status", "main", "-s"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh", "--json"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertEqual(json.loads(status_io["stdout"].getvalue())["action"], "status")

    def test_status_uses_sync_refresh_function(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work1", "claude")

        def refresh(_session):
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
        self.assertNotIn("CR", output)
        self.assertNotIn("AVAIL.", output)
        self.assertNotIn("AVAILABLE", output)
        self.assertNotIn("CREDITS", output)
        self.assertIn("80%", output)
        self.assertIn("60%", output)
        self.assertIn("RESET 5H", output)
        self.assertIn("RESET WEEK", output)
        self.assertIn("Recommended: use work1 first (60% OK).", output)

    def test_status_text_shows_progress_but_json_stays_clean(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["launch_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertIn("Resolving status for 1 session(s)...", output)
        self.assertIn("Checking main (codex)...", output)
        self.assertIn("Checked main (1/1).", output)
        self.assertIn("Resolved 1 status row(s).", output)
        self.assertIn("Current: last launched main (just now).", output)

        json_io = self.make_io()
        self.assertEqual(main(["status", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "status")
        self.assertIsNotNone(payload["rows"][0]["last_launched_at"])
        self.assertNotIn("Resolving status", json_io["stdout"].getvalue())

    def test_status_surfaces_update_notice_at_end(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        lines = [line for line in status_io["stdout"].getvalue().splitlines() if line]
        self.assertTrue(lines[-1].startswith("Update available: cdx-manager 9.9.9"))
        self.assertIn("Run: cdx update", lines[-1])
        self.assertNotIn("https://example.invalid/release", lines[-1])

    def test_status_json_includes_update_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--json"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "update_available")
        self.assertEqual(payload["warnings"][0]["latest_version"], "9.9.9")

    def test_status_and_list_mark_active_session_with_star(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["start_session_runtime"]("main", {"pid": os.getpid()})
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertRegex(list_io["stdout"].getvalue(), r"main\*\s+enabled")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertRegex(status_io["stdout"].getvalue(), r"main\*\s+enabled")

    def test_status_cached_rows_do_not_show_session_checking_progress(self):
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

        first_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **first_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Checking main (codex)...", first_io["stdout"].getvalue())
        self.assertIn("Checked main (1/1).", first_io["stdout"].getvalue())

        second_io = self.make_io()
        self.assertEqual(main(["status"], {
            **second_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertNotIn("Checking main (codex)...", second_io["stdout"].getvalue())
        self.assertNotIn("Checked main", second_io["stdout"].getvalue())
        self.assertEqual(len(calls), 1)

    def test_status_cached_claude_rows_do_not_show_checking_progress_within_refresh_ttl(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": (datetime.now().astimezone() - timedelta(minutes=2)).isoformat(),
        })

        def refresh(_session):
            raise AssertionError("Claude cache inside refresh TTL should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertNotIn("Checking claude (claude)...", output)
        self.assertIn("60%", output)

    def test_status_disabled_claude_rows_do_not_show_checking_progress(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["set_session_enabled"]("claude", False)
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        def refresh(_session):
            raise AssertionError("disabled Claude sessions should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        output = status_io["stdout"].getvalue()
        self.assertNotIn("Checking claude (claude)...", output)
        self.assertIn("disabled", output)
        self.assertNotIn("80%", output)
        self.assertNotIn("60%", output)
        self.assertRegex(output, r"claude\s+disabled\s+-\s+-\s+-")

    def test_status_reports_no_current_session_when_none_launched(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("Current: no launched session known yet.", status_io["stdout"].getvalue())

    def test_status_skips_fresh_claude_refresh_unless_forced(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        def refresh(_session):
            raise AssertionError("fresh status should not refresh")

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("80%", status_io["stdout"].getvalue())

        def forced_refresh(_session):
            return {
                "remaining_5h_pct": 55,
                "remaining_week_pct": 44,
                "updated_at": datetime.now().astimezone().isoformat(),
            }

        refresh_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **refresh_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": forced_refresh,
        }), 0)
        self.assertIn("44%", refresh_io["stdout"].getvalue())

    def test_status_detail_refreshes_only_requested_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["create_session"]("claude", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 70,
            "remaining_week_pct": 70,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        def refresh(_session):
            raise AssertionError("unrequested Claude session should not refresh")

        detail_io = self.make_io()
        self.assertEqual(main(["status", "main"], {
            **detail_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("Session: main", detail_io["stdout"].getvalue())

    def test_status_surfaces_claude_refresh_errors(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")

        def refresh(_session):
            raise RuntimeError("offline")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn("Warning: Claude refresh failed for claude: offline", status_io["stdout"].getvalue())

        json_io = self.make_io()
        self.assertEqual(main(["status", "--json", "--refresh"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["action"], "status")
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["warnings"][0]["code"], "claude_refresh_failed")
        self.assertEqual(json_io["stderr"].getvalue(), "")

    def test_status_keeps_claude_auth_after_invalid_usage_auth_when_probe_succeeds(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def refresh(_session):
            from src.claude_usage import ClaudeAuthInvalidError

            raise ClaudeAuthInvalidError("Claude usage unavailable (HTTP 401: Invalid authentication credentials)")

        status_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--json", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness(initial_auth={
                service["get_session"]("claude")["authHome"]: True,
            }).spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["code"], "claude_refresh_failed")
        self.assertEqual(payload["warnings"][0]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["status_freshness"], "stale")
        self.assertIn("local Claude auth is still valid", payload["warnings"][0]["message"])

        text_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--refresh"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness(initial_auth={
                service["get_session"]("claude")["authHome"]: True,
            }).spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)
        self.assertIn(
            "Warning: Claude quota refresh failed for claude, but local auth is still valid; cached quota may be stale.",
            text_io["stdout"].getvalue(),
        )

    def test_status_rechecks_claude_auth_before_usage_refresh(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def refresh(_session):
            raise AssertionError("logged out Claude sessions should not refresh usage")

        status_io = self.make_io()
        self.assertEqual(main(["status", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness().spawn_sync,
            "refreshClaudeSessionStatus": refresh,
        }), 0)

        rows = service["get_status_rows"]()
        self.assertEqual(rows[0]["auth_status"], "logged_out")
        self.assertIn("logged out", status_io["stdout"].getvalue())

    def test_status_keeps_claude_auth_when_probe_times_out(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("claude", "claude")
        service["update_auth_state"]("claude", lambda auth: {
            **auth,
            "status": "authenticated",
        })

        def timeout_probe(_command, _args, _spec):
            raise subprocess.TimeoutExpired("claude", 15)

        status_io = self.make_io()
        self.assertEqual(main(["status", "claude", "--json", "--refresh"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": timeout_probe,
            "refreshClaudeSessionStatus": lambda _session: None,
        }), 0)

        self.assertEqual(service["get_session"]("claude")["auth"]["status"], "authenticated")
        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["auth_status"], "authenticated")
        self.assertEqual(payload["warnings"][0]["code"], "claude_auth_probe_failed")
        self.assertIn("timed out", payload["warnings"][0]["message"])

    def test_status_small_flag_renders_compact_table(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main", "codex")
        service["create_session"]("claude", "claude")
        service["record_status"]("main", {
            "remaining_5h_pct": 99,
            "remaining_week_pct": 10,
            "credits": 453,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 17 10:10",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 60,
            "reset_5h_at": "Apr 16 02:21",
            "reset_week_at": "Apr 17 10:10",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "-s"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = status_io["stdout"].getvalue()
        header = next(line for line in output.splitlines() if line.startswith("SESSION"))
        self.assertIn("SESSION", header)
        self.assertIn("RESET 5H", header)
        self.assertNotIn("PROV.", header)
        self.assertNotIn("BLOCK", header)
        self.assertNotIn("CR", header)
        self.assertNotIn("UPDATED", header)
        self.assertIn("claude", output)
        self.assertIn("main", output)

    def test_status_color_respects_env_flags(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["record_status"]("main", {
            "remaining_5h_pct": -10,
            "remaining_week_pct": 95,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["create_session"]("secondary")
        service["record_status"]("secondary", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        color_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["status"], {
            **color_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"},
        }), 0)
        color_output = color_io["stdout"].getvalue()
        self.assertIn("\033[", color_output)
        self.assertIn("\033[31m0%\033[0m", color_output)
        self.assertIn("\033[32m80%\033[0m", color_output)
        self.assertIn("\033[96m95%\033[0m", color_output)

        plain_io = {**self.make_io(), "stdout": _TtyStream()}
        self.assertEqual(main(["status"], {
            **plain_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1", "NO_COLOR": "1"},
        }), 0)
        self.assertNotIn("\033[", plain_io["stdout"].getvalue())

    def test_status_recommends_non_credit_session_first(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("credit")
        service["create_session"]("regular")
        service["record_status"]("credit", {
            "remaining_5h_pct": 95,
            "remaining_week_pct": 95,
            "credits": 453,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("regular", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T09:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Recommended: use regular first (80% OK), next credit (95% OK).",
            status_io["stdout"].getvalue(),
        )

    def test_next_uses_same_priority_recommendation_as_status(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("credit")
        service["create_session"]("regular")
        service["record_status"]("credit", {
            "remaining_5h_pct": 95,
            "remaining_week_pct": 95,
            "credits": 453,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("regular", {
            "remaining_5h_pct": 80,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T09:00:00+00:00",
        })

        next_io = self.make_io()
        self.assertEqual(main(["next"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        output = next_io["stdout"].getvalue()
        self.assertIn("Next assistant:", output)
        self.assertIn("regular", output)
        self.assertIn("use regular first (80% OK)", output)
        self.assertIn("Run: cdx regular", output)

        json_io = self.make_io()
        self.assertEqual(main(["next", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "next")
        self.assertEqual(payload["recommended_action"], "use")
        self.assertEqual(payload["session"]["name"], "regular")
        self.assertEqual(payload["command"], "cdx regular")
        self.assertEqual(payload["selection_policy"], "status_priority")

    def test_next_reports_no_suitable_session(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        next_io = self.make_io()
        self.assertEqual(main(["next", "--json"], {
            **next_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 1)
        payload = json.loads(next_io["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "no_suitable_session")

    def test_status_treats_five_percent_available_as_empty_for_priority(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("low")
        service["create_session"]("usable")
        service["record_status"]("low", {
            "remaining_5h_pct": 5,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("usable", {
            "remaining_5h_pct": 6,
            "remaining_week_pct": 80,
            "updated_at": "2026-04-15T10:00:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = status_io["stdout"].getvalue()
        self.assertIn("low", output)
        self.assertIn("5%", output)
        self.assertIn(
            "Recommended: use usable first (6% OK), next low (0% OK).",
            output,
        )

    def test_status_recommends_earliest_blocking_reset_for_zero_ok(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        future = datetime.now() + timedelta(days=1)
        later = future + timedelta(hours=1)
        service["create_session"]("work1")
        service["create_session"]("work2")
        service["create_session"]("claude", "claude")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("work2", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 69,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
            "reset_5h_at": future.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Recommended: use work1 first (6% OK), next claude (0% OK, 5H resets first).",
            status_io["stdout"].getvalue(),
        )

    def test_status_uses_blocking_reset_before_credit_penalty_for_blocked_accounts(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        soon = datetime.now() + timedelta(hours=1)
        later = datetime.now() + timedelta(hours=2)
        service["create_session"]("work1")
        service["create_session"]("credit")
        service["create_session"]("regular")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("credit", {
            "remaining_5h_pct": 99,
            "remaining_week_pct": 0,
            "credits": 453,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": soon.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("regular", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 80,
            "reset_5h_at": later.astimezone().isoformat(),
            "reset_week_at": later.astimezone().isoformat(),
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Recommended: use work1 first (6% OK), next credit (0% OK, WEEK resets first).",
            status_io["stdout"].getvalue(),
        )

    def test_status_recommends_refresh_when_blocking_reset_has_passed(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        past = datetime.now() - timedelta(hours=1)
        later_past = datetime.now() - timedelta(minutes=30)
        service["create_session"]("work1")
        service["create_session"]("work2")
        service["create_session"]("claude", "claude")
        service["record_status"]("work1", {
            "remaining_5h_pct": 100,
            "remaining_week_pct": 6,
            "reset_5h_at": "Apr 16 05:44",
            "reset_week_at": "Apr 18 00:08",
            "updated_at": "2026-04-15T10:00:00+00:00",
        })
        service["record_status"]("work2", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 69,
            "reset_5h_at": later_past.astimezone().isoformat(),
            "reset_week_at": "Apr 22 16:51",
            "updated_at": "2026-04-15T10:01:00+00:00",
        })
        service["record_status"]("claude", {
            "remaining_5h_pct": 0,
            "remaining_week_pct": 75,
            "reset_5h_at": past.astimezone().isoformat(),
            "reset_week_at": "Apr 21 14:00",
            "updated_at": "2026-04-15T10:02:00+00:00",
        })

        status_io = self.make_io()
        self.assertEqual(main(["status"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertIn(
            "Recommended: use work1 first (6% OK), refresh claude next (0% OK, 5H reset passed).",
            status_io["stdout"].getvalue(),
        )

    def test_status_json_global_and_detail_contract(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_session_label"]("main", "work")
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
        payload = json.loads(global_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        rows = payload["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_name"], "main")
        self.assertEqual(rows[0]["label"], "work")
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
        detail_payload = json.loads(detail_io["stdout"].getvalue())
        self.assertEqual(detail_payload["schema_version"], 1)
        row = detail_payload["session"]
        self.assertEqual(row["session_name"], "main")
        self.assertEqual(row["label"], "work")
        self.assertEqual(row["available_pct"], 39)
        self.assertEqual(row["credits"], 453)
        self.assertEqual(row["reset_5h_at"], "Apr 16 02:21")
        self.assertEqual(row["reset_week_at"], "Apr 17 10:10")
        self.assertEqual(row["reset_at"], "Apr 17 10:10")

    def test_status_detail_refreshes_only_named_session(self):
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

        detail_io = self.make_io()
        self.assertEqual(main(["status", "work1", "--json", "--refresh"], {
            **detail_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(detail_io["stdout"].getvalue())
        self.assertEqual(calls, ["work1"])
        self.assertEqual(payload["session"]["session_name"], "work1")
        self.assertEqual(payload["session"]["available_pct"], 70)

    def test_status_cached_skips_provider_refresh(self):
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
        service["record_status"]("main", {
            "remaining_5h_pct": 33,
            "remaining_week_pct": 66,
            "updated_at": datetime.now().astimezone().isoformat(),
        })

        status_io = self.make_io()
        self.assertEqual(main(["status", "--json", "--cached"], {
            **status_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(calls, [])
        self.assertEqual(payload["rows"][0]["session_name"], "main")
        self.assertEqual(payload["rows"][0]["available_pct"], 33)

    def test_status_timeout_flag_applies_to_codex_fetch(self):
        temp_dir = self.make_temp_dir()
        with mock.patch("src.session_service.fetch_codex_rate_limits", return_value={
            "remaining_5h_pct": 80,
            "remaining_week_pct": 70,
            "updated_at": datetime.now().astimezone().isoformat(),
        }) as fetch_status:
            service = create_session_service({"base_dir": temp_dir})
            service["create_session"]("main")

            status_io = self.make_io()
            self.assertEqual(main(["status", "main", "--json", "--refresh", "--timeout", "0.5"], {
                **status_io,
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            }), 0)

        payload = json.loads(status_io["stdout"].getvalue())
        self.assertEqual(payload["session"]["available_pct"], 70)
        self.assertEqual(fetch_status.call_args.kwargs["timeout"], 0.5)

    def test_status_empty_json_is_stable(self):
        temp_dir = self.make_temp_dir()
        io_obj = self.make_io()
        self.assertEqual(main(["status", "--json"], {**io_obj, "env": {"CDX_HOME": temp_dir}}), 0)
        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["rows"], [])

    def test_priority_orders_two_otherwise_equal_sessions(self):
        names, decision = self._ranked([
            self._row("plain"),
            self._row("preferred", priority=90),
        ])

        self.assertEqual(names[0], "preferred")
        self.assertEqual(decision, "priority")

    def test_priority_does_not_promote_a_session_that_cannot_serve(self):
        names, _ = self._ranked([
            self._row("usable", available_pct=40),
            self._row("empty", available_pct=0, priority=99),
        ])

        # Priority says which usable session to prefer. It does not make an
        # exhausted session the right place to send work.
        self.assertEqual(names[0], "usable")

    def test_recommendation_still_surfaces_unknown_auth_sessions(self):
        names, _ = self._ranked([self._row("unknown", auth_status="unknown")])

        # Without require_ready (cdx next, cdx status) an unverified session is
        # still worth showing; it is only excluded from being run.
        self.assertEqual(names, ["unknown"])
