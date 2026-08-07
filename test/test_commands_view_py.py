"""Tests for view.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import subprocess
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
    main,
)
from src.errors import CdxError


class ViewCommandTests(CliTestBase):

    def test_view_delegates_to_logics_manager_from_current_cwd(self):
        temp_dir = self.make_temp_dir()
        cwd = self.make_temp_dir()
        calls = []

        def run_view(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "cwd": cwd,
                "spawn_sync": run_view,
                "checkLogicsManagerForUpdate": lambda *_args, **_kwargs: None,
            }), 0)

        self.assertEqual(calls[0][0], ["/usr/bin/logics-manager", "view"])
        self.assertEqual(calls[0][1]["cwd"], cwd)

    def test_view_ctrl_c_exits_cleanly_without_traceback(self):
        temp_dir = self.make_temp_dir()

        def interrupted(_argv, **_kwargs):
            raise KeyboardInterrupt()

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "cwd": temp_dir,
                "spawn_sync": interrupted,
                "checkLogicsManagerForUpdate": lambda *_args, **_kwargs: None,
            }), 130)

        self.assertEqual(io_obj["stdout"].getvalue(), "\n")
        self.assertEqual(io_obj["stderr"].getvalue(), "")

    def test_view_missing_logics_manager_is_actionable(self):
        temp_dir = self.make_temp_dir()

        with mock.patch("src.logics_view.shutil.which", return_value=None):
            with self.assertRaisesRegex(CdxError, "npm install -g @grifhinz/logics-manager"):
                main(["view"], {
                    **self.make_io(),
                    "env": {"CDX_HOME": temp_dir, "PATH": ""},
                })

    def test_view_json_reports_availability_without_opening_viewer(self):
        temp_dir = self.make_temp_dir()
        calls = []

        with mock.patch("src.logics_view.shutil.which", return_value=None):
            io_obj = self.make_io()
            self.assertEqual(main(["view", "--json"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": ""},
                "spawn_sync": lambda *args, **kwargs: calls.append((args, kwargs)),
            }), 1)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["action"], "view")
        self.assertFalse(payload["viewer"]["available"])
        self.assertEqual(payload["viewer"]["command"], ["logics-manager", "view"])
        self.assertEqual(payload["viewer"]["failure"]["code"], "logics_manager_missing")
        self.assertEqual(calls, [])

    def test_view_json_includes_logics_manager_update_suggestion(self):
        temp_dir = self.make_temp_dir()

        def update_notice(*_args, **_kwargs):
            return {
                "tool": "logics-manager",
                "latest_version": "9.9.9",
                "current_version": "1.0.0",
                "update_command": "logics-manager self-update",
                "url": "https://example.invalid/logics-manager",
            }

        with mock.patch("src.logics_view.shutil.which", return_value="/usr/bin/logics-manager"):
            io_obj = self.make_io()
            self.assertEqual(main(["view", "--json"], {
                **io_obj,
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "checkLogicsManagerForUpdate": update_notice,
            }), 0)

        payload = json.loads(io_obj["stdout"].getvalue())
        self.assertTrue(payload["viewer"]["available"])
        self.assertEqual(payload["viewer"]["update"]["latest_version"], "9.9.9")
        self.assertEqual(payload["warnings"][0]["update_command"], "logics-manager self-update")

