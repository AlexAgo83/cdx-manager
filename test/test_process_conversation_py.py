"""Resolve exact open native rollouts and fail closed on unsafe evidence."""

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
    with path.open("a") as handle:
        handle.write(json.dumps({"type": "response_item", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": identifier}]}}) + "\n")
    return path


def open_rollout(root, path, descriptor="7", flags="0102001"):
    (root / "fd" / descriptor).symlink_to(path)
    (root / "fdinfo" / descriptor).write_text(f"flags:\t{flags}\n")


def assert_resolved(page, identifier=FIRST):
    assert page["status"] == "ok" and page["reason"] is None
    assert page["resolution_status"] == "resolved"
    assert page["resolution_method"] == "process_open_rollout"
    assert page["conversation_id"] == identifier
    assert [entry["text"] for entry in page["entries"]] == [identifier]
    assert page["resolution_scope"] is None and page["next_cursor"] is None


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    proc = tmp_path / "proc"
    root = proc / "123"
    root.mkdir(parents=True)
    (root / "fd").mkdir()
    (root / "fdinfo").mkdir()
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


def test_open_rollout_ambiguity_switch_and_wrong_profile(evidence):
    home, root = evidence
    path = rollout(home)
    open_rollout(root, path)
    first = read_conversation("codex", home, pid=123, fallback_to_recency=True, tail=1)
    assert_resolved(first)
    other = rollout(home, SECOND)
    open_rollout(root, other, "8")
    assert_unknown(read_conversation("codex", home, pid=123), "ambiguous_native_rollouts")
    (root / "fd/7").unlink()
    assert_resolved(read_conversation("codex", home, process_identity=first["process_identity"]), SECOND)
    assert_unknown(read_conversation("codex", home.parent / "unrelated-profile", pid=123), "profile_boundary_mismatch")


def test_duplicate_descriptors_readonly_and_unopened_rollouts(evidence):
    home, root = evidence
    path = rollout(home)
    open_rollout(root, path)
    open_rollout(root, path, "8")
    open_rollout(root, rollout(home, SECOND), "9", "0100000")
    assert_resolved(read_conversation("codex", home, pid=123))
    (root / "fd/7").unlink()
    (root / "fd/8").unlink()
    assert_unknown(read_conversation("codex", home, pid=123, fallback_to_recency=True))


@pytest.mark.parametrize("change,reason", [
    ("id", "invalid_native_rollout"), ("source", "invalid_native_rollout"),
    ("partial", "invalid_native_rollout"), ("large", "evidence_limit"),
    ("malformed", "native_evidence_unavailable"), ("deleted", "invalid_native_rollout"),
])
def test_invalid_rollout_metadata(evidence, change, reason):
    home, root = evidence
    path = rollout(home)
    if change == "id":
        path.write_text(path.read_text().replace(FIRST, SECOND))
    elif change == "source":
        path.write_text(path.read_text().replace('"cli"', '"exec"'))
    elif change == "partial":
        path.write_text('{"type": "session_meta"')
    elif change == "large":
        path.write_text("x" * 65537 + "\n")
    elif change == "malformed":
        path.write_text("not json\n")
    elif change == "deleted":
        deleted = path.with_name(path.name + " (deleted)")
        path.rename(deleted)
        path = deleted
    open_rollout(root, path)
    assert_unknown(read_conversation("codex", home, pid=123), reason)


def test_profile_symlink_escape(evidence):
    home, root = evidence
    foreign = home.parent / "foreign"
    path = rollout(foreign)
    (home / "sessions/escape").symlink_to(foreign / "sessions", target_is_directory=True)
    open_rollout(root, home / "sessions/escape/2026" / path.name)
    assert_unknown(read_conversation("codex", home, pid=123), "profile_boundary_mismatch")


@pytest.mark.parametrize("change", ["switch", "exit", "reuse", "replacement"])
def test_evidence_rechecked_after_read(evidence, monkeypatch, change):
    from src import conversation

    home, root = evidence
    path = rollout(home)
    open_rollout(root, path)
    original = conversation._read_conversation_page

    def changing(*args, **kwargs):
        page = original(*args, **kwargs)
        if change == "switch":
            (root / "fd/7").unlink()
            open_rollout(root, rollout(home, SECOND))
        elif change == "exit":
            (root / "stat").unlink()
        elif change == "reuse":
            (root / "stat").write_text((root / "stat").read_text().replace("100", "101"))
        else:
            path.rename(path.with_suffix(".old"))
            rollout(home)
        return page

    monkeypatch.setattr(conversation, "_read_conversation_page", changing)
    page = read_conversation("codex", home, pid=123)
    assert page["resolution_status"] == "unknown" and page["reason"]
    assert page["entries"] == [] and page["conversation_id"] is None


def test_no_descendant_or_transcript_search(evidence, monkeypatch):
    from src import conversation

    home, root = evidence
    (root / "task/123").mkdir(parents=True)
    (root / "task/123/children").write_text("456")
    child = root.parent / "456"
    (child / "fd").mkdir(parents=True)
    (child / "fd/7").symlink_to(rollout(home))

    def forbidden(*args, **kwargs):
        pytest.fail("process mode must never search transcripts")

    monkeypatch.setattr(conversation, "conversation_transcript", forbidden)
    monkeypatch.setattr(conversation, "resolve_transcript", forbidden)
    assert_unknown(read_conversation("codex", home, pid=123, fallback_to_recency=True))
    open_rollout(root, rollout(home))
    assert_resolved(read_conversation("codex", home, pid=123))


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
    assert paths == ["stat", "status", "boot_id"]

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
            assert_resolved(page)
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


def test_foreign_profile_evidence_is_never_read(evidence):
    home, root = evidence
    path = rollout(home.parent / "other-profile")
    path.write_text("x" * 65537)
    open_rollout(root, path)
    assert_unknown(read_conversation("codex", home, pid=123), "profile_boundary_mismatch")


def test_descriptor_evidence_limit(evidence):
    home, root = evidence
    for number in range(513):
        (root / "fd" / str(number)).symlink_to("/dev/null")
    assert_unknown(read_conversation("codex", home, pid=123), "evidence_limit")


def test_process_read_never_consults_cwd(evidence, monkeypatch):
    home, root = evidence
    open_rollout(root, rollout(home))

    def forbidden():
        pytest.fail("process mode must not consult the working directory")

    monkeypatch.setattr(os, "getcwd", forbidden)
    assert_resolved(read_conversation("codex", home, pid=123))


@pytest.mark.parametrize("options", [{"cursor": "opaque"}, {"before": "opaque"}])
def test_resolved_process_rejects_unbound_cursors(evidence, options):
    home, root = evidence
    open_rollout(root, rollout(home))
    page = read_conversation("codex", home, pid=123, **options)
    assert page["status"] == "reset_required" and page["entries"] == []
    assert page["next_cursor"] is None


def test_exact_file_inode_is_checked_before_read(evidence, monkeypatch):
    from src import conversation

    home, root = evidence
    path = rollout(home)
    open_rollout(root, path)
    original = conversation._read_conversation_page

    def replaced(*args, **kwargs):
        retained = path.with_suffix(".retained")
        path.rename(retained)
        rollout(home)
        try:
            return original(*args, **kwargs)
        finally:
            path.unlink()
            retained.rename(path)

    monkeypatch.setattr(conversation, "_read_conversation_page", replaced)
    assert_unknown(read_conversation("codex", home, pid=123), "evidence_changed")


# Context Codex injects ahead of the first turn, shaped like real rollouts.
CODEX_CONTEXT = [json.dumps({"type": "response_item", "payload": {"type": "message", "role": role, "content": [
    {"type": "input_text", "text": text} for text in texts]}}) for role, texts in (
    ("developer", ["You are Codex.", "<permissions instructions>sandbox</permissions instructions>"]),
    ("user", ["# AGENTS.md instructions for /repo\n\n<INSTRUCTIONS>\nbe brief\n</INSTRUCTIONS>",
              "<environment_context>\n  <cwd>/repo</cwd>\n</environment_context>"]),
)]


def remote_session(tmp_path, home, root, *, launcher=99, source="vscode"):
    """A remote-controlled launch: TUI 123 holds no rollout, app-server 124 writes it."""
    server = root.parent / "124"
    shutil.copytree(root, server, symlinks=True, ignore=shutil.ignore_patterns("fd", "fdinfo"))
    (server / "fd").mkdir()
    (server / "fdinfo").mkdir()
    for process in (root, server):
        name, rest = (process / "stat").read_text().rsplit(")", 1)
        values = rest.split()
        values[1] = str(launcher)
        (process / "stat").write_text(name + ") " + " ".join(values))
    path = rollout(home, SECOND)
    meta = json.loads(path.read_text().splitlines()[0])
    meta["payload"]["source"] = source
    lines = path.read_text().splitlines()
    path.write_text("\n".join([json.dumps(meta), *CODEX_CONTEXT, *lines[1:]]) + "\n")
    open_rollout(server, path)
    endpoint = tmp_path / "work.endpoint.json"
    endpoint.write_text(json.dumps({"port": 1, "secret": "s", "pid": launcher, "tui_pid": 123, "server_pid": 124}))
    return endpoint


def test_remote_controlled_tui_resolves_through_its_app_server(tmp_path, evidence):
    home, root = evidence
    endpoint = remote_session(tmp_path, home, root)
    # Without the session's endpoint the TUI holds no rollout and the app-server's
    # rollout is not a TUI one: both stay refused.
    assert_unknown(read_conversation("codex", home, pid=123, tail=1))
    assert_unknown(read_conversation("codex", home, pid=124, tail=1), "invalid_native_rollout")
    page = read_conversation("codex", home, pid=123, remote_endpoint=endpoint)
    assert page["status"] == "ok" and page["conversation_id"] == SECOND
    assert page["resolution_method"] == "app_server_open_rollout"
    assert [entry["text"] for entry in page["entries"]] == [SECOND]
    assert page["process_identity"].startswith("linux:123:")
    again = read_conversation("codex", home, process_identity=page["process_identity"], remote_endpoint=endpoint)
    assert again["conversation_id"] == SECOND


@pytest.mark.parametrize("change, reason", [
    (lambda endpoint, root: endpoint.write_text(json.dumps({"pid": 99, "tui_pid": 555, "server_pid": 124})),
     "native_conversation_identity_unavailable"),
    (lambda endpoint, root: endpoint.unlink(), "native_conversation_identity_unavailable"),
    (lambda endpoint, root: endpoint.write_text("{"), "native_evidence_unavailable"),
    (lambda endpoint, root: endpoint.write_text(json.dumps({"pid": 98, "tui_pid": 123, "server_pid": 124})),
     "unrelated_process"),
    (lambda endpoint, root: (root.parent / "124" / "exe").unlink() or (root.parent / "124" / "exe").symlink_to("/bin/sh"),
     "unrelated_process"),
])
def test_remote_mapping_fails_closed(tmp_path, evidence, change, reason):
    home, root = evidence
    endpoint = remote_session(tmp_path, home, root)
    change(endpoint, root)
    assert_unknown(read_conversation("codex", home, pid=123, remote_endpoint=endpoint), reason)


def test_app_server_rollout_source_is_still_checked(tmp_path, evidence):
    home, root = evidence
    endpoint = remote_session(tmp_path, home, root, source="exec")
    assert_unknown(read_conversation("codex", home, pid=123, remote_endpoint=endpoint), "invalid_native_rollout")
