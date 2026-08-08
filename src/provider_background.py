"""Delegating detached runs to a provider's own background agents.

cdx has always detached runs itself: fork the child into its own session, keep
its pid, sweep the record when that pid dies. Claude Code now ships the same
thing natively - `--bg` starts a background agent and `claude agents --json`
lists them - so on that provider cdx can stop owning the mechanism and own the
routing instead, which is the part no provider will do.

Two deliberate limits:

Claude only. codex-cli exposes `cloud` and `exec-server`, both marked
EXPERIMENTAL in its own --help. Trading a working in-house path for a surface
the provider may change without notice is a bad trade, so Codex keeps the
in-house launcher until that surface settles.

Capability, never version. The installed CLI is asked what it supports, the
same way `cdx doctor --check-provider-flags` already does, because a version
comparison goes stale the moment either side ships.
"""

import json
import os
import re
import subprocess

from .config import PROVIDER_CLAUDE

BACKGROUND_PATH_PROVIDER = "provider_native"
BACKGROUND_PATH_CDX = "cdx_detached"

_CAPABILITY_PROBE_TIMEOUT_SECONDS = 10

# Observed on Claude Code 2.1.226 by watching one agent from launch to finish:
# completion is carried by `state`, not by `status`. `status` alternates
# idle/busy - it describes activity, not outcome - and an agent waiting on
# something sits at `state: "blocked"` with `status: "idle"`, which reads
# exactly like a finished one if you look at `status`.
_TERMINAL_STATES = {"done", "failed", "cancelled", "canceled", "error", "stopped"}
_SUCCESS_STATE = "done"

# `claude --bg` prints `backgrounded · <id>` on stdout. That is the authoritative
# handle: the provider assigns the id itself and ignores --session-id, so this
# line is the only thing that reliably names the agent just started.
_BACKGROUNDED = re.compile(r"backgrounded\s*[^\w]?\s*([0-9a-fA-F]{6,})")


def parse_backgrounded_id(output):
    """The agent id `claude --bg` reported, or None."""
    if not output:
        return None
    match = _BACKGROUNDED.search(output)
    return match.group(1) if match else None


EXPERIMENTAL_ENV = "CDX_EXPERIMENTAL_NATIVE_BG"


def supports_native_background(provider, env=None, spawn_sync=None):
    """Whether the installed provider CLI can run and report background agents.

    Off unless `CDX_EXPERIMENTAL_NATIVE_BG=1`. Two live trials against Claude
    Code 2.1.226 fixed the identification problems and exposed a deeper one.

    Fixed: the provider assigns its own id and ignores `--session-id`, so the
    agent is now named from the `backgrounded - <id>` line `--bg` prints, and
    completion is read from `state` rather than `status` (which alternates
    idle/busy and says nothing about outcome).

    Not fixed, and the reason this stays off:

    1. A delegated run cannot honour the `cdx run --json` contract. The
       in-house path runs `claude --print --output-format json` and gets a
       structured result, token usage, and a final payload. `--bg` runs the
       interactive TUI; `claude logs <id>` returns an ANSI screen dump. So
       usage accounting, the final payload, and the rate-limit classification
       that `--failover` depends on all have no source.
    2. Nothing yet drives a delegated run to a terminal status. `agent_terminal_status`
       exists but no caller consults the provider, so the record relies on pid
       liveness and a blocked agent reads as running indefinitely.
    3. cdx's own launch spec makes the agent block. A hand-run
       `claude --bg --permission-mode bypassPermissions "..."` reaches
       `state: done`; the same task launched through cdx sits at
       `state: blocked`, most likely because the spec passes a `--session-id`
       that already exists.

    Delegation therefore needs its own request, not a flag flip.
    """
    if provider != PROVIDER_CLAUDE:
        return False
    environment = env if env is not None else os.environ
    if str(environment.get(EXPERIMENTAL_ENV, "")).strip() not in ("1", "true", "on", "yes"):
        return False
    runner = spawn_sync or _default_spawn_sync
    try:
        help_text = runner(["claude", "--help"], env=env)
        agents_help = runner(["claude", "agents", "--help"], env=env)
    except (OSError, subprocess.SubprocessError):
        return False
    if help_text is None or agents_help is None:
        return False
    return "--bg" in help_text and "--json" in agents_help


def _default_spawn_sync(argv, env=None):
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_CAPABILITY_PROBE_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{completed.stdout or ''}{completed.stderr or ''}"


def list_background_agents(env=None, cwd=None, spawn_sync=None):
    """Every background agent the provider knows about, completed ones included.

    Returns [] rather than raising for any failure: this feeds a status refresh
    that must never take down the command that asked for it.
    """
    runner = spawn_sync or _default_spawn_sync
    argv = ["claude", "agents", "--json", "--all"]
    if cwd:
        argv += ["--cwd", cwd]
    output = runner(argv, env=env)
    if not output:
        return []
    start = output.find("[")
    if start < 0:
        return []
    try:
        agents = json.loads(output[start:])
    except ValueError:
        return []
    return agents if isinstance(agents, list) else []


def find_agent(agents, identifier):
    """The agent with this id, matching either the short id or the session id."""
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        if identifier in (agent.get("id"), agent.get("sessionId")):
            return agent
    return None


def agent_terminal_status(agent):
    """The cdx run status a provider agent maps to, or None while it runs.

    An agent the provider no longer lists has finished in a way cdx cannot
    name, so it reports `failed` rather than `succeeded`: claiming success for
    a run whose outcome was never observed is the one answer that must not be
    guessed.
    """
    if agent is None:
        return "failed"
    state = str(agent.get("state") or "").strip().lower()
    if state not in _TERMINAL_STATES:
        return None
    return "succeeded" if state == _SUCCESS_STATE else "failed"
