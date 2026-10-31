"""Source attribution survives disposable workspaces without changing accounting."""

import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from src.cli import main
from src.commands.runs import _detached_child_argv
from src.commands.status import _stats_group, _stats_totals, _summarize_stats
from src.errors import CdxError
from src.project_identity import load_mapping, recorded_project, resolve_project
from src.run_registry import RunRegistry
from src.run_usage import normalize_usage
from src.session_service import create_session_service


def git(*args):
    subprocess.run(["git", *map(str, args)], check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "source" / "app"
    root.mkdir(parents=True)
    git("init", root)
    git("-C", root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "Initial")
    return root.resolve()


@pytest.fixture
def history(tmp_path):
    service = create_session_service({"base_dir": str(tmp_path / "cdx"), "env": {}})
    service["create_session"]("work", provider="claude")
    return service, tmp_path / "cdx" / "state" / "launch_history.jsonl"


def append(service, run_id, **extra):
    service["record_launch_history"]("work", {
        "run_id": run_id, "cwd": "/deleted/missions/1cb05ab48d", "duration_ms": 12,
        "usage_model": "claude-sonnet-5-5", "usage": normalize_usage(input_tokens=100, output_tokens=10), **extra})


def mapping_file(tmp_path, projects):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"version": 1, "projects": projects}))
    return str(path)


def test_worktree_subdirectory_and_deleted_workspace(repository, tmp_path):
    tree = tmp_path / "missions" / "disposable"
    git("-C", repository, "worktree", "add", "-b", "mission", tree)
    subdir = tree / "nested"
    subdir.mkdir()
    expected = {"project": str(repository), "project_source": "git"}
    assert resolve_project(repository) == expected
    saved = resolve_project(subdir)
    assert saved == expected
    git("-C", repository, "worktree", "remove", "--force", tree)
    assert _stats_group({"cwd": str(subdir), **saved}, "project") == str(repository)
    assert resolve_project(tree)["project"] is None


def test_clone_needs_explicit_source_and_unknown_is_not_a_folder(repository, tmp_path):
    clone = tmp_path / "temporary-clone"
    git("clone", repository, clone)
    assert resolve_project(clone)["project"] == str(clone)
    saved = resolve_project(clone, str(repository))
    shutil.rmtree(clone)
    assert _stats_group({"cwd": str(clone), **saved}, "project") == str(repository)
    assert resolve_project(tmp_path)["project"] is None
    assert _stats_group({"cwd": "/deleted/missions/eb54ed8001"}, "project") == "-"
    with pytest.raises(CdxError):
        resolve_project(tmp_path, "relative/app")


def test_mapping_preview_apply_idempotence_and_unchanged_totals(history, tmp_path):
    service, path = history
    for run_id in ("synthetic-run-1", "synthetic-run-2", "synthetic-run-3"):
        append(service, run_id)
    append(service, "unknown")
    with path.open("ab") as handle:
        handle.write(b"\ninvalid-json\n[]\n")
    original = path.read_bytes()
    # Read valid rows directly; malformed historical bytes must also survive.
    before_rows = [json.loads(line) for line in original.splitlines()[:4]]
    before = _stats_totals(_summarize_stats(before_rows))
    mapping = mapping_file(tmp_path, [{"run_id": run_id, "project": "/repos/remote-ops"}
                                      for run_id in ("synthetic-run-1", "synthetic-run-2", "synthetic-run-3")])
    preview = service["backfill_history_projects"](mapping_path=mapping)
    assert (preview["recovered"], preview["unresolved"], preview["applied"]) == (3, 1, 0)
    assert path.read_bytes() == original
    applied = service["backfill_history_projects"](mapping_path=mapping, dry_run=False)
    assert applied["applied"] == 3
    assert Path(applied["backup_path"]).read_bytes() == original
    assert path.read_bytes().endswith(b"\ninvalid-json\n[]\n")
    after_rows = [json.loads(line) for line in path.read_bytes().splitlines()[:4]]
    assert _stats_totals(_summarize_stats(after_rows)) == before
    for old, new in zip(before_rows, after_rows):
        assert {key: new[key] for key in old} == old
    again = service["backfill_history_projects"](mapping_path=mapping, dry_run=False)
    assert (again["recovered"], again["unchanged"], again["unresolved"]) == (0, 3, 1)
    assert len(list(path.parent.glob("*.bak"))) == 1


def test_conflict_blocks_entire_batch_and_checks_all_attempts(history, tmp_path):
    service, path = history
    append(service, "known", project="/a/app", project_source="git")
    append(service, "known")
    append(service, "missing")
    original = path.read_bytes()
    mapping = mapping_file(tmp_path, [{"run_id": "known", "project": "/b/app"},
                                      {"run_id": "missing", "project": "/a/app"}])
    result = service["backfill_history_projects"](mapping_path=mapping, dry_run=False)
    assert (result["conflicting"], result["applied"]) == (2, 0)
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.bak"))


@pytest.mark.parametrize("data", [None, {}, {"version": True, "projects": []},
    {"version": 1, "projects": [{"run_id": "x", "project": "relative"}]},
    {"version": 1, "projects": [{"run_id": "x", "project": "/a/../b"}]},
    {"version": 1, "projects": [{"run_id": "x", "project": "/a"}, {"run_id": "x", "project": "/b"}]}])
def test_invalid_mapping_schema(tmp_path, data):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(data))
    with pytest.raises(CdxError):
        load_mapping(path)


