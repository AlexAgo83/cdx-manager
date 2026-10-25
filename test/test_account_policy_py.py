"""Accounts cdx must not pick on the user's behalf."""

import unittest

from src.errors import CdxError
from src.session_ranking import candidate_rows
from src.session_service import _normalize_launch_settings


def _row(name, policy):
    return {"session_name": name, "provider": "claude", "auth_status": "authenticated",
            "available_pct": 90, "policy": policy}


class AccountPolicyTests(unittest.TestCase):
    def test_automatic_selection_skips_ask_first_and_never(self):
        rows = [_row("mine", "use"), _row("shared", "ask-first"), _row("colleague", "never")]
        self.assertEqual([r["session_name"] for r in candidate_rows(rows)], ["mine"])

    def test_policy_values_are_validated(self):
        self.assertEqual(_normalize_launch_settings({"policy": "ask-first"})["policy"], "ask-first")
        with self.assertRaises(CdxError):
            _normalize_launch_settings({"policy": "sometimes"})


if __name__ == "__main__":
    unittest.main()
