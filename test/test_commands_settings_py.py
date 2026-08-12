"""Tests for set, unset and the power/perm/fast/model aliases.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""

import json
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
from src.cli_args import (
    _parse_run_args,
)
from src.errors import CdxError
from src.session_service import create_session_service


class SettingsCommandTests(CliTestBase):

    def test_notify_preview_is_explicit_and_clearable(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        set_io = self.make_io()
        self.assertEqual(main(["set", "main", "--notify-preview", "on", "--json"], {**set_io, "service": service}), 0)
        self.assertTrue(json.loads(set_io["stdout"].getvalue())["launch"]["notify_preview"])
        unset_io = self.make_io()
        self.assertEqual(main(["unset", "main", "--notify-preview", "--json"], {**unset_io, "service": service}), 0)
        self.assertNotIn("notify_preview", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_notify_preview_notice_names_the_sessions(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("main")
        io_obj = self.make_io()
        self.assertEqual(main(["set", "main", "--notify-preview", "on"], {**io_obj, "service": service}), 0)
        self.assertIn("Response previews enabled for main", io_obj["stdout"].getvalue())

    def test_notify_setting_explains_the_next_launch(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("main")
        io_obj = self.make_io()
        self.assertEqual(main(["set", "main", "--notify", "on"], {**io_obj, "service": service}), 0)
        self.assertIn("hooks install on the next interactive launch", io_obj["stdout"].getvalue())

    def test_notify_setting_reports_unsupported_and_mixed_providers_truthfully(self):
        service = create_session_service({"base_dir": self.make_temp_dir()})
        service["create_session"]("claude", "claude")
        service["create_session"]("local", "ollama")
        io_obj = self.make_io()
        self.assertEqual(main(["set", "--sessions", "claude,local", "--notify", "on"], {
            **io_obj, "service": service,
        }), 0)
        output = io_obj["stdout"].getvalue()
        self.assertIn("Agent alerts enabled for claude — hooks install", output)
        self.assertIn("Agent alerts updated for local — this provider does not support notification hooks.", output)

    def test_unset_reasoning_effort_is_supported(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")
        service["set_launch_settings"]("main", {"reasoning_effort": "high"})

        unset_io = self.make_io()
        self.assertEqual(main(["unset", "main", "--reasoning-effort", "--json"], {
            **unset_io,
            "service": service,
        }), 0)

        self.assertNotIn("reasoning_effort", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_set_launch_settings_can_target_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"], ["add", "ollama", "local", "--model", "llama3.2"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "all", "--permission", "full", "--json"
        ], {
            **set_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(set_io["stdout"].getvalue())
        self.assertEqual(payload["updated_count"], 3)
        self.assertIsNone(payload["session"])
        self.assertEqual(
            {session["name"]: session["launch"]["permission"] for session in payload["sessions"]},
            {"main": "full", "work1": "full", "local": "full"},
        )

    def test_set_launch_settings_can_target_provider_or_named_subset(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "side"], ["add", "claude", "work1"], ["add", "ollama", "local", "--model", "llama3.2"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        provider_io = self.make_io()
        self.assertEqual(main([
            "set", "--provider", "codex", "--power", "low", "--json"
        ], {
            **provider_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        provider_payload = json.loads(provider_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in provider_payload["sessions"]], ["main", "side"])

        subset_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "work1,local", "--fast", "on", "--json"
        ], {
            **subset_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        subset_payload = json.loads(subset_io["stdout"].getvalue())
        self.assertEqual([session["name"] for session in subset_payload["sessions"]], ["work1", "local"])
        self.assertTrue(all(session["launch"]["fast"] for session in subset_payload["sessions"]))

    def test_set_launch_priority_affects_headless_selection_tie_breaker(self):
        target_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": target_dir})
        service["create_session"]("alpha", "codex")
        service["create_session"]("beta", "codex")
        for name in ("alpha", "beta"):
            service["update_auth_state"](name, lambda auth: {**auth, "status": "authenticated"})
            service["record_status"](name, {"remaining_5h_pct": 80, "remaining_week_pct": 80})

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "beta", "--priority", "50", "--json"
        ], {**set_io, "service": service}), 0)
        self.assertEqual(json.loads(set_io["stdout"].getvalue())["launch"]["priority"], 50)

        select_io = self.make_io()
        self.assertEqual(main([
            "select", "--provider", "codex", "--require-ready", "--json"
        ], {**select_io, "service": service}), 0)

        payload = json.loads(select_io["stdout"].getvalue())
        self.assertEqual(payload["session"], "beta")

    def test_set_persists_budget_and_fallback_model_and_unset_clears_them(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("solo", "claude")

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "solo", "--budget", "5", "--fallback-model", "sonnet,haiku", "--json"
        ], {**set_io, "service": service}), 0)
        launch = json.loads(set_io["stdout"].getvalue())["launch"]
        self.assertEqual(launch["budget"], 5)
        self.assertEqual(launch["fallback_model"], "sonnet,haiku")

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "solo", "--budget", "--fallback-model", "--json"
        ], {**unset_io, "service": service}), 0)
        cleared = json.loads(unset_io["stdout"].getvalue())["launch"]
        self.assertNotIn("budget", cleared)
        self.assertNotIn("fallback_model", cleared)

    def test_set_rejects_budgets_that_express_nothing(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("solo", "claude")

        for value in ("0", "-1", "abc", "20000", "nan"):
            with self.assertRaises(CdxError, msg=f"budget {value} should be rejected"):
                main(["set", "solo", "--budget", value], {**self.make_io(), "service": service})

        self.assertIsNone((service["get_session"]("solo").get("launch") or {}).get("budget"))

    def test_set_validates_every_element_of_the_fallback_model_list(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("solo", "claude")

        for value in ("sonnet,", ",haiku", "sonnet,,haiku", "sonnet,bad\x01name", "sonnet," + "x" * 200):
            with self.assertRaises(CdxError, msg=f"fallback list {value!r} should be rejected"):
                main(["set", "solo", "--fallback-model", value], {**self.make_io(), "service": service})

        self.assertIsNone((service["get_session"]("solo").get("launch") or {}).get("fallback_model"))

    def test_set_rejects_conflicting_target_selectors_and_flag_values(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("main")

        # --sessions and --provider are mutually exclusive target scopes.
        with self.assertRaises(CdxError):
            main(["set", "--sessions", "main", "--provider", "codex", "--model", "opus"],
                 {**self.make_io(), "service": service})
        with self.assertRaises(CdxError):
            main(["unset", "--sessions", "main", "--provider", "codex", "--model"],
                 {**self.make_io(), "service": service})

        # A known flag can't be swallowed as another flag's value.
        with self.assertRaises(CdxError):
            main(["set", "main", "--model", "--json"], {**self.make_io(), "service": service})
        launch = service["get_session"]("main").get("launch") or {}
        self.assertIsNone(launch.get("model"))

    def test_set_launch_rtk_preference_can_be_unset(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "main", "--rtk", "on", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertTrue(json.loads(set_io["stdout"].getvalue())["launch"]["rtk"])

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "main", "--rtk", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertNotIn("rtk", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_set_launch_logics_preference_can_be_unset(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "main", "--logics", "off", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertFalse(json.loads(set_io["stdout"].getvalue())["launch"]["logics"])

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "main", "--logics", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertNotIn("logics", json.loads(unset_io["stdout"].getvalue())["launch"])

    def test_logics_prompt_defaults_on_when_cli_is_detected_and_can_be_disabled(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        self.assertEqual(main(["add", "main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)

        with mock.patch(
            "src.provider_runtime.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            self.assertEqual(main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertIn("logics-manager status", _script_launch_text(launch_call))
        self.assertIn("cdx view", _script_launch_text(launch_call))

        self.assertEqual(main(["set", "main", "--logics", "off"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        with mock.patch(
            "src.provider_runtime.shutil.which",
            side_effect=lambda command, path=None: "/usr/bin/logics-manager" if command == "logics-manager" else None,
        ):
            self.assertEqual(main(["main"], {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir, "PATH": "/usr/bin"},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        launch_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        self.assertNotIn("logics-manager status", _script_launch_text(launch_call))

    def test_fast_on_enables_codex_service_tier_without_lowering_power(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        set_io = self.make_io()
        self.assertEqual(main([
            "set", "--sessions", "main,work1", "--fast", "on", "--json"
        ], {**set_io, "env": {"CDX_HOME": temp_dir}}), 0)
        payload = json.loads(set_io["stdout"].getvalue())
        self.assertTrue(all(
            session["launch"] == {"power": "medium", "fast": True, "fastMode": "service_tier"}
            for session in payload["sessions"]
        ))

        self.assertEqual(main(["main"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        codex_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "codex")
        ][-1]
        codex_text = _script_launch_text(codex_call)
        self.assertIn('model_reasoning_effort="medium"', codex_text)
        self.assertIn('service_tier="fast"', codex_text)
        self.assertIn("features.fast_mode=true", codex_text)

        self.assertEqual(main(["work1"], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
            "spawn": harness.spawn,
            "spawn_sync": harness.spawn_sync,
        }), 0)
        claude_call = [
            call for call in harness.calls
            if call["kind"] == "spawn" and call["command"] == "script" and _script_launch_invokes(call, "claude")
        ][-1]
        self.assertIn("--effort", _script_launch_args(claude_call))
        self.assertIn("medium", _script_launch_args(claude_call))

        unset_io = self.make_io()
        self.assertEqual(main([
            "set", "main", "--fast", "off", "--json"
        ], {**unset_io, "env": {"CDX_HOME": temp_dir}}), 0)
        self.assertEqual(json.loads(unset_io["stdout"].getvalue())["launch"], {"fast": False, "power": "medium"})

    def test_unset_launch_settings_can_target_all_sessions(self):
        temp_dir = self.make_temp_dir()
        harness = _AuthHarness()
        for args in (["add", "main"], ["add", "claude", "work1"]):
            self.assertEqual(main(args, {
                **self.make_io(),
                "env": {"CDX_HOME": temp_dir},
                "spawn": harness.spawn,
                "spawn_sync": harness.spawn_sync,
            }), 0)

        self.assertEqual(main([
            "set", "--sessions", "all", "--permission", "full"
        ], {
            **self.make_io(),
            "env": {"CDX_HOME": temp_dir},
        }), 0)

        unset_io = self.make_io()
        self.assertEqual(main([
            "unset", "--sessions", "all", "--permission", "--json"
        ], {
            **unset_io,
            "env": {"CDX_HOME": temp_dir},
        }), 0)
        payload = json.loads(unset_io["stdout"].getvalue())
        self.assertEqual(payload["updated_count"], 2)
        self.assertTrue(all("permission" not in session["launch"] for session in payload["sessions"]))
        self.assertTrue(all(session["launch"]["power"] == "medium" for session in payload["sessions"]))
        self.assertTrue(all(session["launch"]["fast"] is False for session in payload["sessions"]))

    def test_set_and_run_accept_the_same_values(self):
        from src import config
        from src.session_service import _normalize_launch_settings

        # A value accepted by one command must be accepted by the other; the
        # asymmetry this replaces rejected `cdx set --permission workspace-write`
        # while `cdx run --permission workspace-write` worked.
        target = self.make_temp_dir()
        for permission in config.PERMISSION_INPUT_VALUES:
            expected = config.normalize_permission(permission)
            self.assertEqual(
                _parse_run_args(["main", "--cwd", target, "--prompt", "x",
                                 "--permission", permission, "--json"])["permission"],
                expected,
            )
            self.assertEqual(
                _normalize_launch_settings({"permission": permission})["permission"],
                expected,
            )

        for effort in config.REASONING_EFFORT_VALUES:
            _parse_run_args(["main", "--cwd", target, "--prompt", "x",
                             "--reasoning-effort", effort, "--json"])
            _normalize_launch_settings({"power": effort})
            _normalize_launch_settings({"reasoning_effort": effort})


    def test_extra_args_reach_every_spec_unchanged_and_never_via_a_shell(self):
        from src import provider_runtime

        session = {
            "name": "s",
            "provider": "claude",
            "authHome": "/tmp/home",
            "launch": {"extra_args": "--add-dir '../shared dir' --allowedTools 'Bash(git *)'"},
        }

        specs = [
            provider_runtime._build_launch_spec(session, cwd="/tmp/repo", capture_transcript=False),
            provider_runtime._build_resume_spec(session, cwd="/tmp/repo", capture_transcript=False),
            provider_runtime._build_headless_launch_spec(session, cwd="/tmp/repo", initial_prompt="go"),
        ]

        for spec in specs:
            args = spec["args"]
            # Split into literal argv entries: the quoted values survive whole,
            # and nothing is ever handed to a shell to re-interpret.
            self.assertIn("../shared dir", args)
            self.assertIn("Bash(git *)", args)
            self.assertEqual(args[args.index("--add-dir") + 1], "../shared dir")

    def test_extra_args_are_rejected_when_they_are_not_an_argument_list(self):
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("solo", "claude")

        with self.assertRaises(CdxError):
            main(["set", "solo", "--extra-args", "--add-dir 'unbalanced"], {**self.make_io(), "service": service})

        self.assertIsNone((service["get_session"]("solo").get("launch") or {}).get("extra_args"))

    def test_extra_args_land_after_the_settings_cdx_maps(self):
        from src import provider_runtime

        session = {
            "name": "s",
            "provider": "claude",
            "authHome": "/tmp/home",
            "launch": {"model": "sonnet", "extra_args": "--model opus"},
        }

        args = provider_runtime._build_launch_spec(session, cwd="/tmp/repo", capture_transcript=False)["args"]

        # Last occurrence wins in the provider CLI, so the passthrough overrides
        # the mapped setting. That is the point of the escape hatch.
        self.assertGreater(args.index("opus"), args.index("sonnet"))
