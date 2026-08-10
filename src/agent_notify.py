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
import subprocess

from .notify import notification_channel, send_desktop_notification

# Set on the provider process at launch; the hook runs as its child and inherits both.
SESSION_ENV = "CDX_SESSION_NAME"
ENABLED_ENV = "CDX_NOTIFY"
PREVIEW_ENV = "CDX_NOTIFY_PREVIEW"

# Our entries are recognised by the command they run, not by a marker key of our
# own: both providers validate this file against their own schema, and an extra
# key they do not know is a rejection risk for no gain.
HOOK_ARG = "notify"

_WAITING_EVENTS = {"notification", "permissionrequest"}
_PREVIEW_LIMIT = 180
_TOOL_NAME_LIMIT = 80


def supports_agent_alerts(provider):
    """Whether cdx can provision provider hooks for this session."""
    return provider in {"claude", "codex"}


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
    env = os.environ if env is None else env
    if env.get(ENABLED_ENV) == "0":
        # Headless runs share the session's home, so they read the same hooks.
        # Their caller already learns of completion from the return value.
        return None
    session = env.get(SESSION_ENV)
    if not session:
        return None
    directory = payload.get("cwd") or payload.get("workspace") or cwd or os.getcwd()
    event = str(payload.get("hook_event_name") or payload.get("eventName") or payload.get("type") or "").lower()
    event = event.replace("_", "").replace("-", "")
    state = "needs your attention" if event in _WAITING_EVENTS else "turn complete"
    tool_name = _notification_text(payload.get("tool_name"), _TOOL_NAME_LIMIT)
    if event == "permissionrequest" and tool_name:
        state += f" ({tool_name})"
    where = os.path.basename(str(directory).rstrip("/\\")) or directory
    preview = _notification_preview(payload, event, env)
    return f"✓ {session}", f"{where} · {state}" + (f" — {preview}" if preview else "")


def _notification_preview(payload, event, env):
    if event != "stop" or env.get(PREVIEW_ENV) != "1":
        return ""
    return _notification_text(payload.get("last_assistant_message"), _PREVIEW_LIMIT)


def _notification_text(value, limit):
    if not isinstance(value, str):
        return ""
    value = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    if len(value) <= limit:
        return value
    return value[:limit - 1].rstrip() + "…"


def handle_notify(rest, ctx):
    """Hook target. Never fails: a broken notification is not a broken turn."""
    try:
        import sys
        stdin_text = None
        # "stdin" in ctx is the {"isTTY": ...} descriptor, not a stream.
        reader = ctx.get("prompt_stdin") or sys.stdin
        env = os.environ if ctx.get("env") is None else ctx["env"]
        if ctx.get("stdin_is_tty") and not env.get(SESSION_ENV):
            ctx["out"]("cdx notify is called by provider hooks. Enable agent alerts with: cdx set <name> --notify on\n")
            return 0
        if reader is not None and not ctx.get("stdin_is_tty"):
            stdin_text = reader.read()
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
    elif (session.get("launch") or {}).get("notify_preview") is True:
        values[PREVIEW_ENV] = "1"
    return values


def notifications_enabled(session):
    """Off unless this session explicitly turned it on.

    Opt-in rather than on-by-default: provisioning writes into the provider's
    own configuration and, on Codex, asks the user to approve a hook. Doing
    that to every session someone already owns, without being asked, is not a
    default worth having.
    """
    launch = session.get("launch") or {}
    return launch.get("notify") is True


def provision(auth_home, provider, enabled, env=None, spawn_sync=None, base_dir=None):
    """Install or remove cdx's notification hooks in this session's own home.

    Idempotent, so an existing session picks the hooks up on its next launch and
    repeated launches change nothing. Returns True when they were newly
    installed, so the caller can say so once.

    The two providers need different mechanisms, which is not a stylistic
    choice: Claude Code reads hooks straight out of `settings.json`, while Codex
    reads them only from an installed plugin — a free-standing hooks file
    anywhere under `CODEX_HOME` is never looked at.
    """
    env = env or os.environ
    if enabled and not notification_channel(env):
        # Nothing could be delivered on this host, so installing a hook would only
        # buy the user an approval prompt for a feature that shows nothing.
        enabled = False
    if not supports_agent_alerts(provider):
        return False
    command = resolve_hook_command(env)
    if provider == "claude":
        return _apply_hooks(hook_config_path(auth_home, provider), enabled, command)
    if provider == "codex":
        return _provision_codex_plugin(auth_home, enabled, command, env, spawn_sync, base_dir)
    return False


def hook_config_path(auth_home, provider, base_dir=None):
    if provider == "claude":
        return os.path.join(auth_home, ".claude", "settings.json")
    if provider == "codex":
        return os.path.join(codex_plugin_root(auth_home, base_dir), "hooks", "cdx-hooks.json")
    return None


