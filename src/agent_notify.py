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

from .config import get_cdx_home
from .notify import notification_channel, send_desktop_notification
from .tray_alerts import alerts_enabled
from .tray_events import publish

# Set on the provider process at launch; the hook runs as its child and inherits both.
SESSION_ENV = "CDX_SESSION_NAME"
PREVIEW_ENV = "CDX_NOTIFY_PREVIEW"

# Our entries are recognised by the command they run, not by a marker key of our
# own: both providers validate this file against their own schema, and an extra
# key they do not know is a rejection risk for no gain.
HOOK_ARG = "notify"

_WAITING_EVENTS = {"notification", "permissionrequest"}
# The Notification states that mean the agent is waiting for its user.
#
# Claude's Notification hook is a broad one: `permission_prompt` fires for the
# same tool call `PermissionRequest` already reports, exactly and immediately,
# so subscribing to both once produced two alerts for one request. Filtering
# here rather than unsubscribing keeps the idle states, which nothing else
# reports at all — an agent waiting on an answer would otherwise go silent.
_WAITING_NOTIFICATIONS = {"idle_prompt", "agent_needs_input"}
# Hook events that decide something. Anything this process writes to stdout on
# one of these is read by Claude Code as an allow or a deny for the tool call,
# so `cdx notify` has to stay silent on them whatever happens.
_DECIDING_EVENTS = {"permissionrequest"}
# A turn that ended on a provider error rather than on an answer.
#
# Claude Code publishes this; Codex documents no equivalent, so this is a
# Claude-only alert and the documentation says so rather than implying parity.
_FAILURE_EVENTS = {"stopfailure"}
# Error classes that usually clear on their own. The distinction is the whole
# point of the alert: an overloaded model and a billing error both stop the
# turn, and reacting to them the same way is what trains someone to ignore
# both. Anything unrecognised is treated as needing attention — a failure this
# build has never seen is not one to reassure the user about.
_TRANSIENT_ERRORS = {"rate_limit", "overloaded", "server_error", "max_output_tokens"}
_PREVIEW_LIMIT = 180
_TOOL_NAME_LIMIT = 80
_TERMINAL_ID_LIMIT = 128


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


def hook_event(payload):
    """The provider's event name, in one spelling.

    Both providers publish the same names now, but they have each spelled them
    differently over time and Codex's older `notify` used `type`. Normalising in
    one place keeps every caller reading the same value.
    """
    raw = payload.get("hook_event_name") or payload.get("eventName") or payload.get("type") or ""
    return str(raw).lower().replace("_", "").replace("-", "")


def is_deciding_event(payload):
    """Whether this hook's output would be read as a permission decision."""
    return hook_event(payload) in _DECIDING_EVENTS


def _is_reportable(payload, event):
    """Whether this event is one the user should hear about at all.

    A Notification that is not a waiting state is either something another hook
    reports exactly — `permission_prompt` duplicates PermissionRequest — or an
    internal state the user has no action to take on.
    """
    if event != "notification":
        return True
    kind = str(payload.get("notification_type") or "").lower()
    # An older Claude sent no type at all. Reporting it is the safer default: a
    # duplicate is a nuisance, a missed "the agent is waiting for you" is the
    # failure this feature exists to prevent.
    return not kind or kind in _WAITING_NOTIFICATIONS


def compose_notification(payload, env=None, cwd=None):
    """Title and message for this event, or None if we should stay quiet."""
    env = os.environ if env is None else env
    session = env.get(SESSION_ENV)
    if not session:
        return None
    event = hook_event(payload)
    if not _is_reportable(payload, event):
        return None
    directory = payload.get("cwd") or payload.get("workspace") or cwd or os.getcwd()
    where = os.path.basename(str(directory).rstrip("/\\")) or directory
    if event in _FAILURE_EVENTS:
        # A different mark, because the word alone is not enough: a glance at a
        # notification centre reads the symbol first, and a failed turn that
        # carries the completion tick is a turn the user believes finished.
        state = _failure_state(payload)
        detail = _failure_detail(payload, env)
        return f"✕ {session}", f"{where} · {state}" + (f" — {detail}" if detail else "")
    state = "needs your attention" if event in _WAITING_EVENTS else "turn complete"
    tool_name = _notification_text(payload.get("tool_name"), _TOOL_NAME_LIMIT)
    if event == "permissionrequest" and tool_name:
        state += f" ({tool_name})"
    preview = _notification_preview(payload, event, env)
    return f"✓ {session}", f"{where} · {state}" + (f" — {preview}" if preview else "")


