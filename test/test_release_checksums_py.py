import json
import re
import unittest
from pathlib import Path


class ReleaseChecksumsTests(unittest.TestCase):
    def test_current_version_has_release_archive_checksums(self):
        root = Path(__file__).resolve().parents[1]
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        payload = json.loads((root / "checksums" / "release-archives.json").read_text(encoding="utf-8"))

        entry = (payload.get("releases") or {}).get(f"v{version}")

        self.assertIsInstance(entry, dict)
        self.assertRegex(entry.get("github_tarball_sha256", ""), r"^[0-9a-f]{64}$")
        self.assertRegex(entry.get("github_zip_sha256", ""), r"^[0-9a-f]{64}$")

    def test_release_archive_checksums_are_sha256_hex_strings(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / "checksums" / "release-archives.json").read_text(encoding="utf-8"))
        checksum_re = re.compile(r"^[0-9a-f]{64}$")

        for tag, entry in (payload.get("releases") or {}).items():
            with self.subTest(tag=tag):
                self.assertRegex(entry.get("github_tarball_sha256", ""), checksum_re)
                self.assertRegex(entry.get("github_zip_sha256", ""), checksum_re)
