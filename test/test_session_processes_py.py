"""Process and command contract tests using synthetic proc and session files."""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src import session_processes as discovery
from src.cli_args import cdx_schema
from src.commands.status import handle_sessions


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    if sys.platform != "linux":
        pytest.skip("Linux proc fixtures")
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "stat").write_text("btime 1700000000\n", encoding="utf-8")
    monkeypatch.setattr(discovery, "PROC_ROOT", proc)
    monkeypatch.setattr(os, "sysconf", lambda _: 100)
    home = tmp_path / "profile"
    home.mkdir()
    session = {"name": "work", "provider": "claude", "authHome": str(home),
               "conversation": {"id": "saved-launch"}}

    def process(pid, executable="claude", parent=1, args=(), env=None, uid=None, state="S"):
        root = proc / str(pid)
        root.mkdir()
        fields = [state, str(parent)] + ["0"] * 17 + ["250"] + ["0"] * 10
        (root / "stat").write_text(f"{pid} (agent with spaces) {' '.join(fields)}", encoding="utf-8")
        uid = os.getuid() if uid is None else uid
        (root / "status").write_text(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="utf-8")
        (root / "exe").symlink_to("/usr/bin/" + executable)
        (root / "cwd").symlink_to("/work/live")
        (root / "cmdline").write_bytes("\0".join([executable, *args, ""]).encode())
        (root / "environ").write_bytes("\0".join(f"{k}={v}" for k, v in (env or {"HOME": str(home)}).items()).encode())
        return root

    def session_file(pid, identifier="current-conversation", config=None):
        path = (config or home / ".claude") / "sessions" / f"{pid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sessionId": identifier}), encoding="utf-8")
        return path

    return SimpleNamespace(proc=proc, home=home, session=session, process=process, session_file=session_file)


def test_wrapper_children_clear_and_two_sessions(fixture):
    f = fixture
    f.process(100, "script", args=("-q", "-f", "-c", "claude --session-id launch-first"))
    f.process(101, "sh", parent=100)
    f.process(102, parent=101, args=("--session-id", "launch-first"))
    f.process(103, args=("--session-id=launch-second",))
    path = f.session_file(102, "before-clear")
    f.session_file(103, "second-current")
    rows = discovery.discover_session_processes([f.session])["work"]
    assert [r["agent_pid"] for r in rows] == [102, 103]
    assert rows[0] == {"agent_pid": 102, "wrapper_pid": 100, "provider": "claude",
                       "conversation_id": "before-clear", "conversation_source": "claude_session_file",
                       "launch_conversation_id": "launch-first", "cwd": "/work/live",
                       "started_at": "2023-11-14T22:13:22.500000+00:00"}
    assert rows[1]["wrapper_pid"] is None
    assert rows[1]["conversation_id"] == "second-current"
    path.write_text(json.dumps({"sessionId": "after-clear"}), encoding="utf-8")
    assert discovery.discover_session_processes([f.session])["work"][0]["conversation_id"] == "after-clear"
    assert f.session["conversation"]["id"] == "saved-launch"


def test_missing_invalid_oversized_session_and_cwd(fixture):
    f = fixture
    root = f.process(102)
    (root / "cwd").unlink()
    row = discovery.discover_session_processes([f.session])["work"][0]
    assert row["cwd"] is None
    assert row["conversation_id"] is None
    assert row["conversation_source"] == "claude_session_file_missing"
    path = f.session_file(102)
    for contents, reason in [('{}', 'claude_session_file_invalid'), ('[]', 'claude_session_file_invalid'),
                             ('{', 'claude_session_file_unavailable'), ('x' * 16385, 'claude_session_file_unavailable')]:
        path.write_text(contents, encoding="utf-8")
        row = discovery.discover_session_processes([f.session])["work"][0]
        assert row["conversation_id"] is None
        assert row["conversation_source"] == reason


def test_explicit_config_dir_and_node_claude(fixture):
    f = fixture
    f.process(102, "node", args=("/opt/@anthropic-ai/claude-code/cli.js", "--resume", "launch-resume"),
              env={"HOME": "/unrelated", "CLAUDE_CONFIG_DIR": str(f.home)})
    f.session_file(102, config=f.home)
    row = discovery.discover_session_processes([f.session])["work"][0]
    assert row["conversation_id"] == "current-conversation"
    assert row["launch_conversation_id"] == "launch-resume"


def test_foreign_users_unrelated_zombies_and_ambiguous_profiles_are_skipped(fixture):
    f = fixture
    foreign = f.process(101, uid=os.getuid() + 1)
    f.process(102, state="Z")
    f.process(103, env={"HOME": "/another-profile"})
    f.process(104, "sh", args=("-c", "claude --session-id misleading"))
    original = discovery._read

    def guarded(path, *args):
        assert path != foreign / "environ"
        assert path != foreign / "cmdline"
        return original(path, *args)

    with patch.object(discovery, "_read", side_effect=guarded):
        assert discovery.discover_session_processes([f.session]) == {"work": []}
    f.process(105)
    assert discovery.discover_session_processes([f.session, {**f.session, "name": "duplicate"}]) == {"work": [], "duplicate": []}
    with patch.object(os, "getuid", return_value=os.getuid() + 1), patch.object(discovery, "_read", side_effect=AssertionError):
        assert discovery.discover_session_processes([f.session]) == {"work": []}


