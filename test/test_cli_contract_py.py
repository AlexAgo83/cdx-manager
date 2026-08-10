"""Tests for argument parsing, JSON envelopes, help, version and facade contracts.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
import os
import subprocess
import sys

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
    format_json_error,
    main,
)
from src.cli_args import (
    RUN_EFFORT_VALUES,
    RUN_PERMISSION_ALIASES,
    RUN_PERMISSION_CANONICAL_VALUES,
    _parse_run_args,
)
from src.errors import CdxError
from src.session_service import create_session_service


class CliContractTests(CliTestBase):

    def test_help_and_version_flags(self):
        help_io = self.make_io()
        version_io = self.make_io()

        self.assertEqual(main(["--help"], help_io), 0)
        self.assertIn("Usage:", help_io["stdout"].getvalue())
        self.assertIn("cdx update [all] [--check] [--yes] [--json] [--version TAG]", help_io["stdout"].getvalue())
        self.assertIn("cdx ready [--refresh] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx doctor [--severity OK|WARN|FAIL[,OK|WARN|FAIL...]] [--check-provider-flags] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx next [--json] [--refresh]", help_io["stdout"].getvalue())
        self.assertIn("cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b>", help_io["stdout"].getvalue())
        self.assertIn("cdx stats [name]", help_io["stdout"].getvalue())
        self.assertIn("cdx disk [profiles] [--candidates] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx clean profiles (--tmp|--old-logs DAYS) [--yes] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx reset <name> [--yes] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx resume <name> [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx can-resume <name> [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx add [provider] <name> [--model MODEL] [--json]", help_io["stdout"].getvalue())
        self.assertIn("cdx set <name>|--sessions all|a,b|--provider PROVIDER", help_io["stdout"].getvalue())
        self.assertIn("--model MODEL", help_io["stdout"].getvalue())
        self.assertIn("--priority 0..100", help_io["stdout"].getvalue())
        self.assertIn("--rtk on|off", help_io["stdout"].getvalue())
        self.assertIn("--min-power minimal|low|medium|high|xhigh", help_io["stdout"].getvalue())
        self.assertIn("--power minimal|low|medium|high|xhigh", help_io["stdout"].getvalue())
        self.assertIn("workspace-write|read-only|danger-full-access", help_io["stdout"].getvalue())
        self.assertIn("--kind assistant|code-review", help_io["stdout"].getvalue())
        self.assertIn("Notifications:", help_io["stdout"].getvalue())
        self.assertIn("cdx set <name> --notify on", help_io["stdout"].getvalue())
        self.assertNotIn("  cdx notify\n", help_io["stdout"].getvalue())

        self.assertEqual(main(["-v"], version_io), 0)
        self.assertRegex(version_io["stdout"].getvalue().strip(), r"^\d+\.\d+\.\d+$")

    def test_subcommand_dash_h_is_not_hijacked_by_top_level_help(self):
        io_obj = self.make_io()
        with self.assertRaises(CdxError) as caught:
            main(["history", "-h"], {**io_obj, "service": create_session_service({"base_dir": self.make_temp_dir()})})
        self.assertNotIn("Usage: cdx --help", str(caught.exception))

    def test_mutation_commands_support_json_contract(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()

        add_io = self.make_io()
        self.assertEqual(main(["add", "main", "--json"], {
            **add_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        add_payload = json.loads(add_io["stdout"].getvalue())
        self.assertTrue(add_payload["ok"])
        self.assertEqual(add_payload["action"], "add")
        self.assertEqual(add_payload["session"]["name"], "main")

        copy_io = self.make_io()
        self.assertEqual(main(["cp", "main", "copy", "--json"], {
            **copy_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        copy_payload = json.loads(copy_io["stdout"].getvalue())
        self.assertEqual(copy_payload["action"], "copy")
        self.assertEqual(copy_payload["session"]["name"], "copy")
        self.assertFalse(copy_payload["overwritten"])

        rename_io = self.make_io()
        self.assertEqual(main(["ren", "copy", "renamed", "--json"], {
            **rename_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        rename_payload = json.loads(rename_io["stdout"].getvalue())
        self.assertEqual(rename_payload["action"], "rename")
        self.assertEqual(rename_payload["session"]["name"], "renamed")

        clean_io = self.make_io()
        self.assertEqual(main(["clean", "main", "--yes", "--json"], {
            **clean_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        clean_payload = json.loads(clean_io["stdout"].getvalue())
        self.assertEqual(clean_payload["action"], "clean")
        self.assertEqual(clean_payload["sessions"][0]["session_name"], "main")

        logout_io = self.make_io()
        self.assertEqual(main(["logout", "main", "--json"], {
            **logout_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        logout_payload = json.loads(logout_io["stdout"].getvalue())
        self.assertEqual(logout_payload["action"], "logout")
        self.assertEqual(logout_payload["session"]["auth"]["status"], "logged_out")

        login_io = self.make_io()
        self.assertEqual(main(["login", "main", "--json"], {
            **login_io,
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        login_payload = json.loads(login_io["stdout"].getvalue())
        self.assertEqual(login_payload["action"], "login")
        self.assertEqual(login_payload["session"]["auth"]["status"], "authenticated")

        remove_io = self.make_io()
        self.assertEqual(main(["rmv", "renamed", "--force", "--json"], {
            **remove_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        remove_payload = json.loads(remove_io["stdout"].getvalue())
        self.assertEqual(remove_payload["action"], "remove")
        self.assertEqual(remove_payload["session"]["name"], "renamed")
        self.assertFalse(remove_payload["cancelled"])

    def test_invalid_status_syntax_raises_usage_error(self):
        with self.assertRaises(CdxError) as ctx:
            main(["status", "main", "extra"], self.make_io())
        self.assertIn("Usage: cdx status [--json]", str(ctx.exception))
        with self.assertRaises(CdxError) as small_ctx:
            main(["status", "main", "--small"], self.make_io())
        self.assertIn("cdx status --small|-s", str(small_ctx.exception))
        with self.assertRaises(CdxError) as json_ctx:
            main(["status", "--small", "--json"], self.make_io())
        self.assertIn("cdx status --small|-s", str(json_ctx.exception))
        with self.assertRaises(CdxError) as refresh_cached_ctx:
            main(["status", "--refresh", "--cached"], self.make_io())
        self.assertIn("cdx status [--json]", str(refresh_cached_ctx.exception))
        with self.assertRaises(CdxError) as timeout_ctx:
            main(["status", "--timeout", "0"], self.make_io())
        self.assertIn("--timeout SECONDS", str(timeout_ctx.exception))

    def test_non_interactive_login_and_remove_are_rejected(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        })

        with self.assertRaises(CdxError) as login_ctx:
            main(["login", "main"], {
                "stdin": {"isTTY": False},
                "stdout": _Stream(),
                "stderr": _Stream(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            })
        self.assertIn("Login requires an interactive terminal.", str(login_ctx.exception))

        with self.assertRaises(CdxError) as remove_ctx:
            main(["rmv", "main"], {
                "stdin": {"isTTY": False},
                "stdout": _Stream(),
                "stderr": _Stream(),
                "env": {"CDX_HOME": temp_dir},
            })
        self.assertIn("Removal requires confirmation", str(remove_ctx.exception))

    def test_json_error_payload_has_machine_readable_contract(self):
        error = CdxError("Unknown session: missing", exit_code=3)
        payload = json.loads(format_json_error(error))
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "unknown_session")
        self.assertEqual(payload["error"]["message"], "Unknown session: missing")
        self.assertEqual(payload["error"]["exit_code"], 3)

    def test_empty_power_blames_the_flag_that_was_passed(self):
        target = self.make_temp_dir()
        with self.assertRaises(CdxError) as caught:
            _parse_run_args(["main", "--cwd", target, "--prompt", "x", "--power", "", "--json"])

        self.assertEqual(caught.exception.arguments, ("--power",))

    def test_every_validator_shares_one_accepted_value_definition(self):
        # Not equality but identity: equality would still pass if someone
        # reintroduced a second literal that happened to match today. These
        # names must all resolve to the one definition config.py owns.
        from src import config, provider_runtime, session_service

        for shared in (
            RUN_EFFORT_VALUES,
            provider_runtime.REASONING_EFFORT_VALUES,
            session_service.LAUNCH_POWER_VALUES,
            session_service.LAUNCH_REASONING_EFFORT_VALUES,
        ):
            self.assertIs(shared, config.REASONING_EFFORT_VALUES)

        self.assertIs(RUN_PERMISSION_CANONICAL_VALUES, config.PERMISSION_VALUES)
        self.assertIs(session_service.LAUNCH_PERMISSION_VALUES, config.PERMISSION_VALUES)
        self.assertIs(RUN_PERMISSION_ALIASES, config.PERMISSION_ALIASES)

    def test_no_module_restates_an_accepted_value_set(self):
        # The guard that keeps the deduplication from silently regressing: a
        # fresh copy of one of these sets anywhere in src/ fails here, named.
        import pathlib
        import re

        duplicates = []
        for path in sorted(pathlib.Path("src").rglob("*.py")):
            if path.name == "config.py":
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                literal = re.match(r'^[A-Z_]{4,}\s*=\s*([\{\(].*[\}\)])\s*$', line.strip())
                if not literal:
                    continue
                values = set(re.findall(r'"([^"]+)"', literal.group(1)))
                if values in (set(RUN_EFFORT_VALUES), set(RUN_PERMISSION_CANONICAL_VALUES)):
                    duplicates.append(f"{path}:{number} {line.strip()}")
        self.assertEqual(duplicates, [], "accepted-value set restated instead of imported from config")

    def test_cli_commands_facade_still_exposes_every_name_its_callers_import(self):
        # cli_commands is a facade over src/commands/*: the handlers live
        # elsewhere but must stay importable from here. Nothing else catches a
        # dropped re-export until an unrelated module fails to import, so the
        # contract is asserted directly. This caught `_format_bytes`, which
        # cli.py imports through the facade and ruff removed as unused once the
        # last in-file caller moved out.
        import ast
        import importlib
        import pathlib

        facade = importlib.import_module("src.cli_commands")
        missing = []
        for path in [pathlib.Path("src/cli.py"), *sorted(pathlib.Path("test").glob("test_*.py"))]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if (node.module or "").rsplit(".", 1)[-1] != "cli_commands":
                    continue
                for alias in node.names:
                    if not hasattr(facade, alias.name):
                        missing.append(f"{path}:{node.lineno} {alias.name}")
        self.assertEqual(missing, [], "cli_commands no longer re-exports a name its callers import")

    def test_every_version_declaration_agrees(self):
        import pathlib
        import re

        from src.cli import VERSION

        root = pathlib.Path(".")
        declared = (root / "VERSION").read_text().strip()
        package_json = json.loads((root / "package.json").read_text())["version"]
        pyproject = re.search(
            r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M
        ).group(1)
        badge = re.search(r"badge/version-v([0-9][^-]*)-", (root / "README.md").read_text()).group(1)

        # cli.py used to restate the version as a fourth copy and drifted a
        # release behind, so `cdx --version` reported a release it was not.
        self.assertEqual(VERSION, declared)
        self.assertEqual(package_json, declared)
        self.assertEqual(pyproject, declared)
        self.assertEqual(badge, declared)

    def test_bin_cdx_runs_as_real_subprocess(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir}
        result = subprocess.run(
            [sys.executable, "bin/cdx", "--help"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_bin_cdx_delegates_to_cli_entry(self):
        with open("bin/cdx", encoding="utf-8") as handle:
            text = handle.read()

        self.assertIn("from src.cli import cli_entry", text)
        self.assertIn("cli_entry()", text)
        self.assertNotIn("format_json_error", text)
        self.assertNotIn("except CdxError", text)

    def test_bin_cdx_colors_errors_when_enabled(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir, "CLICOLOR_FORCE": "1"}
        env.pop("NO_COLOR", None)
        result = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("\033[31m", result.stderr)
        self.assertIn("Usage: cdx status [--json]", result.stderr)

        plain = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra"],
            cwd=os.getcwd(),
            env={**env, "NO_COLOR": "1"},
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(plain.returncode, 0)
        self.assertNotIn("\033[", plain.stderr)

    def test_bin_cdx_writes_json_errors_when_requested(self):
        temp_dir = self.make_temp_dir()
        env = {**os.environ, "CDX_HOME": temp_dir}
        result = subprocess.run(
            [sys.executable, "bin/cdx", "status", "main", "extra", "--json"],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema_version"], 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_usage")
        self.assertIn("Usage: cdx status [--json]", payload["error"]["message"])
