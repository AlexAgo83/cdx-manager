import io
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_release_ci import normalize_tag, resolve_tag_commit, verify_ci_success  # noqa: E402


class FakeApi:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def get(self, path, params=None):
        self.requests.append((path, params or {}))
        key = (path, tuple(sorted((params or {}).items())))
        if key in self.responses:
            return self.responses[key]
        if path in self.responses:
            return self.responses[path]
        raise AssertionError(f"unexpected request: {path} {params}")


class ReleaseCiTests(unittest.TestCase):
    def test_normalize_tag_adds_v_prefix(self):
        self.assertEqual(normalize_tag("0.9.2"), "v0.9.2")
        self.assertEqual(normalize_tag("v0.9.2"), "v0.9.2")

    def test_resolve_tag_commit_handles_lightweight_tag(self):
        api = FakeApi({"/git/ref/tags/v1.2.3": {"object": {"type": "commit", "sha": "abc123"}}})

        self.assertEqual(resolve_tag_commit(api, "1.2.3"), "abc123")

    def test_resolve_tag_commit_handles_annotated_tag(self):
        api = FakeApi(
            {
                "/git/ref/tags/v1.2.3": {"object": {"type": "tag", "sha": "tag-sha"}},
                "/git/tags/tag-sha": {"object": {"type": "commit", "sha": "commit-sha"}},
            }
        )

        self.assertEqual(resolve_tag_commit(api, "v1.2.3"), "commit-sha")

    def test_verify_ci_success_accepts_successful_run_for_tag_commit(self):
        api = FakeApi(
            {
                "/git/ref/tags/v1.2.3": {"object": {"type": "commit", "sha": "commit-sha"}},
                (
                    "/actions/workflows/ci.yml/runs",
                    (("head_sha", "commit-sha"), ("per_page", 50)),
                ): {
                    "workflow_runs": [
                        {
                            "head_sha": "commit-sha",
                            "status": "completed",
                            "conclusion": "success",
                            "created_at": "2026-06-16T10:00:00Z",
                            "html_url": "https://example.test/run",
                        }
                    ]
                },
            }
        )
        out = io.StringIO()

        self.assertEqual(verify_ci_success(api, "v1.2.3", timeout=0, output=out), "commit-sha")
        self.assertIn("Release CI validation OK", out.getvalue())

    def test_verify_ci_success_fails_when_timeout_expires_without_success(self):
        api = FakeApi(
            {
                "/git/ref/tags/v1.2.3": {"object": {"type": "commit", "sha": "commit-sha"}},
                (
                    "/actions/workflows/ci.yml/runs",
                    (("head_sha", "commit-sha"), ("per_page", 50)),
                ): {
                    "workflow_runs": [
                        {
                            "head_sha": "commit-sha",
                            "status": "completed",
                            "conclusion": "failure",
                        }
                    ]
                },
            }
        )

        with self.assertRaises(TimeoutError):
            verify_ci_success(api, "v1.2.3", timeout=0, output=io.StringIO())


if __name__ == "__main__":
    unittest.main()
