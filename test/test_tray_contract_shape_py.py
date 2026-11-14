"""The tray snapshot shape is pinned per schema version (req_085, item_172).

cdx-tray rebuilds only when the contract breaks, so a shape change must come with a version bump:
added keys need a new minor, removed or renamed keys a new major. Record each version's shape in
test/fixtures/tray_contract_shapes.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.tray_contract import SCHEMA_MAJOR, SCHEMA_MINOR, build_snapshot

SHAPES = json.loads((Path(__file__).parent / "fixtures" / "tray_contract_shapes.json").read_text())


def _current_shape():
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    row = {"session_name": "work", "provider": "codex", "available_pct": 50, "remaining_5h_pct": 50,
           "remaining_week_pct": 60, "updated_at": now.isoformat(), "enabled": True}
    snapshot = build_snapshot([row], now, "0.0.0")
    return {"snapshot": sorted(snapshot), "icon": sorted(snapshot["icon"]), "session": sorted(snapshot["sessions"][0])}


def _version(key):
    major, minor = key.split(".")
    return int(major), int(minor)


def test_the_current_schema_version_has_a_recorded_shape_that_matches():
    key = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}"
    assert key in SHAPES, f"record the shape of tray schema {key} in tray_contract_shapes.json"
    assert _current_shape() == SHAPES[key], (
        "the tray snapshot shape changed: bump SCHEMA_MINOR for added keys or SCHEMA_MAJOR for removed "
        "or renamed keys, then record the new shape")


def test_minor_versions_only_add_keys():
    versions = sorted(SHAPES, key=_version)
    for older, newer in zip(versions, versions[1:]):
        if _version(older)[0] == _version(newer)[0]:
            for part in ("snapshot", "icon", "session"):
                assert set(SHAPES[older][part]) <= set(SHAPES[newer][part]), (
                    f"{newer} removes {part} keys of {older}: that is a major version")