def error_class(payload):
    """The provider's error class, normalised. Empty when it sent none."""
    return _notification_text(payload.get("error_type"), _TOOL_NAME_LIMIT).lower().replace(" ", "_")


def _failure_state(payload):
    """What a failed turn says it is, in words that suggest what to do.

    The class itself is included rather than translated: `rate_limit` and
    `billing_error` mean different things to whoever reads them, and inventing
    friendlier wording for a closed vocabulary loses the part that identifies
    the problem.
    """
    kind = error_class(payload)
    if not kind:
        return "turn failed"
    if kind in _TRANSIENT_ERRORS:
        return f"turn interrupted ({kind})"
    return f"turn failed ({kind}) — needs you"


def _failure_detail(payload, env):
    """The provider's own message, under the same opt-in as any other free text."""
    if env.get(PREVIEW_ENV) != "1":
        return ""
    return _notification_text(payload.get("error_message"), _PREVIEW_LIMIT)


def structured_details(payload, env=None, cwd=None):
    """The event as fields, for a tray that should not parse a sentence.

    What is deliberately absent is the point of this function. `tool_input`
    carries command lines, paths and patch bodies; `transcript_path` points at
    the whole conversation; `session_id` and `turn_id` identify a provider
    session rather than a cdx one. None of them reach the spool. What crosses is
    what cdx already knew (its own session name, the project directory) plus the
    closed-vocabulary metadata the providers document: the event, the tool name,
    the model, the permission category and the stop reason.
    """
    env = os.environ if env is None else env
    event = hook_event(payload)
    directory = payload.get("cwd") or payload.get("workspace") or cwd or os.getcwd()
    details = {
        "session": env.get(SESSION_ENV) or "",
        "project": os.path.basename(str(directory).rstrip("/\\")) or str(directory),
        "event": event,
    }
    terminal_id = _notification_text(env.get("ITERM_SESSION_ID"), _TERMINAL_ID_LIMIT)
    if terminal_id:
        details["terminal"] = {"kind": "iterm2", "id": terminal_id}
    for key, source, limit in (
        ("tool", "tool_name", _TOOL_NAME_LIMIT),
        ("error_type", "error_type", _TOOL_NAME_LIMIT),
        ("model", "model", _TOOL_NAME_LIMIT),
        ("category", "permission_category", _TOOL_NAME_LIMIT),
        ("stop_reason", "stop_reason", _TOOL_NAME_LIMIT),
    ):
        value = _notification_text(payload.get(source), limit)
        if value:
            details[key] = value
    preview = _notification_preview(payload, event, env)
    if preview:
        details["preview"] = preview
    reason = _permission_reason(payload, event, env)
    if reason:
        details["reason"] = reason
    failure = _failure_detail(payload, env) if event in _FAILURE_EVENTS else ""
    if failure:
        details["preview"] = failure
    return details


def alert_kind(payload):
    """Which of the three shapes this event is, for the tray's marker.

    A failure is its own kind rather than borrowing `attention`: they call for
    different reactions, and a companion that predates this shows the neutral
    marker with a message that still says the turn failed.
    """
    event = hook_event(payload)
    if event in _FAILURE_EVENTS:
        return "failed"
    return "attention" if event in _WAITING_EVENTS else "complete"