def test_mapping_exact_identity_and_no_current_cwd_lookup(history, tmp_path):
    service, path = history
    append(service, "exact")
    original = path.read_bytes()
    mapping = mapping_file(tmp_path, [{"run_id": "exa", "project": "/repos/app"}])
    with pytest.raises(CdxError, match="unknown exact run ids"):
        service["backfill_history_projects"](mapping_path=mapping, dry_run=False)
    with mock.patch("src.project_identity.resolve_project", side_effect=AssertionError("no live lookup")):
        assert service["backfill_history_projects"]()["unresolved"] == 1
    assert path.read_bytes() == original


def test_exact_recorded_report_recovers_after_deletion(history):
    service, path = history
    append(service, "exact")
    registry = RunRegistry(str(path.parent.parent))
    registry.start("exact", kind="assistant", session="work", provider="claude", model=None,
                   cwd="/deleted/mission", project="/source/app", project_source="git")
    registry.start("other", kind="assistant", session="work", provider="claude", model=None,
                   cwd="/deleted/mission", project="/wrong/app", project_source="git")
    assert service["backfill_history_projects"](dry_run=False)["applied"] == 1
    assert service["get_launch_history"]()[0]["project"] == "/source/app"


def test_cli_stats_json_uses_canonical_keys_and_disambiguated_labels(history):
    import io

    service, _ = history
    for run_id, project in (("one", "/a/app"), ("two", "/b/app"), ("three", "/a/app")):
        append(service, run_id, project=project, project_source="git")
    append(service, "unknown")
    payloads = []
    for grouping in ("session", "project"):
        out = io.StringIO()
        assert main(["stats", "--by", grouping, "--json"], {"service": service, "stdout": out, "env": {}}) == 0
        payloads.append(json.loads(out.getvalue()))
    assert {key: value for key, value in payloads[0]["totals"].items() if key != "sessions"} == {
        key: value for key, value in payloads[1]["totals"].items() if key != "sessions"}
    rows = {row["project"]: row for row in payloads[1]["stats"]}
    assert rows["/a/app"]["session_name"] == "a/app"
    assert rows["/b/app"]["session_name"] == "b/app"
    assert rows["/a/app"]["launches"] == 2
    assert rows["-"]["session_name"] == "-"


def test_detached_child_carries_resolved_source():
    argv = _detached_child_argv({"project": "/source/app"}, "/prompt", "work", "/temporary/clone")
    assert argv[argv.index("--project") + 1] == "/source/app"
    assert argv[argv.index("--cwd") + 1] == "/temporary/clone"


def test_history_command_defaults_to_preview_and_rejects_mixed_modes(history, tmp_path):
    import io

    service, path = history
    append(service, "exact")
    mapping = mapping_file(tmp_path, [{"run_id": "exact", "project": "/source/app"}])
    original = path.read_bytes()
    out = io.StringIO()
    ctx = {"service": service, "stdout": out, "env": {}}
    assert main(["history", "backfill-projects", "--mapping", mapping, "--json"], ctx) == 0
    assert json.loads(out.getvalue())["dry_run"] is True
    assert path.read_bytes() == original
    with pytest.raises(CdxError):
        main(["history", "backfill-projects", "--apply", "--dry-run"], ctx)
    assert main(["history", "backfill-projects", "--mapping", mapping, "--apply"], ctx) == 0
    assert service["get_launch_history"]()[0]["project"] == "/source/app"


def test_synthetic_tower_receipts_recover_84_attempts_without_changing_usage(history, tmp_path):
    service, _path = history
    projects = []
    expected = {"remote-ops": 66, "cdx-manager": 10, "logics-manager": 6, "city-jump": 2}
    for name, count in expected.items():
        for index in range(count):
            run_id = f"synthetic-cdx-{name}-{index}"
            append(service, run_id, cwd=f"/deleted/missions/synthetic-{name}-{index}")
            projects.append({"run_id": run_id, "project": f"/repos/{name}"})
    append(service, "synthetic-unresolved")
    before = _stats_totals(_summarize_stats(service["get_launch_history"](limit=0)))
    result = service["backfill_history_projects"](mapping_path=mapping_file(tmp_path, projects), dry_run=False)
    assert (result["recovered"], result["unresolved"], result["conflicting"]) == (84, 1, 0)
    entries = service["get_launch_history"](limit=0)
    rows = _summarize_stats([{**entry, "session_name": _stats_group(entry, "project")} for entry in entries])
    assert {row["session_name"]: row["launches"] for row in rows} == {
        **{f"/repos/{name}": count for name, count in expected.items()}, "-": 1}
    after = _stats_totals(rows)
    # Grouped sums retain the existing floating-point accounting order.
    assert after["cost_usd"] == pytest.approx(before["cost_usd"], abs=1e-12)
    assert {key: value for key, value in after.items() if key not in {"sessions", "cost_usd"}} == {
        key: value for key, value in before.items() if key not in {"sessions", "cost_usd"}}


@pytest.mark.parametrize("source", [None, [], {}, "unknown", "provider_output"])
def test_untrusted_or_malformed_attribution_stays_unknown(source):
    entry = {"project": "/source/app", "project_source": source}
    assert recorded_project(entry) is None
    assert _stats_group(entry, "project") == "-"


def test_cli_conflicts_return_failure_and_counts_without_writing(history, tmp_path):
    import io

    service, path = history
    append(service, "known", project="/source/app", project_source="git")
    original = path.read_bytes()
    mapping = mapping_file(tmp_path, [{"run_id": "known", "project": "/other/app"}])
    out = io.StringIO()
    assert main(["history", "backfill-projects", "--mapping", mapping, "--apply", "--json"],
                {"service": service, "stdout": out, "env": {}}) == 1
    payload = json.loads(out.getvalue())
    assert payload["ok"] is False
    assert (payload["conflicting"], payload["applied"]) == (1, 0)
    assert path.read_bytes() == original
