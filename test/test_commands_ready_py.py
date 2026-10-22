"""Tests for ready.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
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
    main,
)
from src.errors import CdxError


class ReadyCommandTests(CliTestBase):

    def test_ready_schedules_next_ready_notification(self):
        temp_dir = self.make_temp_dir()
        reset = datetime.now().astimezone() + timedelta(minutes=30)
        service = {
            "base_dir": temp_dir,
            "get_status_rows": lambda **_kwargs: [{
                "session_name": "main",
                "provider": "codex",
                "enabled": True,
                "status": "enabled",
                "remaining_5h_pct": 0,
                "remaining_week_pct": 20,
                "reset_5h_at": reset.isoformat(),
                "updated_at": datetime.now().astimezone().isoformat(),
            }],
        }
        calls = []

        def spawn_sync(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch("sys.platform", "linux"):
            with mock.patch("src.notify.shutil.which", side_effect=lambda command, path=None: command == "systemd-run"):
                ready_io = self.make_io()
                self.assertEqual(main(["ready", "--json"], {
                    **ready_io,
                    "service": service,
                    "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin", "CDX_BIN": "/usr/local/bin/cdx"},
                    "spawn_sync": spawn_sync,
                }), 0)

        payload = json.loads(ready_io["stdout"].getvalue())
        self.assertEqual(payload["action"], "notify")
        self.assertTrue(payload["schedule"]["scheduled"])
        self.assertEqual(payload["event"]["session"], "main")
        self.assertEqual(calls[0][0][0], "systemd-run")

    def test_ready_without_upcoming_reset_returns_unscheduled_result(self):
        temp_dir = self.make_temp_dir()
        service = {
            "base_dir": temp_dir,
            "get_status_rows": lambda **_kwargs: [],
        }

        json_io = self.make_io()
        self.assertEqual(main(["ready", "--json"], {
            **json_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(json_io["stdout"].getvalue())
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["schedule"]["scheduled"])
        self.assertEqual(payload["schedule"]["backend"], "none")
        self.assertEqual(payload["event"]["message"], "No upcoming session reset available")

        text_io = self.make_io()
        self.assertEqual(main(["ready"], {
            **text_io,
            "service": service,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        self.assertIn("No upcoming session reset available", text_io["stdout"].getvalue())

    def test_ready_rejects_notify_only_options(self):
        with self.assertRaisesRegex(CdxError, "Usage: cdx ready"):
            main(["ready", "--once"], self.make_io())


    def test_scheduled_job_argv_shows_the_notification(self):
        """The argv a scheduler stores must, when run, put a banner on screen."""
        from src.notify import _scheduled_notify_argv
        argv = _scheduled_notify_argv({"session": "main"}, {"CDX_BIN": "cdx"})
        calls = []
        with mock.patch("sys.platform", "linux"), \
                mock.patch("src.notify.shutil.which", side_effect=lambda command, path=None: command == "notify-send"):
            code = main(argv[1:], {
                **self.make_io(),
                "env": {"PATH": "/usr/bin", "DISPLAY": ":0"},
                "spawn_sync": lambda command, **kwargs: calls.append(command) or subprocess.CompletedProcess(command, 0, "", ""),
            })
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][:3], ["notify-send", "-a", "cdx"])
        self.assertIn("main", calls[0][-1])