def test_unowned_session_file_is_not_read(fixture):
    f = fixture
    f.process(102)
    path = f.session_file(102)
    inode = path.stat().st_ino
    original = os.fstat

    def ownership(fd):
        info = original(fd)
        return SimpleNamespace(st_uid=info.st_uid + 1, st_mode=info.st_mode) if info.st_ino == inode else info

    with patch.object(os, "fstat", side_effect=ownership):
        row = discovery.discover_session_processes([f.session])["work"][0]
    assert row["conversation_id"] is None
    assert row["conversation_source"] == "claude_session_file_unavailable"


def test_other_providers_report_only_reliable_fields(fixture):
    f = fixture
    codex = {**f.session, "provider": "codex", "name": "codex"}
    agy = {**f.session, "provider": "antigravity", "name": "agy"}
    f.process(101, "codex", env={"CODEX_HOME": str(f.home)})
    f.process(102, "agy")
    rows = discovery.discover_session_processes([codex, agy])
    for name, pid in (("codex", 101), ("agy", 102)):
        row = rows[name][0]
        assert row["agent_pid"] == pid
        assert row["conversation_id"] is None
        assert row["launch_conversation_id"] is None
        assert row["conversation_source"] == "current_conversation_unavailable"
        assert row["cwd"] == "/work/live"


def test_scan_and_reads_are_bounded(fixture, monkeypatch):
    f = fixture
    for pid in range(100, 110):
        f.process(pid)
    monkeypatch.setattr(discovery, "MAX_PROCESSES", 3)
    assert len(discovery.discover_session_processes([f.session])["work"]) <= 3
    monkeypatch.setattr(discovery, "MAX_PROCESSES", 8192)
    for path in f.proc.glob("*/environ"):
        path.write_bytes(b"x" * (discovery.MAX_FILE_BYTES + 1))
    assert discovery.discover_session_processes([f.session]) == {"work": []}


def test_missing_proc_and_non_linux_return_empty(fixture, monkeypatch):
    monkeypatch.setattr(discovery, "PROC_ROOT", fixture.proc / "missing")
    assert discovery.discover_session_processes([fixture.session]) == {"work": []}
    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    assert discovery.discover_session_processes([fixture.session]) == {"work": []}


def test_sessions_command_keeps_profile_rows_and_fields(fixture):
    f = fixture
    f.process(100, "script")
    f.process(102, parent=100, args=("--session-id", "actual-launch"))
    f.process(103)
    f.session_file(102)
    idle = {**f.session, "name": "idle", "authHome": str(f.home / "idle")}
    runtime = {"pid": 100, "cwd": "/launch-cwd", "startedAt": "launch-time", "runId": "runtime-id"}
    output = []
    ctx = {"service": {"list_sessions": lambda: [f.session, idle],
                       "active_session_runtime": lambda name: runtime if name == "work" else None},
           "out": output.append}
    assert handle_sessions(["--json"], ctx) == 0
    row = json.loads("".join(output))["sessions"][0]
    processes = row.pop("processes")
    assert row == {"session": "work", "provider": "claude", "active": True, "pid": 100,
                   "cwd": "/launch-cwd", "started_at": "launch-time", "runtime_id": "runtime-id",
                   "conversation_id": "saved-launch", "profile_dir": str(f.home),
                   "transcripts_dir": str(f.home / ".claude" / "projects")}
    assert [p["agent_pid"] for p in processes] == [102, 103]
    output.clear()
    assert handle_sessions(["--all", "--json"], ctx) == 0
    rows = json.loads("".join(output))["sessions"]
    assert len(rows) == 2
    assert rows[1]["processes"] == []
    schema = cdx_schema()
    assert set(schema["outputs"]["sessions"]["processes"]["items"]) == set(processes[0])


def test_native_claude_and_process_exit_during_discovery(fixture):
    f = fixture
    root = f.process(102)
    (root / "exe").unlink()
    (root / "exe").symlink_to("/home/user/.local/share/claude/versions/2.1.0")
    assert discovery.discover_session_processes([f.session])["work"][0]["agent_pid"] == 102
    original = discovery._read

    def exiting(path, *args):
        if path == root / "environ":
            (root / "stat").unlink()
        return original(path, *args)

    with patch.object(discovery, "_read", side_effect=exiting):
        assert discovery.discover_session_processes([f.session]) == {"work": []}


def test_missing_process_files_and_timing_do_not_fail_command(fixture):
    f = fixture
    f.process(101)
    root = f.process(102)
    (root / "environ").unlink()
    (f.proc / "stat").unlink()
    rows = discovery.discover_session_processes([f.session])["work"]
    assert len(rows) == 1
    assert rows[0]["agent_pid"] == 101
    assert rows[0]["started_at"] is None
