#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _package_version(root):
    return str(_read_json(root / "package.json").get("version") or "").strip()


def _python_version(root):
    match = re.search(
        r'^version = "([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def _cli_version(root):
    """What `cdx --version` actually reports, not what a literal claims.

    cli.py used to restate the version as a fourth hardcoded copy and drifted a
    release behind. It now resolves the value, so scraping a `VERSION = "..."`
    literal finds nothing and this validator refused every release. The check
    that matters is unchanged - does the CLI report the same version as the
    declarations - so it is made against the resolved value.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "from src.cli import VERSION; print(VERSION)"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _version_file(root):
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def expected_versions(root):
    return {
        "package.json": _package_version(root),
        "pyproject.toml": _python_version(root),
        "src/cli.py": _cli_version(root),
        "VERSION": _version_file(root),
    }


def _normalize_tag(tag):
    tag = str(tag or "").strip()
    if not tag:
        return ""
    return tag if tag.startswith("v") else f"v{tag}"


def validate_release_checksums(root, tag=None, checksums_file=None):
    root = Path(root)
    versions = expected_versions(root)
    unique_versions = {value for value in versions.values() if value}
    missing_version_sources = [name for name, value in versions.items() if not value]
    if missing_version_sources:
        raise ValueError("Missing release version in: " + ", ".join(missing_version_sources))
    if len(unique_versions) != 1:
        details = ", ".join(f"{name}={value}" for name, value in versions.items())
        raise ValueError(f"Release versions do not match: {details}")

    version = next(iter(unique_versions))
    expected_tag = _normalize_tag(tag or version)
    if expected_tag != f"v{version}":
        raise ValueError(f"Release tag {expected_tag} does not match project version {version}")

    checksums_path = Path(checksums_file) if checksums_file else root / "checksums" / "release-archives.json"
    payload = _read_json(checksums_path)
    entry = (payload.get("releases") or {}).get(expected_tag)
    if not isinstance(entry, dict):
        raise ValueError(f"{checksums_path} is missing release checksum metadata for {expected_tag}")

    missing_fields = [
        field
        for field in ("github_tarball_sha256", "github_zip_sha256")
        if not SHA256_RE.match(str(entry.get(field) or ""))
    ]
    if missing_fields:
        raise ValueError(
            f"{checksums_path} entry {expected_tag} is missing valid SHA-256 field(s): "
            + ", ".join(missing_fields)
        )
    return expected_tag


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Validate that the current release version has GitHub archive checksums "
            "before registry publication."
        )
    )
    parser.add_argument("--tag", help="Release tag to validate, for example v0.7.8")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root to validate",
    )
    parser.add_argument("--checksums-file", help="Override checksums/release-archives.json path")
    args = parser.parse_args(argv)

    try:
        resolved_tag = validate_release_checksums(args.root, tag=args.tag, checksums_file=args.checksums_file)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Release checksum validation failed: {error}") from error

    print(f"Release checksum validation OK for {resolved_tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
