"""Read-only input validation and the shared local/worker mount boundary."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import workspace_sandbox
from src.cli_args import _parse_run_args
from src.commands.runs import _detached_child_argv
from src.errors import CdxError
from src.remote_run import worker_input

BASE = ["work", "--cwd", "/tmp/example-worktree", "--prompt", "Work", "--isolate-workspace", "--json"]


def test_repeated_inputs_survive_detached_reexec(tmp_path):
    first, second = str(tmp_path / "example-input"), str(tmp_path / "example-other-input")
    parsed = _parse_run_args([*BASE, "--ro-input", "EXAMPLE_ROOT=" + first,
                              "--ro-input=EXAMPLE_OTHER=" + second])
    assert parsed["ro_inputs"] == {"EXAMPLE_ROOT": first, "EXAMPLE_OTHER": second}
    child = _parse_run_args(_detached_child_argv(parsed, "/tmp/example-prompt", "work", parsed["cwd"])[1:])
    assert child["ro_inputs"] == parsed["ro_inputs"]


@pytest.mark.parametrize("value", ["example=/tmp/example-input", "_EXAMPLE=/tmp/example-input",
                                  "1EXAMPLE=/tmp/example-input", "EXAMPLE-ROOT=/tmp/example-input",
                                  "EXAMPLE_ROOT", "EXAMPLE_ROOT=", "EXAMPLE_ROOT=/tmp/example\x00input"])
def test_invalid_input_name_or_assignment(value):
    with pytest.raises(CdxError, match="--ro-input"):
        _parse_run_args([*BASE, "--ro-input", value])


@pytest.mark.parametrize("name", ["HOME", "PATH", "CI", "CDX_HOME", "CODEX_HOME", "GIT_WORK_TREE", "RTK_DB_PATH",
                                 "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
                                 "AWS_PROFILE", "AZURE_CLIENT_SECRET", "GH_TOKEN", "PYTHONPATH", "LANG", "LC_ALL", "TERM", "TZ"])
def test_reserved_input_name(name):
    with pytest.raises(CdxError, match="reserved"):
        _parse_run_args([*BASE, "--ro-input", name + "=/tmp/example-input"])


def test_duplicate_names_and_nonisolated_inputs_are_refused():
    with pytest.raises(CdxError, match="repeats"):
        _parse_run_args([*BASE, "--ro-input", "EXAMPLE_ROOT=/tmp/example-input",
                         "--ro-input", "EXAMPLE_ROOT=/tmp/example-other-input"])
    with pytest.raises(CdxError, match="requires --isolate-workspace"):
        _parse_run_args([arg for arg in BASE if arg != "--isolate-workspace"] +
                        ["--ro-input", "EXAMPLE_ROOT=/tmp/example-input"])


@pytest.fixture(params=["local", "shipped-worker"])
def sandbox(request):
    if request.param == "local":
        return workspace_sandbox
    namespace = {"__name__": "input_worker"}
    exec(json.loads(worker_input()), namespace)
    module = {"__name__": "input_sandbox"}
    exec(namespace["SANDBOX_SOURCE"], module)
    return SimpleNamespace(**module)


@pytest.mark.skipif(os.name == "nt", reason="Linux sandbox ownership")
@pytest.mark.parametrize("writable", [False, True])
def test_inputs_are_always_read_only_and_internal_symlinks_are_untouched(tmp_path, monkeypatch, sandbox, writable):
    tree, inputs, other = (tmp_path / name for name in ("tree", "inputs", "other"))
    tree.mkdir()
    inputs.mkdir()
    other.mkdir()
    (inputs / "link").symlink_to("/tmp/example-unavailable")
    monkeypatch.setitem(sandbox.sandbox_command.__globals__, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(workspace_sandbox.shutil, "which", lambda name, path=None: "/usr/bin/" + name)
    args, env = sandbox.sandbox_command(["true"], tree, network=False, writable=writable,
                                       ro_inputs={"EXAMPLE_ROOT": str(inputs), "EXAMPLE_OTHER": str(other)}, source={})
    destination = args.index("/opt/inputs/example_root")
    assert args[destination - 2:destination] == ["--ro-bind", str(inputs)]
    assert env["EXAMPLE_ROOT"] == "/opt/inputs/example_root"
    destination = args.index("/opt/inputs/example_other")
    assert args[destination - 2:destination] == ["--ro-bind", str(other)]
    assert env["EXAMPLE_OTHER"] == "/opt/inputs/example_other"
    assert (inputs / "link").is_symlink()
    assert os.readlink(inputs / "link") == "/tmp/example-unavailable"


@pytest.mark.skipif(os.name == "nt", reason="Linux sandbox ownership")
@pytest.mark.parametrize("condition", ["missing", "file", "symlink", "dangling", "owner", "tree", "tree-child",
                                       "tree-parent", "state", "state-child", "state-parent", "config", "home",
                                       "credential", "credential-parent", "credential-env", "alias", "runtime"])
def test_invalid_input_directory(tmp_path, monkeypatch, sandbox, condition):
    tree, inputs, state, home = (tmp_path / name for name in ("tree", "inputs", "state", "home"))
    for path in (tree, inputs, state, home):
        path.mkdir()
    config = home / ".config"
    config.mkdir()
    credential = tmp_path / "credential" / "login.json"
    credential.parent.mkdir()
    credential.write_text("fake-credential")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    source = {"CDX_HOME": str(state)}
    path = inputs
    if condition == "missing":
        path = tmp_path / "missing"
    elif condition == "file":
        path = credential
    elif condition in ("symlink", "dangling", "alias"):
        path = tmp_path / "link"
        path.symlink_to(config if condition == "alias" else inputs if condition == "symlink" else tmp_path / "missing")
    elif condition == "owner":
        monkeypatch.setattr(os, "getuid", lambda: inputs.stat().st_uid + 1)
    elif condition == "tree":
        path = tree
    elif condition == "tree-child":
        path = tree / "child"
        path.mkdir()
    elif condition in ("tree-parent", "state-parent"):
        path = tmp_path
    elif condition == "state":
        path = state
    elif condition == "state-child":
        path = state / "child"
        path.mkdir()
    elif condition == "runtime":
        path = Path("/proc")
    elif condition == "config":
        path = config
    elif condition == "home":
        path = home
    elif condition == "credential":
        path = credential
    elif condition == "credential-parent":
        path = credential.parent
    elif condition == "credential-env":
        source["GOOGLE_APPLICATION_CREDENTIALS"] = str(inputs / "login.json")
    with pytest.raises(RuntimeError, match="--ro-input"):
        sandbox.validate_ro_inputs({"EXAMPLE_ROOT": str(path)}, tree, source=source, protected_paths=(str(credential),))
