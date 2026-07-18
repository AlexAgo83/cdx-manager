import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_release_checksums import validate_release_checksums  # noqa: E402


class ReleaseChecksumsTests(unittest.TestCase):
    def _write_release_root(self, temp_dir, version="1.2.3", releases=None):
        root = Path(temp_dir)
        (root / "src").mkdir()
        (root / "checksums").mkdir()
        (root / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        (root / "pyproject.toml").write_text(f'version = "{version}"\n', encoding="utf-8")
        (root / "src" / "cli.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
        (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (root / "checksums" / "release-archives.json").write_text(
            json.dumps({"schema_version": 1, "releases": releases or {}}),
            encoding="utf-8",
        )
        return root

    def test_release_archive_checksums_are_sha256_hex_strings(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / "checksums" / "release-archives.json").read_text(encoding="utf-8"))
        checksum_re = re.compile(r"^[0-9a-f]{64}$")

        for tag, entry in (payload.get("releases") or {}).items():
            with self.subTest(tag=tag):
                self.assertRegex(entry.get("github_tarball_sha256", ""), checksum_re)
                self.assertRegex(entry.get("github_zip_sha256", ""), checksum_re)

    def test_standalone_installers_use_tagged_release_checksum_asset(self):
        root = Path(__file__).resolve().parents[1]
        shell = (root / "install.sh").read_text(encoding="utf-8")
        powershell = (root / "install.ps1").read_text(encoding="utf-8")

        for text in (shell, powershell):
            self.assertIn("releases/download/", text)
            self.assertIn("release-archives.json", text)
            self.assertNotIn("contents/checksums/release-archives.json?ref=main", text)
            self.assertNotIn("raw.githubusercontent.com/$REPO/main/checksums/release-archives.json", text)
            self.assertIn("CDX_ALLOW_UNVERIFIED=1 disables archive integrity checks", text)

    def test_release_validator_accepts_project_when_checksum_metadata_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(
                temp_dir,
                releases={
                    "v1.2.3": {
                        "github_tarball_sha256": "a" * 64,
                        "github_zip_sha256": "b" * 64,
                    }
                },
            )

            self.assertEqual(validate_release_checksums(root), "v1.2.3")

    def test_release_validator_rejects_missing_current_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(temp_dir)

            with self.assertRaisesRegex(ValueError, "missing release checksum metadata for v1.2.3"):
                validate_release_checksums(root)

    def test_release_validator_requires_both_archive_checksums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(
                temp_dir,
                releases={
                    "v1.2.3": {
                        "github_tarball_sha256": "a" * 64,
                    }
                },
            )

            with self.assertRaisesRegex(ValueError, "github_zip_sha256"):
                validate_release_checksums(root)

    def test_release_validator_rejects_tag_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._write_release_root(temp_dir)

            with self.assertRaisesRegex(ValueError, "does not match project version"):
                validate_release_checksums(root, tag="v9.9.9")
