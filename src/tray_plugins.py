"""Cards the tray shows for tools other than CDX itself.

The shape of this is a deliberate refusal. A plugin system would mean discovery,
trust, packaging, versioning and a lifecycle — and there is exactly one
integration asking for it, which is not evidence that any of that is needed. So
there is no marketplace, no installation from a URL, no plugin-defined command,
and nothing runs inside the tray process. What exists is narrower and testable:

  - **CDX owns the registry.** Adapters are functions in this repository, named
    here. Nothing is discovered at runtime, so nothing unknown can run.
  - **Adapters produce data, never behaviour.** A card is a summary, at most two
    rows, and action ids drawn from a fixed vocabulary. An adapter cannot ask
    the tray to run a command, because it cannot express one.
  - **Failure is silence.** A slow, broken, absent or malformed adapter costs
    its own card and nothing else. The session rows that are the reason the tray
    exists are never at risk from an integration nobody depends on.
  - **The tray executes nothing.** Cards ride the snapshot CDX already builds,
    and every action goes back through CDX. `adr_005` put the transport there;
    an integration is not a reason to open a second one.
"""
import json
import os
import re

CARD_SCHEMA_MAJOR = 1
# How long a card stays usable before CDX asks its adapter again. The tray polls
# every 30 to 60 seconds and must not make an integration pay that rate, so a
# card outlives a poll and a manual refresh bypasses it.
CARD_TTL_SECONDS = 60
# What an adapter is allowed to spend. It runs inside `cdx tray status`, which a
# user is waiting on, so this is small on purpose.
ADAPTER_TIMEOUT_SECONDS = 5

_MAX_ROWS = 2
_MAX_TEXT = 80
# Action ids are `<plugin>.<verb>` or `<plugin>.<verb>:<ref>`, and the reference
# is restricted to what a Logics ref can contain. This is the whole reason an
# action cannot become a command: there is no character in here that a shell
# would treat as one.
_ACTION_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,15}\.[a-z][a-z0-9_]{0,15}(:[A-Za-z0-9_.-]{1,120})?$")

STATE_VERSION = 1


def state_path(base_dir):
    return os.path.join(base_dir, "tray", "plugins.json")


def enabled_plugins(base_dir):
    """The plugins the user turned on. Nothing is on by default.

    An unreadable or unknown-version state file reads as nothing enabled: an
    integration is opt-in, and inheriting one from a file we cannot parse is
    the opposite of opt-in.
    """
    try:
        with open(state_path(base_dir), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        return []
    enabled = state.get("enabled")
    return [name for name in enabled if name in ADAPTERS] if isinstance(enabled, list) else []


def set_plugin_enabled(base_dir, name, enabled):
    """Turn one plugin on or off, and report what is on afterwards."""
    if name not in ADAPTERS:
        raise KeyError(name)
    current = set(enabled_plugins(base_dir))
    current.add(name) if enabled else current.discard(name)
    path = state_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump({"version": STATE_VERSION, "enabled": sorted(current)}, handle, indent=2)
    os.replace(temp, path)
    return sorted(current)


def _text(value, limit=_MAX_TEXT):
    """Printable, single-line and bounded. A card is a menu row, not a document."""
    if not isinstance(value, str):
        return ""
    value = " ".join("".join(c if c.isprintable() else " " for c in value).split())
    return value[: limit - 1] + "…" if len(value) > limit else value


def bounded_card(raw, plugin):
    """One adapter's output, or None if it cannot be trusted as a card.

    Everything is checked rather than assumed, including from an adapter in this
    repository: the check is what lets the tray render a card without knowing
    which adapter produced it, and a first-party bug is not less of a bug.
    """
    if not isinstance(raw, dict):
        return None
    title = _text(raw.get("title"))
    summary = _text(raw.get("summary"))
    if not title or not summary:
        return None
    rows = []
    for row in (raw.get("rows") or [])[:_MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        label = _text(row.get("label"))
        action = row.get("action")
        if not label or not _valid_action(action, plugin):
            continue
        root = row.get("root")
        if root is not None:
            if plugin != "logics" or not action.startswith("logics.focus:") or not _valid_root(root):
                continue
        rows.append({"label": label, "action": action, **({"root": root} if root else {})})
    actions = [a for a in (raw.get("actions") or []) if _valid_action(a, plugin)]
    return {
        "plugin": plugin,
        "schema": CARD_SCHEMA_MAJOR,
        "title": title,
        "summary": summary,
        "rows": rows,
        "actions": actions[:_MAX_ROWS],
    }


def _valid_action(action, plugin):
    return (
        isinstance(action, str)
        and bool(_ACTION_PATTERN.match(action))
        and action.split(".", 1)[0] == plugin
    )


def _valid_root(root):
    return isinstance(root, str) and os.path.isabs(root) and "\x00" not in root and len(root) <= 4096


def collect_cards(base_dir, env=None, now=None, adapters=None, cache=None, directories=None):
    """Every enabled plugin's card, bounded, with failures dropped.

    Never raises. An adapter that throws, hangs past its timeout, returns
    nonsense or is simply not installed contributes nothing, and the caller
    cannot tell the difference — which is the point: the tray's own data must
    not depend on how an integration is having its day.
    """
    registry = ADAPTERS if adapters is None else adapters
    cards = []
    for name in enabled_plugins(base_dir):
        adapter = registry.get(name)
        if not adapter:
            continue
        try:
            raw = adapter(env=env, now=now, cache=cache, directories=directories) if name == "logics" else adapter(env=env, now=now, cache=cache)
        except Exception:  # noqa: BLE001 - an integration cannot break the tray
            continue
        card = bounded_card(raw, name)
        if card:
            cards.append(card)
    return cards


def _logics_adapter(env=None, now=None, cache=None, directories=None):
    from .tray_logics import logics_card

    return logics_card(env=env, now=now, cache=cache, directories=directories)


# The registry. A name here is the only way an adapter can run, and adding one
# is a change to this repository — which is the trust model, stated as code.
ADAPTERS = {"logics": _logics_adapter}
