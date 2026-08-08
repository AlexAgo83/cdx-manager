"""Tests for the bare `cdx` screen and its notices.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json

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
    main,
)
from src.session_service import create_session_service


class MainScreenTests(CliTestBase):

    def test_main_screen_formats_updated_as_relative_age(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("just now", output)
        self.assertNotRegex(output, r"\d{4}-\d{2}-\d{2}T")

    def test_main_screen_next_actions_are_curated(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        lines = list_io["stdout"].getvalue().splitlines()
        start = lines.index("Next actions:") + 1
        self.assertEqual(lines[start:start + 10], [
            "  cdx status",
            "  cdx next",
            "  cdx configs",
            "  cdx stats",
            "  cdx ready",
            "  cdx perm all default",
            "  cdx handoff <source> <target>",
            "  cdx history",
            "  cdx help",
            "  cdx update",
        ])
        self.assertNotIn("  cdx add <name>", lines[start:])
        self.assertNotIn("  cdx login <name>", lines[start:])
        self.assertNotIn("  cdx handoff <name>", lines[start:])

    def test_main_screen_without_sessions_points_at_the_first_add(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("No sessions yet.", output)
        self.assertIn("cdx add codex work", output)
        self.assertNotIn("Known sessions:", output)
        self.assertNotIn("Next actions:", output)

    def test_main_screen_surfaces_update_notice(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        output = list_io["stdout"].getvalue()
        self.assertIn("Update available: cdx-manager 9.9.9", output)
        self.assertIn("Run: cdx update", output)
        self.assertNotIn("https://example.invalid/release", output)

    def test_main_screen_json_includes_update_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "update_available")
        self.assertEqual(payload["warnings"][0]["latest_version"], "9.9.9")

    def test_main_screen_surfaces_disk_cleanup_notice(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main([], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkDiskCleanup": lambda _service, _options: {
                "tool": "cdx-disk",
                "code": "disk_cleanup_available",
                "message": "Disk cleanup available: 2 GB reclaimable. Inspect: cdx disk profiles --candidates",
                "reclaimable_bytes": 2 * 1024 * 1024 * 1024,
            },
        }), 0)

        self.assertIn("Disk cleanup available: 2 GB reclaimable", list_io["stdout"].getvalue())

    def test_main_screen_json_includes_disk_cleanup_warning(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
            "checkDiskCleanup": lambda _service, _options: {
                "tool": "cdx-disk",
                "code": "disk_cleanup_available",
                "message": "Disk cleanup available: 2 GB reclaimable. Inspect: cdx disk profiles --candidates",
                "reclaimable_bytes": 2 * 1024 * 1024 * 1024,
            },
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["warnings"][0]["code"], "disk_cleanup_available")
        self.assertEqual(payload["warnings"][0]["reclaimable_bytes"], 2 * 1024 * 1024 * 1024)

    def test_root_list_supports_json_contract(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        list_io = self.make_io()
        self.assertEqual(main(["--json"], {
            **list_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        payload = json.loads(list_io["stdout"].getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "list")
        self.assertEqual(payload["sessions"][0]["name"], "main")

