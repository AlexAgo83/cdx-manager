"""What each cdx session's agent is doing right now, kept from its hook events.

`cdx notify` hears every hook event and used to forget it once the alert was
out. Here the same event also rewrites one small record per session, so a
dashboard, a chat agent or a terminal board can ask `cdx agents --json` which
sessions are working, waiting for their user, done, failed or out of quota
without parsing transcripts or terminals.

One file per session rather than one shared file: two sessions finishing in
the same instant then never race over a single document.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from .errors import CdxError
from .fs_utils import atomic_write
from .run_failover import _mentions_exhaustion, status_confirms_exhaustion
from .session_helpers import _process_is_running

AGENTS_USAGE = "Usage: cdx agents [--max-age-hours N] [--json]"
DEFAULT_MAX_AGE_HOURS = 24
# Set on the provider at launch: the cdx process that waits on it. The hook is
# a grandchild at best (Claude Code runs it through a shell), so its own parent
# is no proof the agent is alive; the launcher is.
PID_ENV = "CDX_AGENT_PID"
_PROMPT_LIMIT = 120
_WAITING_NOTIFICATIONS = {"", "idle_prompt", "agent_needs_input", "permission_prompt"}


def agent_state_enabled(session):
    """Whether this session asked for its hooks to keep state, alerts or not."""
    return ((session or {}).get("launch") or {}).get("agent_state") is True


def state_dir(base_dir):
    return os.path.join(base_dir, "state", "agents")


def classify(payload, event, error_class):
    """(state, reason) for this event, or None when it changes nothing."""
    if event == "userpromptsubmit":
        return "working", None
    if event == "permissionrequest":
        tool = payload.get("tool_name")
        return "waiting", f"permission ({tool})" if isinstance(tool, str) and tool else "permission"
    if event == "notification":
        kind = str(payload.get("notification_type") or "").lower()
        return ("waiting", kind or "notification") if kind in _WAITING_NOTIFICATIONS else None
    if event in ("stop", "agentturncomplete"):
        return "done", None
    if event == "stopfailure":
        return "failed", error_class or "turn failed"
    return None


def confirmed_limit(ctx, name, payload, error_class):
    """The status row proving a usage limit, or None.

    The run_failover rule, both halves: the provider has to call the failure
    exhaustion in its own words, and the account's own status has to agree. A
    turn that merely failed, or an account whose status cannot be read, stays
    `failed`; marking a healthy session `limit` would send someone to wait out a
    reset that is not coming.
    """
    message = payload.get("error_message")
    if not _mentions_exhaustion([error_class] + ([message] if isinstance(message, str) else [])):
        return None
    # Imported here: commands sit above this module, and the refresh-then-cache
    # read is theirs to own.
    from .commands.runs import _status_row_for
    row = _status_row_for(ctx, name)
    return row if status_confirms_exhaustion(row) else None


def record(ctx, name, payload, event, error_class, cwd, env, prompt=None):
    """Rewrite this session's record for one hook event. Writes nothing to stdout."""
    base_dir = (ctx.get("service") or {}).get("base_dir")
    # The name comes from the environment; it must stay a plain file name.
    if not base_dir or not name or os.path.basename(name) != name or name in (".", ".."):
        return None
    classified = classify(payload, event, error_class)
    if not classified:
        return None
    state, reason = classified
    path = os.path.join(state_dir(base_dir), f"{name}.json")
    current = _read(path) or {}
    if state == "working":
        # Only under the preview opt-in, like any other free text a hook carries.
        current["prompt"] = prompt or None
    current.setdefault("prompt", None)
    reset_at = None
    if state == "failed":
        row = confirmed_limit(ctx, name, payload, error_class)
        if row is not None:
            state, reset_at = "limit", row.get("reset_at")
    provider = current.get("provider")
    get_session = (ctx.get("service") or {}).get("get_session")
    if get_session:
        provider = (get_session(name) or {}).get("provider") or provider
    pid = env.get(PID_ENV)
    current.update({
        "session": name,
        "provider": provider,
        "cwd": str(cwd),
        "project": os.path.basename(str(cwd).rstrip("/\\")) or str(cwd),
        "state": state,
        "reason": reason,
        "reset_at": reset_at,
        "pid": int(pid) if pid and pid.isdigit() else current.get("pid"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    atomic_write(path, json.dumps(current, indent=2) + "\n", mode=0o600)
    return current


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def list_agents(base_dir, max_age_hours=DEFAULT_MAX_AGE_HOURS, now=None, is_running=_process_is_running):
    """Live records, waiting first then newest; stale ones are deleted on the way."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    directory = state_dir(base_dir)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    agents = []
    for file_name in names:
        if not file_name.endswith(".json"):
            continue
        path = os.path.join(directory, file_name)
        entry = _read(path)
        try:
            updated = datetime.fromisoformat(entry["updated_at"])
        except (TypeError, KeyError, ValueError):
            updated = None
        if updated is None or updated.tzinfo is None or updated < cutoff:
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        if entry.get("pid") and not is_running(entry["pid"]):
            entry["last_state"], entry["state"] = entry.get("state"), "ended"
        agents.append(entry)
    agents.sort(key=lambda entry: entry["updated_at"], reverse=True)
    agents.sort(key=lambda entry: entry.get("state") != "waiting")
    return agents


def handle_agents(rest, ctx):
    # Imported here: this module is loaded by the hook path through
    # agent_notify, and the CLI helpers import provider_runtime, which imports
    # agent_notify back.
    from .cli_args import _parse_flag_args
    from .cli_helpers import _json_success, _write_json
    from .cli_render import _pad_table

    parsed = _parse_flag_args(rest, {
        "--max-age-hours": {"key": "max_age_hours", "type": "str", "default": None},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, AGENTS_USAGE)
    max_age = DEFAULT_MAX_AGE_HOURS
    if parsed["max_age_hours"] is not None:
        try:
            max_age = int(parsed["max_age_hours"])
        except ValueError:
            max_age = 0
        if max_age < 1:
            raise CdxError(AGENTS_USAGE)
    agents = list_agents(ctx["service"]["base_dir"], max_age)
    if parsed["json"]:
        _write_json(ctx, _json_success("agents", "Agents loaded.", agents=agents, max_age_hours=max_age))
        return 0
    if not agents:
        ctx["out"]("No agent state recorded. Turn it on with: cdx set <name> --agent-state on\n")
        return 0
    rows = [["SESSION", "STATE", "PROJECT", "REASON", "UPDATED"]]
    for entry in agents:
        rows.append([
            entry.get("session") or "",
            entry.get("state") or "",
            entry.get("project") or "",
            entry.get("reason") or "",
            entry.get("updated_at") or "",
        ])
    ctx["out"](_pad_table(rows) + "\n")
    return 0
