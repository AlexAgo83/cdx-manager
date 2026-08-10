#!/usr/bin/env python3
"""Record tray companion asset checksums in the release ledger.

Kept apart from `update_release_checksums.py`, which records the tarballs GitHub
generates from a tag. These are artifacts we build ourselves, per OS and
architecture, and `cdx tray install` refuses any asset that has no entry here.
That refusal is the point: the companion is self-signed, so this ledger is what
vouches for it.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "checksums" / "release-archives.json"
ASSET_RE = re.compile(r"^cdx-tray-(?P<version>[0-9][^-]*)-(?P<target>[a-z0-9_.-]+)\.tar\.gz$")


def parse_asset(path):
    """The version and target an asset name declares, or None.

    Read from the filename rather than passed separately, so a mislabelled file
    cannot be recorded under the wrong target and then installed on a machine it
    cannot run on.
    """
    match = ASSET_RE.match(Path(path).name)
    if not match:
        return None
    return match.group("version"), match.group("target")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(ledger_path, assets):
    ledger = {"schema_version": 1, "releases": {}}
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    releases = ledger.setdefault("releases", {})
    recorded = []
    for asset in assets:
        parsed = parse_asset(asset)
        if not parsed:
            raise SystemExit(f"Not a tray asset name: {asset}")
        version, target = parsed
        entry = releases.setdefault(f"v{version}", {})
        entry.setdefault("tray_assets", {})[target] = sha256(asset)
        recorded.append((f"v{version}", target))
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return recorded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", nargs="+", help="cdx-tray-<version>-<target>.tar.gz files")
    parser.add_argument("--ledger", default=str(LEDGER))
    args = parser.parse_args(argv)
    for tag, target in record(Path(args.ledger), args.assets):
        print(f"recorded {tag} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
