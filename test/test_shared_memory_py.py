"""Claude auto-memory shared across the profiles that opt in."""

import os

import pytest

from src import shared_memory

pytestmark = pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")


def _memory(home, cwd):
    return home / ".claude" / "projects" / shared_memory.claude_project_name(str(cwd)) / "memory"


@pytest.fixture
def layout(tmp_path):
    cwd = tmp_path / "repo"
    cwd.mkdir()
    return tmp_path / "cdx", tmp_path / "a", tmp_path / "b", cwd


def test_project_name_matches_claude_code_folders():
    assert shared_memory.claude_project_name("/Users/me/Documents/remote-ops") == "-Users-me-Documents-remote-ops"


def test_two_profiles_end_up_on_one_store_and_nothing_is_deleted(layout):
    base, a, b, cwd = layout
    old = _memory(a, cwd)
    old.mkdir(parents=True)
    (old / "MEMORY.md").write_text("- [A](a.md) — from a\n")
    (old / "a.md").write_text("fact a\n")

    assert shared_memory.link(str(a), str(base), str(cwd), now=0) == ("linked", str(old))
    assert shared_memory.link(str(b), str(base), str(cwd)) == ("linked", str(_memory(b, cwd)))
    assert (_memory(b, cwd) / "a.md").read_text() == "fact a\n"
    (_memory(b, cwd) / "b.md").write_text("fact b\n")
    assert (old / "b.md").read_text() == "fact b\n"
    assert (old.parent / "memory.pre-cdx-19700101T000000" / "a.md").read_text() == "fact a\n"
    assert shared_memory.link(str(a), str(base), str(cwd))[0] == "linked"


def test_indexes_merge_and_identical_files_are_not_conflicts(layout):
    base, a, b, cwd = layout
    for home, extra in ((a, "- [A](a.md) — a\n"), (b, "- [B](b.md) — b\n")):
        memory = _memory(home, cwd)
        memory.mkdir(parents=True)
        (memory / "MEMORY.md").write_text("- [S](s.md) — shared\n" + extra)
        (memory / "s.md").write_text("same\n")
    shared_memory.link(str(a), str(base), str(cwd))
    assert shared_memory.link(str(b), str(base), str(cwd))[0] == "linked"
    assert (_memory(a, cwd) / "MEMORY.md").read_text().splitlines() == [
        "- [S](s.md) — shared", "- [A](a.md) — a", "- [B](b.md) — b"]


def test_a_conflicting_file_leaves_the_profile_untouched(layout):
    base, a, b, cwd = layout
    for home, text in ((a, "one\n"), (b, "two\n")):
        memory = _memory(home, cwd)
        memory.mkdir(parents=True)
        (memory / "x.md").write_text(text)
    shared_memory.link(str(a), str(base), str(cwd))
    assert shared_memory.link(str(b), str(base), str(cwd)) == ("conflict", ["x.md"])
    assert not os.path.islink(_memory(b, cwd))
    assert (_memory(b, cwd) / "x.md").read_text() == "two\n"


def test_a_link_cdx_did_not_make_is_left_alone(layout):
    base, a, _b, cwd = layout
    elsewhere = layout[0].parent / "elsewhere"
    elsewhere.mkdir()
    memory = _memory(a, cwd)
    memory.parent.mkdir(parents=True)
    os.symlink(elsewhere, memory)
    assert shared_memory.link(str(a), str(base), str(cwd))[0] == "skipped"
    assert os.path.realpath(memory) == str(elsewhere.resolve())