def _permission_reason(payload, event, env):
    """The provider's own words for what it is asking permission to do.

    The one field taken out of `tool_input`, and only this one: it is prose the
    provider wrote for a human, where everything else in there is the command
    itself. It follows the response-preview preference like any other free text,
    because prose a provider composed can quote whatever it was asked to do.
    """
    if event != "permissionrequest" or env.get(PREVIEW_ENV) != "1":
        return ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return _notification_text(tool_input.get("description"), _PREVIEW_LIMIT)


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
        payload = read_hook_payload(rest, stdin_text)
        # From here on nothing may be written to stdout. On a PermissionRequest
        # Claude Code reads this process's stdout as the decision for the tool
        # call being asked about, so a stray line would allow or deny it. The
        # notification paths below print nothing; this is the statement of why
        # they must not start.
        composed = compose_notification(payload, env, ctx.get("cwd"))
        if composed:
            # Muted stops the banner, not the record: the event still reaches a
            # running tray so the menu can show what was missed, and the direct
            # path stays quiet too — otherwise quitting the tray would un-mute.
            base_dir = (ctx.get("service") or {}).get("base_dir")
            muted = bool(base_dir) and not alerts_enabled(base_dir)
            if muted:
                _published_to_tray(ctx, composed, payload, env, ctx.get("cwd"))
                return 0
            # A live tray becomes the sole owner of this alert, so the user sees
            # one notification rather than two. Publication happens below the
            # composition boundary on purpose: the tray receives the same
            # already-sanitized title and message the direct path would send,
            # and cannot be handed anything the privacy rules removed.
            if not _published_to_tray(ctx, composed, payload, env, ctx.get("cwd")):
                send_desktop_notification(*composed, spawn_sync=ctx.get("spawn_sync"), env=env)
    except Exception:  # noqa: BLE001 - deliberate: the caller is an agent turn
        pass
    return 0


def launch_notify_env(session, enabled, env=None):
    """Env the provider is launched with, carrying who we are and privacy settings.

    `CDX_HOME` is pinned rather than inherited, and that is what makes tray
    routing work at all. It defaults to `~/.cdx`, resolved against `HOME` — and
    a provider session runs with `HOME` redirected into its own profile, which
    is how cdx isolates auth. So a hook calling `cdx notify` would resolve a
    *different* store from the one the companion writes its heartbeat into, find
    no tray, and quietly deliver the notification itself. The symptom is a
    running tray that never receives an alert, with nothing reporting an error.
    """
    env = os.environ if env is None else env
    values = {SESSION_ENV: session["name"], "CDX_HOME": get_cdx_home(env)}
    if enabled and (session.get("launch") or {}).get("notify_preview") is True:
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
    # PermissionRequest is what Codex has always used and Claude Code now
    # publishes too: it fires immediately and names the tool, where Notification
    # is delayed and does not. Notification stays subscribed for the waiting
    # states nothing else reports; the duplicate it used to cause is filtered in
    # `cdx notify` rather than avoided by unsubscribing.
    # StopFailure is Claude-only: Codex documents no equivalent, so a turn its
    # provider kills stays silent there and the documentation says so rather
    # than implying a parity that does not exist.
    for event in ("Stop", "StopFailure", "Notification", "PermissionRequest"):
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


def _published_to_tray(ctx, composed, payload, env=None, cwd=None):
    """Hand the alert to a live tray, or say we did not.

    False is the safe answer to everything: no base directory, no heartbeat, a
    stale one, a schema mismatch, or an unwritable spool all mean the direct
    path still runs. The only way to lose a notification here would be to
    return True without having written it.

    The rendered title and message go too, unchanged. A companion older than the
    structured fields reads exactly what it read before, and a newer one that is
    handed a malformed event still has a sentence to show.
    """
    try:
        base_dir = (ctx.get("service") or {}).get("base_dir")
        if not base_dir:
            return False
        return publish(
            base_dir,
            composed[0],
            composed[1],
            kind=alert_kind(payload),
            details=structured_details(payload, env, cwd),
        )
    except Exception:  # noqa: BLE001 - the caller is an agent turn
        return False