def codex_plugin_root(auth_home, base_dir=None):
    """Where the generated Codex plugin lives — deliberately outside CODEX_HOME.

    A marketplace rooted inside Codex's own home installs without complaint and
    then never runs: Codex registers it pointing straight at the source
    directory instead of taking the cache copy it executes from. Moving the same
    plugin one directory out is the whole difference between working and
    silently doing nothing.
    """
    if base_dir:
        return os.path.join(base_dir, "state", "codex-plugins", os.path.basename(auth_home))
    # Without a base directory, sit beside the home rather than guessing at cdx's
    # layout by walking up from it: two levels above a home is `/` for anything
    # not laid out as `<base>/profiles/<name>`, and writing there fails.
    return os.path.join(os.path.dirname(auth_home), ".cdx-codex-plugins", os.path.basename(auth_home))


# Codex only runs hooks that come from an installed plugin, identified as
# `<plugin>@<marketplace>`. Generating one per session keeps the resolved cdx
# path baked into it.
CODEX_PLUGIN = "cdx-notify"
CODEX_MARKETPLACE = "cdx"
CODEX_PLUGIN_REF = f"{CODEX_PLUGIN}@{CODEX_MARKETPLACE}"


def _provision_codex_plugin(auth_home, enabled, command, env, spawn_sync=None, base_dir=None):
    installed = _codex_plugin_installed(auth_home)
    if enabled == installed:
        return False
    if not enabled:
        _run_codex(["plugin", "remove", CODEX_PLUGIN_REF], auth_home, env, spawn_sync)
        _run_codex(["plugin", "marketplace", "remove", CODEX_MARKETPLACE], auth_home, env, spawn_sync)
        return False
    root = _write_codex_plugin(auth_home, command, base_dir)
    if not root:
        return False
    if not _run_codex(["plugin", "marketplace", "add", root], auth_home, env, spawn_sync):
        return False
    return _run_codex(["plugin", "add", CODEX_PLUGIN_REF], auth_home, env, spawn_sync)


def _codex_plugin_installed(auth_home):
    """Whether Codex's own config already lists our plugin.

    Read rather than remembered, so a plugin the user removed by hand is
    reinstalled on the next launch instead of being assumed present.
    """
    try:
        with open(os.path.join(auth_home, "config.toml"), encoding="utf-8") as handle:
            return f'[plugins."{CODEX_PLUGIN_REF}"]' in handle.read()
    except OSError:
        return False


def _write_codex_plugin(auth_home, command, base_dir=None):
    root = codex_plugin_root(auth_home, base_dir)
    files = {
        os.path.join(root, ".claude-plugin", "marketplace.json"): {
            "name": CODEX_MARKETPLACE,
            "description": "cdx agent notifications",
            "owner": {"name": "cdx"},
            "plugins": [{
                "name": CODEX_PLUGIN,
                "description": "Notify when this cdx session finishes a turn or waits for you",
                "source": "./",
            }],
        },
        # The "hooks" key is what makes Codex load the file at all; without it
        # the plugin installs cleanly and never runs anything.
        os.path.join(root, ".claude-plugin", "plugin.json"): {
            "name": CODEX_PLUGIN,
            "version": "1.0.0",
            "description": "Notify when this cdx session finishes a turn or waits for you",
            "hooks": "./hooks/cdx-hooks.json",
        },
        os.path.join(root, "hooks", "cdx-hooks.json"): {
            "hooks": {
                event: [{"hooks": [{"type": "command", "command": f"{command} {HOOK_ARG}"}]}]
                for event in ("Stop", "PermissionRequest")
            },
        },
    }
    for path, document in files.items():
        if not _write_json(path, document):
            return None
    return root


def _run_codex(args, auth_home, env, spawn_sync):
    """Run one `codex` command, following the repo's (command, args, options)
    spawn_sync contract rather than subprocess.run's, so the same injected
    double serves here as everywhere else."""
    options = {"env": {**env, "CODEX_HOME": auth_home}, "cwd": auth_home}
    try:
        result = (spawn_sync or _subprocess_spawn_sync)("codex", list(args), options)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        # No codex on PATH, or it hung: a skipped provisioning step, never a
        # failed launch.
        return False
    if isinstance(result, dict):
        return not result.get("error") and result.get("status", 0) == 0
    return getattr(result, "returncode", 0) == 0


def _subprocess_spawn_sync(command, args, options):
    return subprocess.run(
        [command, *args],
        env=options.get("env"),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _apply_hooks(path, enabled, command):
    document = _read_json(path)
    if document is None:
        return False
    hooks = document.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    before = json.dumps(hooks, sort_keys=True)
    for event in ("Stop", "Notification"):
        # Rebuilt from whatever is there minus our own entry, so user-authored
        # hooks on the same event survive both installing and removing.
        entries = [entry for entry in hooks.get(event, []) if not _is_ours(entry)]
        if enabled:
            entries.append({
                "hooks": [{"type": "command", "command": f"{command} {HOOK_ARG}"}],
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
    """Ours if any of its commands is a cdx notify invocation."""
    if not isinstance(entry, dict):
        return False
    for hook in entry.get("hooks") or []:
        command = str((hook or {}).get("command") or "")
        if command.endswith(f" {HOOK_ARG}") and "cdx" in command:
            return True
    return False


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
