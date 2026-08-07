"""Tests for the shared session ranking contract.

Moved verbatim from test_cli_py.py; see test/cli_test_support.py for fixtures.
"""


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


class SessionRankingContractTests(CliTestBase):

    def test_every_selector_agrees_on_the_best_session(self):
        from src.status_view import recommend_priority_rows

        rows = [self._row("beta", available_pct=30), self._row("alpha", available_pct=80, priority=10)]

        ranked, _ = self._ranked(rows)
        self.assertEqual(recommend_priority_rows(rows)[0]["session_name"], ranked[0])

    def test_require_ready_rejects_an_unknown_auth_state(self):
        names, _ = self._ranked(
            [self._row("unknown", auth_status="unknown"), self._row("known")],
            require_ready=True,
        )

        # `cdx run --provider` asks for readiness so it does not hand work to a
        # session that will fail at launch; unknown is not ready.
        self.assertEqual(names, ["known"])

    def test_lower_reasoning_effort_wins_a_tie(self):
        names, decision = self._ranked([
            self._row("strong", reasoning_effort="xhigh"),
            self._row("cheap", reasoning_effort="low"),
        ])

        # Deliberate cost preference, kept from the headless ranking where it
        # was implied by an un-negated sort term.
        self.assertEqual(names[0], "cheap")
        self.assertEqual(decision, "reasoning_effort")

    def test_single_candidate_reports_no_deciding_factor(self):
        _names, decision = self._ranked([self._row("only")])

        self.assertIsNone(decision)

