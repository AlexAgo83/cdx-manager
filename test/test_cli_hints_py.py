"""Setup hints: shown while actionable, and quiet everywhere else."""
import json
import os

from cli_test_support import CliTestBase

from src.cli import main
from src.cli_hints import MAX_SHOWINGS, QUIET_SECONDS, available_hints, next_hint
from src.session_service import create_session_service


class HintSelectionTest(CliTestBase):
    def _sessions(self, notify=False):
        return [{"name": "work", "provider": "codex", "enabled": True, "notify": notify}]

    def test_no_sessions_means_no_hints(self):
        """Every hint presumes something to watch. With nothing registered,
        suggesting a quota watcher is advice about an empty room."""
        base = self.make_temp_dir()
        self.assertEqual(available_hints(base, {}, []), [])

    def test_the_tray_hint_yields_to_an_install_override(self):
        """`CDX_TRAY_BIN` means a companion is already in use, built locally.
        Telling that user to install one would be telling them to undo their setup."""
        base = self.make_temp_dir()
        codes = [code for code, _ in available_hints(base, {"CDX_TRAY_BIN": "/tmp/cdx-tray"}, self._sessions())]
        self.assertNotIn("tray_not_installed", codes)

    def test_alerts_hint_disappears_once_a_session_has_them(self):
        base = self.make_temp_dir()
        with_alerts = [code for code, _ in available_hints(base, {}, self._sessions(notify=True))]
        without = [code for code, _ in available_hints(base, {}, self._sessions(notify=False))]
        self.assertIn("agent_alerts_off", without)
        self.assertNotIn("agent_alerts_off", with_alerts)


class HintPacingTest(CliTestBase):
    def _sessions(self):
        return [{"name": "work", "provider": "codex", "enabled": True, "notify": False}]

    def test_a_hint_is_not_repeated_within_the_quiet_window(self):
        """A burst of commands must show one hint, not one per command."""
        base = self.make_temp_dir()
        first = next_hint(base, {}, self._sessions(), now=1000.0)
        second = next_hint(base, {}, self._sessions(), now=1000.0 + 60)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_a_hint_retires_after_being_shown_enough(self):
        """Three showings without action is an answer. Asking again is nagging."""
        base = self.make_temp_dir()
        now = 1000.0
        seen = []
        for _ in range(MAX_SHOWINGS + 2):
            message = next_hint(base, {}, self._sessions(), now=now)
            if message:
                seen.append(message)
            now += QUIET_SECONDS + 1
        counted = seen.count(seen[0])
        self.assertEqual(counted, MAX_SHOWINGS, seen)

    def test_the_off_switch_is_honoured(self):
        base = self.make_temp_dir()
        self.assertIsNone(next_hint(base, {"CDX_NO_HINTS": "1"}, self._sessions(), now=1000.0))

    def test_a_damaged_state_file_costs_a_hint_not_a_crash(self):
        base = self.make_temp_dir()
        with open(os.path.join(base, "hints.json"), "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertIsNotNone(next_hint(base, {}, self._sessions(), now=1000.0))


class HintOutputTest(CliTestBase):
    def _run(self, argv, service, temp_dir):
        io_obj = self.make_io()
        code = main(argv, {**io_obj, "service": service, "env": {"CDX_HOME": temp_dir}})
        return code, io_obj["stdout"].getvalue()

    def test_json_output_never_carries_a_hint(self):
        """The JSON is a contract. A friendly line inside it is a parse error
        somewhere else, so the hint belongs only to the human rendering."""
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        code, out = self._run(["status", "--cached", "--json"], service, temp_dir)
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertNotIn("Did you know?", out)
        self.assertTrue(all("Did you know?" not in str(w) for w in payload.get("warnings", [])))

    def test_an_update_notice_takes_the_last_line(self):
        """Both want the last line. One is actionable news about the tool being
        run, the other is optional discovery, so they never stack."""
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        io_obj = self.make_io()
        main(["status", "--cached"], {
            **io_obj, "service": service, "env": {"CDX_HOME": temp_dir},
            "checkForUpdate": lambda _base_dir, _version, env=None, now_fn=None: {
                "latest_version": "9.9.9",
                "url": "https://example.invalid/release",
            },
        })
        out = io_obj["stdout"].getvalue()
        lines = [line for line in out.splitlines() if line]
        self.assertTrue(lines[-1].startswith("Update available"), lines[-1])
        self.assertNotIn("Did you know?", out)

    def test_the_human_rendering_can_carry_one(self):
        """The other half of the same rule: suppressed in JSON, present for a
        person. Without this, the JSON test would pass on a broken feature."""
        temp_dir = self.make_temp_dir()
        service = create_session_service({"base_dir": temp_dir})
        service["create_session"]("work")
        _code, out = self._run(["status", "--cached"], service, temp_dir)
        self.assertIn("Did you know?", out)
