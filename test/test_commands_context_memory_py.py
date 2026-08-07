"""Tests for context, memory.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os

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


class ContextMemoryCommandTests(CliTestBase):

    def test_context_commands_store_context_per_workspace(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        os.makedirs(workspace)

        set_io = self.make_io()
        self.assertEqual(main(["context", "set", "Goal: ship handoff", "--json"], {
            **set_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        set_payload = json.loads(set_io["stdout"].getvalue())
        self.assertEqual(set_payload["action"], "context.set")
        self.assertTrue(set_payload["context"]["path"].endswith("context.md"))

        show_io = self.make_io()
        self.assertEqual(main(["context", "show"], {
            **show_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        self.assertIn("Goal: ship handoff", show_io["stdout"].getvalue())

        other_io = self.make_io()
        other_workspace = os.path.join(temp_dir, "other")
        os.makedirs(other_workspace)
        self.assertEqual(main(["context", "show"], {
            **other_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other_workspace,
        }), 0)
        self.assertIn("No shared context", other_io["stdout"].getvalue())

    def test_memory_commands_support_current_global_project_and_list(self):
        temp_dir = self.make_temp_dir()
        workspace = os.path.join(temp_dir, "repo")
        other = os.path.join(temp_dir, "other")
        os.makedirs(workspace)
        os.makedirs(other)

        current_io = self.make_io()
        self.assertEqual(main(["memory", "append", "Current note", "--json"], {
            **current_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        current_payload = json.loads(current_io["stdout"].getvalue())
        self.assertEqual(current_payload["action"], "memory.append")
        self.assertEqual(current_payload["memory"]["scope"], "current")

        global_io = self.make_io()
        self.assertEqual(main(["memory", "--global", "append", "Global note", "--json"], {
            **global_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        self.assertEqual(json.loads(global_io["stdout"].getvalue())["memory"]["scope"], "global")

        project_io = self.make_io()
        self.assertEqual(main(["memory", "--project", "client A", "append", "Project note", "--json"], {
            **project_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        project_payload = json.loads(project_io["stdout"].getvalue())
        self.assertEqual(project_payload["memory"]["project"], "client A")
        self.assertEqual(project_payload["memory"]["project_kind"], "name")

        path_io = self.make_io()
        self.assertEqual(main(["memory", "--project", workspace, "path", "--json"], {
            **path_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": other,
        }), 0)
        path_payload = json.loads(path_io["stdout"].getvalue())
        self.assertEqual(path_payload["memory"]["project_kind"], "path")
        self.assertEqual(path_payload["memory"]["path"], current_payload["memory"]["path"])

        list_io = self.make_io()
        self.assertEqual(main(["memory", "list", "--json"], {
            **list_io,
            "env": {"CDX_HOME": temp_dir},
            "cwd": workspace,
        }), 0)
        list_payload = json.loads(list_io["stdout"].getvalue())
        scopes = [entry["scope"] for entry in list_payload["memories"]]
        self.assertEqual(scopes, ["global", "project", "current"])
        self.assertEqual(list_payload["memories"][1]["project"], "client A")

    def test_memory_rejects_empty_append_and_conflicting_scope_flags(self):
        temp_dir = self.make_temp_dir()
        with self.assertRaisesRegex(CdxError, "Memory append requires text"):
            main(["memory", "append", "  "], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })
        with self.assertRaisesRegex(CdxError, "Usage: cdx memory"):
            main(["memory", "--global", "--project", "A", "path"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
            })

