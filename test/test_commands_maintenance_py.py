"""Tests for doctor, repair, clean, disk, update.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
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
    _get_disk_cleanup_notice,
    main,
)
from src.cli_commands import _format_update_all, _format_update_all_result
from src.errors import CdxError
from src.health import collect_health_report
from src.session_service import create_session_service


class MaintenanceCommandTests(CliTestBase):

    def test_update_all_format_is_scannable_and_colored(self):
        plan = {
            "items": [{"name": "codex", "version": "1.0.0", "latest_version": "1.1.0", "status": "update_available"}],
            "setup": {"rtk_missing_sessions": ["main"], "ponytail": [{"session": "main", "status": "up_to_date"}]},
            "steps": [{"name": "codex"}],
        }
        plain = _format_update_all(plan)
        colored = _format_update_all(plan, use_color=True)
        self.assertIn("Inventory only", plain)
        self.assertIn("CURRENT", plain)
        self.assertIn("Session setup", plain)
        self.assertIn("1 action(s) ready", plain)
        self.assertIn("\033[", colored)

    def test_update_all_failure_includes_its_reason(self):
        text = _format_update_all_result({"name": "Claude Code", "command": ["brew", "upgrade", "--cask", "claude-code@latest"], "returncode": 1, "stderr": "network unavailable"})
        self.assertIn("exit 1", text)
        self.assertIn("network unavailable", text)
        self.assertIn("claude-code@latest", text)
        self.assertIn("blocked by marketplace", _format_update_all_result({"name": "install", "skipped": True, "blocked_by": "marketplace"}))

    def test_disk_reports_cdx_home_size(self):
        temp_dir = self.make_temp_dir()
        disk_io = self.make_io()

        self.assertEqual(main(["disk"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1536\t{temp_dir}\n",
        }), 0)

        self.assertEqual(disk_io["stdout"].getvalue().splitlines(), [
            "CDX home",
            f"Path:  {temp_dir}",
            "Total: 1.5 MB",
        ])

    def test_disk_json_reports_cdx_home_size(self):
        temp_dir = self.make_temp_dir()
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"2048\t{temp_dir}\n",
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "disk")
        self.assertEqual(payload["disk"]["target"], "home")
        self.assertEqual(payload["disk"]["path"], temp_dir)
        self.assertEqual(payload["disk"]["bytes"], 2097152)
        self.assertEqual(payload["disk"]["size"], "2 MB")

    def test_disk_profiles_reports_profiles_size(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        os.makedirs(profiles_dir)
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"4096\t{profiles_dir}\n",
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        self.assertEqual(payload["disk"]["target"], "profiles")
        self.assertEqual(payload["disk"]["path"], profiles_dir)
        self.assertEqual(payload["disk"]["bytes"], 4194304)
        self.assertEqual(payload["disk"]["size"], "4 MB")

    def test_disk_profiles_prints_profile_breakdown(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        main_dir = os.path.join(profiles_dir, "main")
        work_dir = os.path.join(profiles_dir, "work")
        os.makedirs(main_dir)
        os.makedirs(work_dir)
        sizes = {
            profiles_dir: "4096",
            main_dir: "3072",
            work_dir: "1024",
        }
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"{sizes[argv[2]]}\t{argv[2]}\n",
        }), 0)

        output = disk_io["stdout"].getvalue()
        self.assertIn("CDX profiles", output)
        self.assertIn(f"Path:  {profiles_dir}", output)
        self.assertIn("Total: 4 MB", output)
        self.assertIn("PROFILE  SIZE  SHARE", output)
        self.assertRegex(output, r"main\s+3 MB\s+75\.0%")
        self.assertRegex(output, r"work\s+1 MB\s+25\.0%")

    def test_disk_profiles_reports_progress_on_interactive_stderr(self):
        temp_dir = self.make_temp_dir()
        profiles_dir = os.path.join(temp_dir, "profiles")
        profile_dir = os.path.join(profiles_dir, "main")
        os.makedirs(profile_dir)
        disk_io = {**self.make_io(), "stderr": _TtyStream()}

        self.assertEqual(main(["disk", "profiles"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1\t{argv[2]}\n",
        }), 0)

        progress = disk_io["stderr"].getvalue()
        self.assertIn("Measuring CDX profiles disk usage", progress)
        self.assertIn("Measuring profile main (1/1)", progress)

    def test_disk_json_keeps_interactive_stderr_empty(self):
        temp_dir = self.make_temp_dir()
        disk_io = {**self.make_io(), "stderr": _TtyStream()}

        self.assertEqual(main(["disk", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1\t{argv[2]}\n",
        }), 0)

        self.assertEqual(disk_io["stderr"].getvalue(), "")

    def test_disk_candidates_rejects_home_before_scanning(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx disk"):
            main(["disk", "--candidates"], {
                **self.make_io(),
                "env": {"CDX_HOME": self.make_temp_dir()},
                "diskUsageRunner": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not scan")),
            })

    def test_disk_profiles_candidates_report_cleanup_evidence(self):
        temp_dir = self.make_temp_dir()
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        clone_dir = os.path.join(profile_dir, ".tmp", "plugins-clone-test")
        log_dir = os.path.join(profile_dir, "log")
        os.makedirs(marketplace_dir)
        os.makedirs(clone_dir)
        os.makedirs(log_dir)
        for path in (
            os.path.join(marketplace_dir, "cache.bin"),
            os.path.join(clone_dir, "clone.bin"),
            os.path.join(log_dir, "old.log"),
        ):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)
        os.utime(os.path.join(log_dir, "old.log"), (1000, 1000))

        disk_io = self.make_io()
        self.assertEqual(main(["disk", "profiles", "--candidates", "--json"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(disk_io["stdout"].getvalue())
        candidates = payload["disk"]["candidates"]
        self.assertEqual({item["kind"] for item in candidates}, {"tmp-marketplaces", "tmp-plugin-clone", "old-logs-30d"})
        old_logs = next(item for item in candidates if item["kind"] == "old-logs-30d")
        self.assertEqual(old_logs["risk"], "review")
        self.assertEqual(old_logs["evidence"]["file_count"], 1)

    def test_disk_profiles_candidates_prints_aligned_report(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        with open(os.path.join(marketplace_dir, "cache.bin"), "wb") as handle:
            handle.write(b"x")
        disk_io = self.make_io()

        self.assertEqual(main(["disk", "profiles", "--candidates"], {
            **disk_io,
            "env": {"CDX_HOME": temp_dir},
            "diskUsageRunner": lambda argv, **kwargs: f"1024\t{argv[2]}\n",
        }), 0)

        output = disk_io["stdout"].getvalue()
        self.assertRegex(output, r"PROFILE\s+SIZE\s+SHARE\s+RECLAIMABLE")
        self.assertIn("Cleanup candidates", output)
        self.assertIn("SIZE  TYPE", output)
        self.assertIn("RISK  EVIDENCE", output)
        self.assertRegex(output, r"1 MB\s+tmp-marketplaces\s+safe\s+temporary marketplace cache/staging")

    def test_clean_profiles_tmp_removes_temporary_candidates(self):
        temp_dir = self.make_temp_dir()
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        backup_dir = os.path.join(profile_dir, ".tmp", "plugins-backup-test")
        os.makedirs(marketplace_dir)
        os.makedirs(backup_dir)
        for path in (
            os.path.join(marketplace_dir, "cache.bin"),
            os.path.join(backup_dir, "backup.bin"),
        ):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--tmp", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "clean.profiles")
        self.assertFalse(os.path.exists(marketplace_dir))
        self.assertFalse(os.path.exists(backup_dir))
        self.assertEqual(payload["profiles"][0]["profile"], "main")

    def test_clean_profiles_tmp_reports_removal_failure(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        with open(os.path.join(marketplace_dir, "cache.bin"), "wb") as handle:
            handle.write(b"x")

        with mock.patch("src.commands.maintenance.shutil.rmtree", side_effect=OSError("permission denied")):
            with self.assertRaisesRegex(CdxError, "Failed to remove cleanup candidate"):
                main(["clean", "profiles", "--tmp", "--yes"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir},
                })

    def test_clean_profiles_old_logs_removes_only_old_log_files(self):
        temp_dir = self.make_temp_dir()
        log_dir = os.path.join(temp_dir, "profiles", "main", "log")
        os.makedirs(log_dir)
        old_log = os.path.join(log_dir, "old.log")
        new_log = os.path.join(log_dir, "new.log")
        for path in (old_log, new_log):
            with open(path, "wb") as handle:
                handle.write(b"x" * 1024)
        os.utime(old_log, (1000, 1000))
        os.utime(new_log, (1000 + 29 * 86400, 1000 + 29 * 86400))

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--old-logs", "30d", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["profiles"][0]["removed_count"], 1)
        self.assertFalse(os.path.exists(old_log))
        self.assertTrue(os.path.exists(new_log))

    def test_clean_profiles_bare_prints_usage(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx clean profiles"):
            main(["clean", "profiles"], {
                **self.make_io(),
                "env": {"CDX_HOME": self.make_temp_dir()},
            })

    def test_clean_old_logs_equals_routes_to_profiles_cleanup(self):
        temp_dir = self.make_temp_dir()
        old_log = os.path.join(temp_dir, "profiles", "main", "log", "old.log")
        os.makedirs(os.path.dirname(old_log))
        with open(old_log, "wb") as handle:
            handle.write(b"x")
        os.utime(old_log, (1000, 1000))

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "--old-logs=30", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "now": lambda: 1000 + 31 * 86400,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "clean.profiles")
        self.assertFalse(os.path.exists(old_log))

    def test_clean_profiles_old_logs_reports_removal_failure(self):
        temp_dir = self.make_temp_dir()
        old_log = os.path.join(temp_dir, "profiles", "main", "log", "old.log")
        os.makedirs(os.path.dirname(old_log))
        with open(old_log, "wb") as handle:
            handle.write(b"x")
        os.utime(old_log, (1000, 1000))

        real_remove = os.remove

        def remove(path):
            if path == old_log:
                raise OSError("permission denied")
            return real_remove(path)

        with mock.patch("src.commands.maintenance.os.remove", side_effect=remove):
            with self.assertRaisesRegex(CdxError, "Failed to remove old log"):
                main(["clean", "profiles", "--old-logs", "30d", "--yes"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir},
                    "now": lambda: 1000 + 31 * 86400,
                })

    def test_clean_profiles_without_cleanup_flags_is_profiles_usage(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("profiles")
        log_path = os.path.join(temp_dir, "profiles", "profiles", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("session transcript")

        with self.assertRaisesRegex(CdxError, "Usage: cdx clean profiles"):
            main(["clean", "profiles", "--yes", "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "service": service,
            })
        self.assertGreater(os.path.getsize(log_path), 0)

    def test_clean_profiles_requires_confirmation_before_deleting(self):
        temp_dir = self.make_temp_dir()
        marketplace_dir = os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        cache_path = os.path.join(marketplace_dir, "cache.bin")
        with open(cache_path, "wb") as handle:
            handle.write(b"x")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "profiles", "--tmp", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
            "confirmProfileCleanup": lambda _action: False,
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        self.assertTrue(payload["cancelled"])
        self.assertTrue(os.path.exists(cache_path))

    def test_clean_profiles_requires_yes_in_non_interactive_mode(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(os.path.join(temp_dir, "profiles", "main", ".tmp", "marketplaces"))

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal or --yes"):
            main(["clean", "profiles", "--tmp"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "stdin": {"isTTY": False},
            })

    def test_update_check_json_reports_available_update(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")

        list_io = self.make_io()
        self.assertEqual(main(["update", "--check", "--json"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "update")
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["target_version"], "9.9.9")
        self.assertEqual(payload["warnings"][0]["code"], "update_available")

    def test_update_runs_the_injected_installer(self):
        temp_dir = self.make_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")

        commands = []

        def run_update(command, cwd=None, env=None, check=False):
            commands.append({
                "command": command,
                "cwd": cwd,
                "env": env,
                "check": check,
            })
            return {"returncode": 0, "stdout": "", "stderr": ""}

        def run_version_check(command, **kwargs):
            return {"returncode": 0, "stdout": "9.9.9\n", "stderr": ""}

        list_io = self.make_io()
        self.assertEqual(main(["update", "--yes"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
            "runUpdate": run_update,
            "runVersionCheck": run_version_check,
        }), 0)

        self.assertEqual(commands[0]["command"], ["npm", "install", "-g", "cdx-manager@9.9.9"])
        self.assertIn("Updated cdx-manager to 9.9.9", list_io["stdout"].getvalue())

    def test_update_warns_when_path_resolves_old_version(self):
        temp_dir = self.make_temp_dir()
        bin_dir = os.path.join(temp_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        cdx_path = os.path.join(bin_dir, "cdx.cmd" if os.name == "nt" else "cdx")
        with open(os.path.join(temp_dir, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        with open(cdx_path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
        os.chmod(cdx_path, 0o755)

        def run_update(command, cwd=None, env=None, check=False):
            return {"returncode": 0, "stdout": "", "stderr": ""}

        def run_version_check(command, **kwargs):
            self.assertEqual(os.path.normcase(command[0]), os.path.normcase(cdx_path))
            self.assertEqual(command[1:], ["-v"])
            return {"returncode": 0, "stdout": "8.8.8\n", "stderr": ""}

        update_io = self.make_io()
        self.assertEqual(main(["update", "--yes", "--json"], {
            **update_io,
            "env": {"CDX_HOME": temp_dir, "PATH": bin_dir},
            "packageRoot": temp_dir,
            "fetchLatestRelease": lambda: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
            "runUpdate": run_update,
            "runVersionCheck": run_version_check,
        }), 0)

        payload = json.loads(update_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["warnings"][0]["code"], "update_version_mismatch")
        self.assertEqual(os.path.normcase(payload["warnings"][0]["path"]), os.path.normcase(cdx_path))
        self.assertEqual(payload["warnings"][0]["resolved_version"], "8.8.8")

    def test_disk_cleanup_notice_checks_daily(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        profile_dir = os.path.join(temp_dir, "profiles", "main")
        marketplace_dir = os.path.join(profile_dir, ".tmp", "marketplaces")
        os.makedirs(marketplace_dir)
        sizes = {
            temp_dir: str(11 * 1024 * 1024),
            profile_dir: str(3 * 1024 * 1024),
            marketplace_dir: str(2 * 1024 * 1024),
        }

        def runner(argv, **kwargs):
            return f"{sizes.get(argv[2], '1')}\t{argv[2]}\n"

        options = {
            "diskUsageRunner": runner,
            "now": lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        first = _get_disk_cleanup_notice(service, options)
        second = _get_disk_cleanup_notice(service, options)

        self.assertIsNotNone(first)
        self.assertEqual(first["code"], "disk_cleanup_available")
        self.assertIn("cdx clean profiles --tmp", first["message"])
        self.assertIsNone(second)

    def test_clean_reports_sessions_with_and_without_logs(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("withlog")
        service["create_session"]("nolog")
        log_path = os.path.join(temp_dir, "profiles", "withlog", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("status transcript")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "--yes", "--json"], {
            **clean_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(clean_io["stdout"].getvalue())
        by_name = {item["session_name"]: item for item in payload["sessions"]}
        self.assertTrue(by_name["withlog"]["cleared"])
        self.assertEqual(by_name["withlog"]["files_cleared"], 1)
        self.assertFalse(by_name["nolog"]["cleared"])
        self.assertEqual(os.path.getsize(log_path), 0)

    def test_clean_logs_requires_confirmation_before_truncating(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        log_path = os.path.join(temp_dir, "profiles", "main", "log", "cdx-session.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("transcript")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "main", "--json"], {
            **clean_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "confirmClean": lambda _target: False,
        }), 0)

        self.assertTrue(json.loads(clean_io["stdout"].getvalue())["cancelled"])
        self.assertGreater(os.path.getsize(log_path), 0)

    def test_update_parser_supports_schema_flags(self):
        temp_dir = self.make_temp_dir()
        update_io = self.make_io()

        self.assertEqual(main(["update", "--check", "--json"], {
            **update_io,
            "env": {"CDX_HOME": temp_dir},
            "version": "1.0.0",
            "fetchLatestRelease": lambda: {"latest_version": "1.0.0", "url": "https://example.test"},
        }), 0)
        payload = json.loads(update_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "update")
        self.assertTrue(payload["checked"])

        with self.assertRaisesRegex(CdxError, "cannot be combined"):
            main(["update", "--check", "--version=1.2.3"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_repair_parser_rejects_unknown_flags(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        with self.assertRaisesRegex(CdxError, "Usage: cdx repair"):
            main(["repair", "--bad"], {
                **self.make_io(),
                "service": service,
                "env": {"CDX_HOME": temp_dir},
            })

    def test_doctor_reports_missing_state_and_json_summary(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        os.remove(os.path.join(temp_dir, "state", "main.json"))

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(doctor_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["report"]["summary"]["fail"], 1)
        self.assertTrue(any(issue["code"] == "missing_state" for issue in payload["report"]["issues"]))

    def test_doctor_filters_severity_in_json_and_text(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        os.remove(os.path.join(temp_dir, "state", "main.json"))

        json_io = self.make_io()
        self.assertEqual(main(["doctor", "--severity=warn,fail", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        report = payload["report"]
        self.assertEqual(report["severity"], "WARN,FAIL")
        self.assertTrue(report["issues"])
        self.assertTrue(all(issue["status"] in {"WARN", "FAIL"} for issue in report["issues"]))
        self.assertEqual(report["summary"]["ok"], 0)
        self.assertEqual(report["summary"]["fail"], 1)

        text_io = self.make_io()
        self.assertEqual(main(["doctor", "--severity", "fail"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        text = text_io["stdout"].getvalue()
        self.assertIn("missing_state", text)
        self.assertNotIn("\nWARN", text)
        self.assertIn("Summary: 0 OK, 0 WARN, 1 FAIL", text)

    def test_doctor_rejects_invalid_or_repeated_severity(self):
        for args in (
            ["doctor", "--severity"],
            ["doctor", "--severity=info"],
            ["doctor", "--severity", "warn", "--severity", "fail"],
        ):
            with self.subTest(args=args):
                with self.assertRaisesRegex(CdxError, "Usage: cdx doctor"):
                    main(args, self.make_io())

    def test_doctor_severity_allows_empty_matches(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        io_obj = self.make_io()

        self.assertEqual(main(["doctor", "--severity", "FAIL", "--json"], {
            **io_obj,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "PATH": ""},
        }), 0)
        report = json.loads(io_obj["stdout"].getvalue())["report"]
        self.assertEqual(report["severity"], "FAIL")
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["summary"], {"ok": 0, "warn": 0, "fail": 0, "repairable": 0})

    def test_doctor_reports_codex_auth_diagnostic_without_tokens(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        session = service["create_session"]("main")
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"access_token": "secret-token"}}, handle)
        harness = _AuthHarness(initial_auth={session["authHome"]: True})

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        auth_file = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_auth_file")
        live_auth = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_live_auth")
        self.assertTrue(auth_file["detail"]["auth_json_exists"])
        self.assertTrue(auth_file["detail"]["local_tokens_present"])
        self.assertEqual(live_auth["detail"]["live_status"], "authenticated")
        self.assertNotIn("secret-token", json.dumps(payload))

    def test_doctor_treats_shared_codex_business_account_id_as_ambiguous(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        first = service["create_session"]("worka")
        second = service["create_session"]("workb")
        for session, email in ((first, "paul@example.com"), (second, "romaric@example.com")):
            with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
                json.dump({"tokens": {"refresh_token": "secret-token", "account_id": "acct-business-123456789"}}, handle)
            log_dir = os.path.join(session["authHome"], "log")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "cdx-session.log"), "w", encoding="utf-8") as handle:
                handle.write(f"Account: {email} (Business)\n")
        harness = _AuthHarness()

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": harness.spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        issue = next(item for item in payload["report"]["issues"] if item["code"] == "codex_shared_account_id")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"]["account_id"], "acct-b...6789")
        self.assertEqual(issue["detail"]["observed_identities"], ["paul@example.com", "romaric@example.com"])
        self.assertIn("not a user identity", issue["message"])
        self.assertNotIn("secret-token", json.dumps(payload))

    def test_doctor_reports_recent_codex_stale_auth_logs(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        session = service["create_session"]("main")
        with open(os.path.join(session["authHome"], "auth.json"), "w", encoding="utf-8") as handle:
            json.dump({"tokens": {"refresh_token": "secret-token"}}, handle)
        log_dir = os.path.join(session["authHome"], "log")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "cdx-session.log"), "w", encoding="utf-8") as handle:
            handle.write("HTTP 401 token_expired: authentication token is expired\n")

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": _AuthHarness().spawn_sync,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        issue = next(item for item in payload["report"]["issues"] if item["code"] == "codex_stale_auth_logs")
        self.assertEqual(issue["status"], "WARN")
        self.assertEqual(issue["detail"]["markers"], ["token_expired", "authentication token is expired", "http 401"])
        self.assertIn("cdx login main", issue["message"])
        self.assertNotIn("secret-token", json.dumps(payload))

    def test_doctor_reports_codex_auth_probe_timeout_as_degraded(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        def timeout_probe(_command, _args, _spec):
            raise subprocess.TimeoutExpired("codex", 15)

        doctor_io = self.make_io()
        self.assertEqual(main(["doctor", "--json"], {
            **doctor_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "spawn_sync": timeout_probe,
        }), 0)

        payload = json.loads(doctor_io["stdout"].getvalue())
        live_auth = next(issue for issue in payload["report"]["issues"] if issue["code"] == "codex_live_auth")
        self.assertEqual(live_auth["detail"]["live_status"], "degraded")
        self.assertIn("Auth probe timed out", live_auth["detail"]["live_error"])

    def test_doctor_windows_script_warning_mentions_expected_fallback(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch("src.health.sys.platform", "win32"):
            report = collect_health_report(service, temp_dir, env={"PATH": ""})

        issue = next(item for item in report["issues"] if item["code"] == "script_cli")
        self.assertIn("expected on many Windows setups", issue["message"])

    def test_doctor_reports_rtk_availability(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch("src.health.shutil.which", side_effect=lambda command, path=None: "/usr/bin/rtk" if command == "rtk" else None):
            report = collect_health_report(service, temp_dir, env={"PATH": "/usr/bin"})

        issue = next(item for item in report["issues"] if item["code"] == "rtk_cli")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"], "/usr/bin/rtk")

    def test_doctor_reports_logics_manager_availability(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }

        with mock.patch(
            "src.health.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            report = collect_health_report(service, temp_dir, env={"PATH": "/usr/bin"})

        issue = next(item for item in report["issues"] if item["code"] == "logics_manager_cli")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"], "/usr/bin/logics-manager")

    def test_doctor_reports_provider_cli_versions_and_capability_hints(self):
        temp_dir = self.make_temp_dir()
        service = {
            "list_sessions": lambda: [],
            "get_session_root": lambda _name: temp_dir,
        }
        harness = _AuthHarness()

        with mock.patch(
            "src.health.shutil.which",
            side_effect=lambda command, path=None: f"/usr/bin/{command}" if command in {"codex", "claude"} else None,
        ):
            report = collect_health_report(
                service,
                temp_dir,
                env={"PATH": "/usr/bin"},
                spawn_sync=harness.spawn_sync,
            )

        codex = next(item for item in report["issues"] if item["code"] == "codex_cli_version")
        claude = next(item for item in report["issues"] if item["code"] == "claude_cli_version")
        self.assertEqual(codex["detail"]["version"], "0.145.0")
        self.assertIn("provider_memory_import_surfaces_may_exist_in_recent_codex", codex["detail"]["capabilities"])
        self.assertEqual(claude["detail"]["version"], "2.1.219")
        self.assertIn("project_memory_and_stream_json_diagnostics_may_exist_in_recent_claude_code", claude["detail"]["capabilities"])

    def test_repair_dry_run_and_force_recreate_missing_state(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        state_path = os.path.join(temp_dir, "state", "main.json")
        os.remove(state_path)

        dry_io = self.make_io()
        self.assertEqual(main(["repair", "--dry-run"], {
            **dry_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertFalse(os.path.exists(state_path))
        self.assertIn("PLANNED", dry_io["stdout"].getvalue())

        force_io = self.make_io()
        self.assertEqual(main(["repair", "--force"], {
            **force_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertTrue(os.path.exists(state_path))
        self.assertIn("APPLIED", force_io["stdout"].getvalue())

    def test_repair_force_quarantines_orphan_profile(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        orphan = os.path.join(temp_dir, "profiles", "old")
        os.makedirs(orphan, exist_ok=True)

        repair_io = self.make_io()
        self.assertEqual(main(["repair", "--force"], {
            **repair_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        self.assertFalse(os.path.exists(orphan))
        self.assertTrue(os.path.isdir(os.path.join(temp_dir, "profiles", ".old.remove.orphan")))

