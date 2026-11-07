"""Fail closed when native selected-conversation evidence is unavailable."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from src import process_conversation as native
from src.conversation import read_conversation
from src.errors import CdxError

FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc evidence")


def rollout(home, identifier=FIRST):
    path = home / "sessions" / "2026" / f"rollout-2026-11-07-{identifier}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "session_meta", "payload": {
        "id": identifier, "source": "cli", "cwd": "/same-project"}}) + "\n")
    return path


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    proc = tmp_path / "proc"
    root = proc / "123"
    root.mkdir(parents=True)
    (proc / "sys/kernel/random").mkdir(parents=True)
    (proc / "sys/kernel/random/boot_id").write_text(FIRST)
    executable = tmp_path / "codex"
    executable.touch()
    (root / "exe").symlink_to(executable)
    (root / "stat").write_text("123 (codex with ) spaces) S " + " ".join(["0"] * 18 + ["100"]))
    (root / "status").write_text("Uid:\t" + "\t".join([str(os.getuid())] * 4) + "\n")
    home = tmp_path / "profile"
    rollout(home)
    monkeypatch.setattr(native, "PROC_ROOT", proc)
    return home, root


def assert_unknown(page, reason="native_conversation_identity_unavailable"):
    assert page["resolution_status"] == "unknown" and page["reason"] == reason
    assert page["entries"] == [] and page["conversation_id"] is None
    assert page["resolution_method"] is None and page["next_cursor"] is None


def test_fresh_resumed_and_reused_pid(evidence):
    home, root = evidence
    first = read_conversation("codex", home, pid=123, tail=1)
    assert_unknown(first)
    identity = first["process_identity"]
    assert identity.startswith("linux:123:")
    # Original resume argv is not evidence of the currently selected thread.
    (root / "cmdline").write_bytes(b"codex\0resume\0" + FIRST.encode())
    assert_unknown(read_conversation("codex", home, process_identity=identity))
    (root / "stat").write_text((root / "stat").read_text().replace("100", "101"))
    assert_unknown(read_conversation("codex", home, process_identity=identity), "process_identity_changed")


def test_switch_ambiguous_and_wrong_profile_never_choose_a_transcript(evidence):
    home, root = evidence
    path = rollout(home)
    (root / "fd").mkdir()
    (root / "fd/7").symlink_to(path)
    # A sole open old rollout cannot establish which TUI thread is selected.
    assert_unknown(read_conversation("codex", home, pid=123, fallback_to_recency=True))
    other = rollout(home, SECOND)
    (root / "fd/8").symlink_to(other)
    assert_unknown(read_conversation("codex", home, pid=123))
    (root / "fd/7").unlink()
    assert_unknown(read_conversation("codex", home, pid=123))
    assert_unknown(read_conversation("codex", home.parent / "unrelated-profile", pid=123))


@pytest.mark.parametrize("change,reason", [
    ("dead", "process_not_running"), ("user", "unrelated_user"),
    ("exe", "unrelated_process"), ("missing", "native_evidence_unavailable"),
    ("large", "evidence_limit"), ("boot", "process_identity_changed"),
])
def test_invalid_native_process_evidence(evidence, change, reason):
    home, root = evidence
    identity = read_conversation("codex", home, pid=123)["process_identity"]
    if change == "dead":
        (root / "stat").write_text((root / "stat").read_text().replace(") S", ") Z"))
    elif change == "user":
        (root / "status").write_text("Uid:\t99999\t99999\t99999\t99999\n")
    elif change == "exe":
        (root / "exe").unlink()
        (root / "exe").symlink_to(sys.executable)
    elif change == "missing":
        (root / "status").unlink()
    elif change == "large":
        (root / "status").write_text("x" * 8193)
    elif change == "boot":
        (native.PROC_ROOT / "sys/kernel/random/boot_id").write_text(SECOND)
    assert_unknown(read_conversation("codex", home, process_identity=identity), reason)


def test_unavailable_and_unsupported(evidence, monkeypatch):
    home, _ = evidence
    assert_unknown(read_conversation("codex", home, pid=456), "native_evidence_unavailable")
    assert_unknown(read_conversation("claude", home, pid=123), "unsupported_process_resolution")
    monkeypatch.setattr(native.sys, "platform", "darwin")
    assert_unknown(read_conversation("codex", home, pid=123), "unsupported_process_resolution")


@pytest.mark.parametrize("options", [{"pid": -1}, {"pid": True}, {"process_identity": "invalid"},
                                     {"pid": 123, "process_identity": "invalid"}])
def test_invalid_identity(evidence, options):
    assert_unknown(read_conversation("codex", evidence[0], **options), "invalid_process_identity")


@pytest.mark.parametrize("options", [{"limit": 0}, {"tail": 1001}, {"cursor": "opaque", "tail": 1},
                                     {"conversation_id": FIRST}, {"cwd": "/repo"}, {"started_at": "2026-11-07"}])
def test_page_validation_and_selection_conflicts(evidence, options):
    with pytest.raises(CdxError):
        read_conversation("codex", evidence[0], pid=123, **options)


def test_inaccessible_evidence_and_no_unrelated_reads(evidence, monkeypatch):
    real_read = native._bounded
    paths = []

    def bounded(path, *args, **kwargs):
        paths.append(path.name)
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(native, "_bounded", bounded)
    assert_unknown(read_conversation("codex", evidence[0], pid=123))
    assert paths == ["stat", "status", "boot_id"] * 2

    def denied(*args, **kwargs):
        raise PermissionError("private path must not escape")

    monkeypatch.setattr(native, "_bounded", denied)
    page = read_conversation("codex", evidence[0], pid=123)
    assert_unknown(page, "native_evidence_unavailable")
    assert "private path" not in json.dumps(page)


@pytest.mark.parametrize("options", [{"cursor": "opaque"}, {"before": "opaque"}])
def test_process_mode_never_replays_unbound_cursors(evidence, options):
    page = read_conversation("codex", evidence[0], pid=123, **options)
    assert_unknown(page)
    assert page["status"] == "reset_required"


def test_kernel_concurrent_process_identity_and_exit(tmp_path):
    # Actual kernel identities with controlled writers, not a Codex TUI claim.
    executable = tmp_path / "codex"
    shutil.copyfile(sys.executable, executable)
    executable.chmod(0o700)
    home = tmp_path / "home"
    path = rollout(home)
    script = "import sys; h=open(sys.argv[1], 'a'); print('ready', flush=True); sys.stdin.readline()"
    children = []
    try:
        for _ in range(2):
            child = subprocess.Popen([str(executable), "-c", script, str(path)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True)
            children.append(child)
            assert child.stdout.readline().strip() == "ready"
        pages = [read_conversation("codex", home, pid=child.pid) for child in children]
        for page in pages:
            assert_unknown(page)
        assert pages[0]["process_identity"] != pages[1]["process_identity"]
        children[0].stdin.write("exit\n")
        children[0].stdin.flush()
        children[0].wait(timeout=5)
        assert_unknown(read_conversation("codex", home, process_identity=pages[0]["process_identity"]),
                       "native_evidence_unavailable")
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
            child.stdin.close()
            child.stdout.close()
