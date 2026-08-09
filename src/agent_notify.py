"""Agent-event notifications: the hook target, and the per-session provisioning.

`cdx notify` is what a provider hook calls when an agent turn ends or blocks
waiting for input. It exists because the notification has to name *which* cdx
session, in *which* repository — the case the feature is for is several sessions
running in parallel — and only cdx knows the session name.

Provisioning writes the hook into the session's own home, which cdx already
owns because it sets HOME/CODEX_HOME per session at launch.
"""

import json
import os
import shutil

from .notify import notification_channel, send_desktop_notification

# Set on the provider process at launch; the hook runs as its child and inherits both.
SESSION_ENV = "CDX_SESSION_NAME"
ENABLED_ENV = "CDX_NOTIFY"

# Marks the entries cdx wrote, so revocation removes exactly those and leaves
# anything the user added by hand alone.
MARKER = "cdx-agent-notify"

_WAITING_EVENTS = {"notification", "permissionrequest", "userpromptsubmit"}


def resolve_hook_command(env=None):
    """Absolute path to cdx, not the bare name.

    Codex spawns the hook without a shell, and a Windows npm install ships a
    `.cmd` shim rather than an executable called `cdx`, so the bare name does
    not resolve there. pipx and uv installs can likewise leave cdx off the PATH
    the provider inherits.
    """
    env = env or os.environ
    return env.get("CDX_BIN") or shutil.which("cdx", path=env.get("PATH")) or "cdx"


def read_hook_payload(args, stdin_text=None):
    """Accept the payload however the provider hands it over.

    Claude Code and current Codex hooks write JSON to stdin. Codex's older
    `notify` key — which it now calls `legacy_notify` — passes it as an argv.
    Anything unparseable is an empty payload, never an error: a hook that fails
    loudly turns a missing notification into a broken agent turn.
    """
    for candidate in ([stdin_text] if stdin_text else []) + list(args or []):
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def compose_notification(payload, env=None, cwd=None):
    """Title and message for this event, or None if we should stay quiet."""
    env = env or os.environ
    if env.get(ENABLED_ENV) == "0":
        # Headless runs share the session's home, so they read the same hooks.
        # Their caller already learns of completion from the return value.
        return None
    session = env.get(SESSION_ENV)
    if not session:
        return None
    directory = payload.get("cwd") or payload.get("workspace") or cwd or os.getcwd()
    event = str(payload.get("hook_event_name") or payload.get("eventName") or payload.get("type") or "").lower()
    state = "waiting for you" if event.replace("_", "") in _WAITING_EVENTS else "finished"
    where = os.path.basename(str(directory).rstrip("/\\")) or directory
    return f"✓ {session}", f"{where} · {state}"


def handle_notify(rest, ctx):
    """Hook target. Never fails: a broken notification is not a broken turn."""
    try:
        stdin_text = None
        reader = ctx.get("stdin")
        if reader is not None and not ctx.get("stdin_is_tty"):
            stdin_text = reader.read()
        env = ctx.get("env") or os.environ
        composed = compose_notification(read_hook_payload(rest, stdin_text), env, ctx.get("cwd"))
        if composed:
            send_desktop_notification(*composed, spawn_sync=ctx.get("spawn_sync"), env=env)
    except Exception:  # noqa: BLE001 - deliberate: the caller is an agent turn
        pass
    return 0


def launch_notify_env(session, enabled, env=None):
    """Env the provider is launched with, carrying who we are and whether to notify."""
    values = {SESSION_ENV: session["name"]}
    if not enabled:
        values[ENABLED_ENV] = "0"
    return values


def notifications_enabled(session):
    """On unless this session was explicitly turned off."""
    launch = session.get("launch") or {}
    return launch.get("notify", "on") != "off"


def provision(auth_home, provider, enabled, env=None):
    """Install or remove cdx's hook entries in this session's own home.

    Idempotent, so an existing session picks the hooks up on its next launch and
    repeated launches change nothing. Returns True when entries were newly
    installed, so the caller can tell the user they need approving once.
    """
    env = env or os.environ
    if enabled and not notification_channel(env):
        # Nothing could be delivered on this host, so installing a hook would only
        # buy the user an approval prompt for a feature that shows nothing.
        enabled = False
    command = resolve_hook_command(env)
    if provider == "claude":
        return _provision_claude(auth_home, enabled, command)
    if provider == "codex":
        return _provision_codex(auth_home, enabled, command)
    return False


def _provision_claude(auth_home, enabled, command):
    path = os.path.join(auth_home, ".claude", "settings.json")
    settings = _read_json(path)
    if settings is None:
        return False
    hooks = settings.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    before = json.dumps(hooks, sort_keys=True)
    for event in ("Stop", "Notification"):
        entries = [entry for entry in hooks.get(event, []) if not _is_ours(entry)]
        if enabled:
            entries.append({
                "_source": MARKER,
                "hooks": [{"type": "command", "command": f"{command} notify"}],
            })
        if entries:
            hooks[event] = entries
        else:
            hooks.pop(event, None)
    if json.dumps(hooks, sort_keys=True) == before:
        return False
    settings["hooks"] = hooks
    return _write_json(path, settings) and enabled


def _provision_codex(auth_home, enabled, command):
    # CODEX_HOME is authHome itself, so the file sits at its root rather than
    # under a .codex segment.
    path = os.path.join(auth_home, "hooks.json")
    document = _read_json(path)
    if document is None:
        return False
    hooks = document.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    before = json.dumps(hooks, sort_keys=True)
    for event in ("Stop", "Notification"):
        entries = [entry for entry in hooks.get(event, []) if not _is_ours(entry)]
        if enabled:
            entries.append({
                "_source": MARKER,
                "hooks": [{"type": "command", "command": f"{command} notify"}],
            })
        if entries:
            hooks[event] = entries
        else:
            hooks.pop(event, None)
    if json.dumps(hooks, sort_keys=True) == before:
        return False
    document["hooks"] = hooks
    return _write_json(path, document) and enabled


def _is_ours(entry):
    return isinstance(entry, dict) and entry.get("_source") == MARKER


def _read_json(path):
    """Existing content, {} when absent, or None when we must not touch it.

    An unparseable file is someone else's, so we leave it exactly as it is
    rather than replacing settings the user cares about.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _write_json(path, document):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
    except OSError:
        # An unwritable home is a skipped provisioning step, not a failed launch.
        return False
    return True
