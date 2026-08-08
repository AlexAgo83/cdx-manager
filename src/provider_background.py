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
import subprocess

from .config import PROVIDER_CLAUDE

BACKGROUND_PATH_PROVIDER = "provider_native"
BACKGROUND_PATH_CDX = "cdx_detached"

_CAPABILITY_PROBE_TIMEOUT_SECONDS = 10

# `claude agents --json` reports these; anything else is treated as still
# running, because ending a run early is worse than reporting it late.
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "canceled", "error"}


EXPERIMENTAL_ENV = "CDX_EXPERIMENTAL_NATIVE_BG"


def supports_native_background(provider, env=None, spawn_sync=None):
    """Whether the installed provider CLI can run and report background agents.

    Off unless `CDX_EXPERIMENTAL_NATIVE_BG=1`, because a live trial against
    Claude Code 2.1.226 broke three assumptions this module was built on:

    1. `--session-id` is not honoured under `--bg`. cdx asked for
       `6e8e9e0b-...` and the agent came back as `373c3949-...`, so looking the
       agent up by the id cdx requested finds nothing.
    2. The `pid` in `claude agents --json` is not the run. It pointed at a
       `claude bg-spare` daemon helper, and became `null` a minute later, so it
       cannot drive `_refresh_stale_runs`.
    3. `status` can be absent entirely (`null`), alongside an undocumented
       `state: "blocked"`, so terminal detection has nothing dependable to read.

    Consequence when it was enabled: the agent started, cdx failed to identify
    it, fell back to the in-house launcher, and the same task ran twice - once
    untracked. Duplicate execution on a user's account is worse than not
    delegating at all, so the default is off until the surface is understood.

    Both halves are still required when opted in: starting an agent cdx cannot
    observe would leave runs stuck at "running" forever.
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


def find_agent(agents, session_id):
    for agent in agents:
        if isinstance(agent, dict) and agent.get("sessionId") == session_id:
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
    status = str(agent.get("status") or "").strip().lower()
    if status not in _TERMINAL_STATUSES:
        return None
    return "succeeded" if status == "completed" else "failed"
