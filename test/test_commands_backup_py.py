"""Tests for export, import.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
import unittest

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
from src.errors import CdxError
from src.session_service import create_session_service


class BackupCommandTests(CliTestBase):

    def test_export_import_commands_support_json_contract(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        self.assertEqual(main(["add", "main", "--json"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        export_path = os.path.join(temp_dir, "backup.cdx")
        export_io = self.make_io()
        self.assertEqual(main(["export", export_path, "--json"], {
            **export_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertEqual(export_payload["action"], "export")
        self.assertEqual(export_payload["bundle"]["path"], export_path)
        self.assertEqual(export_payload["bundle"]["session_names"], ["main"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main(["import", export_path, "--json"], {
            **import_io,
            "env": {"CDX_HOME": import_dir},
        }), 0)
        import_payload = json.loads(import_io["stdout"].getvalue())
        self.assertEqual(import_payload["action"], "import")
        self.assertEqual(import_payload["bundle"]["session_names"], ["main"])

        imported_service = create_session_service({"base_dir": import_dir})
        self.assertEqual(imported_service["get_session"]("main")["name"], "main")

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_with_auth_uses_passphrase_env_and_import_restores_profile(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "claude", "claude1", "--json"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        auth_path = os.path.join(temp_dir, "profiles", "claude1", "claude-home", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')

        export_path = os.path.join(temp_dir, "secure.cdx")
        export_io = self.make_io()
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json",
        ], {
            **export_io,
            "env": {"CDX_HOME": temp_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertTrue(export_payload["bundle"]["include_auth"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main([
            "import", export_path, "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json",
        ], {
            **import_io,
            "env": {"CDX_HOME": import_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)
        imported_auth = os.path.join(import_dir, "profiles", "claude1", "claude-home", "auth.json")
        with open(imported_auth, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_and_import_accept_passphrase_from_stdin(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "claude", "claude1", "--json"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        auth_path = os.path.join(temp_dir, "profiles", "claude1", "claude-home", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')

        export_path = os.path.join(temp_dir, "secure.cdx")
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-stdin", "--json",
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "read_stdin": lambda: "pw123\n",
        }), 0)

        import_dir = self.make_temp_dir()
        self.assertEqual(main([
            "import", export_path, "--passphrase-stdin", "--json",
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": import_dir},
            "read_stdin": lambda: "pw123\n",
        }), 0)
        imported_auth = os.path.join(import_dir, "profiles", "claude1", "claude-home", "auth.json")
        with open(imported_auth, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), '{"token":"secret"}')

    def test_export_rejects_conflicting_passphrase_sources(self):
        with self.assertRaisesRegex(CdxError, "mutually exclusive"):
            main([
                "export", "x.cdx", "--include-auth",
                "--passphrase-env", "VAR", "--passphrase-stdin", "--json",
            ], {**self.make_io(), "env": {}})

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_export_with_auth_reports_progress_and_summary(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        auth_path = os.path.join(temp_dir, "profiles", "main", "auth.json")
        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        with open(auth_path, "w", encoding="utf-8") as handle:
            handle.write('{"token":"secret"}')

        export_path = os.path.join(temp_dir, "secure.cdx")
        export_io = self.make_io()
        self.assertEqual(main([
            "export", export_path, "--include-auth", "--passphrase-env", "CDX_BUNDLE_PASSPHRASE",
        ], {
            **export_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir, "CDX_BUNDLE_PASSPHRASE": "pw123"},
        }), 0)

        output = export_io["stdout"].getvalue()
        self.assertIn("Exporting 1 session(s) with auth...", output)
        self.assertIn("Collecting main...", output)
        self.assertIn("Encoding and encrypting bundle...", output)
        self.assertIn("Writing ", output)
        self.assertIn("Exported 1 session with auth to", output)
        self.assertIn(f"Path: {export_path}", output)
        self.assertIn("Auth: included and encrypted", output)
        self.assertRegex(output, r"Auth files: [1-9]\d*")
        self.assertIn("Auth data: ", output)
        self.assertIn("Bundle size: ", output)

    def test_export_import_parsers_support_equals_flags_and_session_subset(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["create_session"]("side")
        export_path = os.path.join(temp_dir, "subset.cdx")

        export_io = self.make_io()
        self.assertEqual(main([
            "export",
            export_path,
            "--sessions=side",
            "--json",
        ], {
            **export_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        export_payload = json.loads(export_io["stdout"].getvalue())
        self.assertEqual(export_payload["bundle"]["session_names"], ["side"])

        import_dir = self.make_temp_dir()
        import_io = self.make_io()
        self.assertEqual(main([
            "import",
            export_path,
            "--sessions=side",
            "--json",
        ], {
            **import_io,
            "env": {"CDX_HOME": import_dir},
        }), 0)

        imported_service = create_session_service({"base_dir": import_dir})
        self.assertIsNone(imported_service["get_session"]("main"))
        self.assertEqual(imported_service["get_session"]("side")["name"], "side")

    def test_export_with_auth_rejects_non_interactive_without_passphrase_env(self):
        temp_dir = self.make_temp_dir()
        create_session_service({"base_dir": temp_dir})["create_session"]("main")
        io_obj = self.make_io()
        io_obj["stdin"] = {"isTTY": False}

        with self.assertRaisesRegex(CdxError, "requires an interactive terminal"):
            main(["export", os.path.join(temp_dir, "backup.cdx"), "--include-auth"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir},
            })

    @unittest.skipUnless(HAS_CRYPTOGRAPHY, CRYPTOGRAPHY_REQUIRED)
    def test_import_rejects_wrong_passphrase(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        bundle_path = os.path.join(temp_dir, "secure.cdx")
        service["export_bundle"](bundle_path, include_auth=True, passphrase="pw123")

        import_dir = self.make_temp_dir()
        with self.assertRaisesRegex(CdxError, "Invalid bundle passphrase or corrupted bundle"):
            main(["import", bundle_path, "--passphrase-env", "CDX_BUNDLE_PASSPHRASE", "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": import_dir, "CDX_BUNDLE_PASSPHRASE": "wrong"},
            })

    def test_import_rejects_corrupted_bundle(self):
        temp_dir = self.make_temp_dir()
        bundle_path = os.path.join(temp_dir, "corrupt.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(b"not a cdx bundle")

        with self.assertRaisesRegex(CdxError, "Invalid bundle"):
            main(["import", bundle_path, "--json"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

    def test_import_rejects_force_and_merge_together(self):
        temp_dir = self.make_temp_dir()
        bundle_path = os.path.join(temp_dir, "backup.cdx")
        with open(bundle_path, "wb") as handle:
            handle.write(b"placeholder")

        with self.assertRaisesRegex(CdxError, "mutually exclusive"):
            main(["import", bundle_path, "--force", "--merge"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

