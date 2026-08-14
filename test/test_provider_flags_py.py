"""Tests for provider CLI flag mapping and launch fallbacks.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

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

from src import provider_runtime
from src.session_service import create_session_service


class ProviderFlagTests(CliTestBase):

    def test_provider_flag_check_confirms_a_complete_mapping(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(
            service,
            help_text="-s <sandbox> -a <approval> --dangerously-bypass-approvals-and-sandbox -c <cfg>",
            check_provider_flags=True,
        )

        self.assertEqual(self._flag_issue(report, "codex")["status"], "OK")

    def test_provider_flag_check_fails_on_a_flag_the_cli_lacks(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        # The issue #8 condition: a mapped flag the provider CLI never had.
        with mock.patch.dict(
            provider_runtime.LAUNCH_PERMISSION_ARGS[provider_runtime.PROVIDER_CODEX],
            {"full": ["--experimental-yolo"]},
        ):
            report = self._health_report(
                service,
                help_text="-s -a --dangerously-bypass-approvals-and-sandbox -c",
                check_provider_flags=True,
            )

        issue = self._flag_issue(report, "codex")
        self.assertEqual(issue["status"], "FAIL")
        self.assertEqual(issue["detail"]["missing"], {"full": ["--experimental-yolo"]})

    def test_provider_flag_check_is_indeterminate_without_the_cli(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service, cli_installed=False, check_provider_flags=True)

        # Not a failure, and emphatically not a pass: "could not check" is the
        # state issue #8 lived in for months.
        self.assertEqual(self._flag_issue(report, "codex")["status"], "WARN")

    def test_provider_flag_check_is_indeterminate_on_unreadable_help(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service, help_text="", check_provider_flags=True)

        self.assertEqual(self._flag_issue(report, "codex")["status"], "WARN")

    def test_provider_with_no_permission_mapping_still_verifies_cdx_own_flags(self):
        # ollama maps no *permission* to a flag, but cdx passes `--verbose` on
        # its own initiative to get token counts. Issue #8 was a mapped flag
        # the CLI never had; a flag cdx invents is exactly as capable of not
        # existing, so it is verified the same way.
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("local", "ollama")

        report = self._health_report(service, help_text="run --verbose", check_provider_flags=True)

        issue = self._flag_issue(report, "ollama")
        self.assertEqual(issue["status"], "OK")
        self.assertEqual(issue["detail"]["mapped"], {"cdx feature flags": ["--verbose"]})

    def test_a_cdx_feature_flag_the_cli_lacks_is_reported(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("local", "ollama")

        report = self._health_report(service, help_text="run", check_provider_flags=True)

        issue = self._flag_issue(report, "ollama")
        self.assertEqual(issue["status"], "FAIL")
        self.assertEqual(issue["detail"]["missing"], {"cdx feature flags": ["--verbose"]})

    def test_provider_flag_check_absence_is_reported_not_omitted(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("work", "codex")

        report = self._health_report(service)

        codes = [i["code"] for i in report["issues"]]
        self.assertNotIn("codex_permission_flags", codes)
        # A check that did not run must say so; silently omitting it would let
        # a green doctor imply the mappings were verified.
        unchecked = next(i for i in report["issues"] if i["code"] == "provider_permission_flags_unchecked")
        self.assertEqual(unchecked["status"], "WARN")

