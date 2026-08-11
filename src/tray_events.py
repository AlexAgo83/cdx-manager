"""The handoff from a provider hook to a running tray, and back.

`cdx notify` runs inside a provider's hook. It cannot wait on a GUI, it may be
killed the moment the turn ends, and several sessions can fire at once. Those
three facts decide the whole design:

  - **Append-only JSONL, opened `O_APPEND`.** A small append is atomic, so two
    hooks firing together cannot interleave or lose each other's event. A
    read-modify-write of one JSON array would silently drop one of them, and
    the loser would be a notification the user simply never gets.
  - **A heartbeat, not a process check.** The tray says it is alive by writing a
    file; `notify` publishes only when that file is fresh. A pid check would
    claim a companion in a different WSL namespace is reachable when it is not.
  - **Freshness wider than one poll period.** The tray writes its heartbeat once
    per poll, so a window narrower than that period reads a perfectly healthy
    tray as stale every time — and the alert would then be delivered twice, once
    by the tray and once by the direct fallback.

Everything degrades to the existing direct notification. A tray that is absent,
stale, too old to understand the schema, or backed by unreadable state is not an
error: it means `notify` keeps doing exactly what it did before.
"""
import json
import os
import time

SCHEMA_VERSION = 1
# The tray heartbeats once per poll: 30s native, 60s across WSL. This window has
# to clear the slowest of those with room for a late tick, or a live tray reads
# as stale and the user gets the same alert twice.
HEARTBEAT_FRESH_SECONDS = 150
# Old alerts are worth less than new ones, so the spool drops the oldest rather
# than growing without bound. A tray that has been down for an hour should not
# flood the user on return.
MAX_SPOOLED_EVENTS = 32
# Compaction threshold. Acknowledged lines stay on disk until this many have
# accumulated, so the common path is one append and no rewrite at all.
COMPACT_AFTER_LINES = 128


def _tray_dir(base_dir):
    return os.path.join(base_dir, "tray")


def events_path(base_dir):
    return os.path.join(_tray_dir(base_dir), "events.jsonl")


def heartbeat_path(base_dir):
    return os.path.join(_tray_dir(base_dir), "heartbeat.json")


def _write_atomic(path, text):
    """Replace a file in one step, so a killed writer never leaves half of one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temp, path)


# --- the tray's side -------------------------------------------------------

def write_heartbeat(base_dir, pid=None, now=None):
    """Say the tray is alive, and which schema it speaks."""
    now = time.time() if now is None else now
    _write_atomic(heartbeat_path(base_dir), json.dumps({
        "schema": SCHEMA_VERSION,
        "pid": os.getpid() if pid is None else pid,
        "at": now,
    }))


def read_heartbeat(base_dir):
    """The heartbeat, or None. Unreadable and malformed both read as absent."""
    try:
        with open(heartbeat_path(base_dir), encoding="utf-8") as handle:
            beat = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(beat, dict) or not isinstance(beat.get("at"), (int, float)):
        return None
    return beat


def tray_is_listening(base_dir, now=None):
    """Whether a tray should own this notification instead of the direct path.

    A schema this CDX does not speak counts as not listening. Publishing to a
    companion that cannot read the event would lose the notification entirely,
    where falling back merely delivers it the old way.
    """
    now = time.time() if now is None else now
    beat = read_heartbeat(base_dir)
    if not beat:
        return False
    if beat.get("schema") != SCHEMA_VERSION:
        return False
    return (now - beat["at"]) <= HEARTBEAT_FRESH_SECONDS


# --- the hook's side -------------------------------------------------------

def publish(base_dir, title, message, kind="complete", now=None, event_id=None, details=None):
    """Hand one event to the tray. Returns True only if it was written.

    False means the caller must deliver it directly, so every failure here has
    to be a False and never an exception: the alternative is a provider hook
    that raises inside someone's agent turn.

    `details` carries the same event as fields, so a companion does not have to
    read a sentence to know which session it belongs to. It is written beside
    the rendered title and message, never instead of them: a companion that
    predates the fields ignores an unknown key and shows what it always showed,
    and a newer one handed a malformed `details` still has the sentence.
    """
    now = time.time() if now is None else now
    try:
        if not tray_is_listening(base_dir, now=now):
            return False
        event = {
            "id": event_id or f"{int(now * 1000)}-{os.getpid()}",
            "at": now,
            "kind": kind,
            "title": title,
            "message": message,
        }
        if isinstance(details, dict) and details:
            event["details"] = details
        path = events_path(base_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        # O_APPEND makes this atomic against other hooks firing at the same
        # instant, which a read-modify-write of a JSON array would not be.
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
        return True
    except OSError:
        return False


# --- shared -----------------------------------------------------------------

def read_events(base_dir, include_acknowledged=False):
    """Every event still on the spool, oldest first.

    A malformed line is skipped rather than fatal. The spool is written by a
    process that can be killed mid-write, so a partial last line is an expected
    state, not corruption.
    """
    try:
        with open(events_path(base_dir), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or not event.get("id"):
            continue
        if event.get("acknowledged") and not include_acknowledged:
            continue
        events.append(event)
    # Keep the newest when the spool has overflowed: a stale alert helps nobody.
    return events[-MAX_SPOOLED_EVENTS:]


def acknowledge(base_dir, ids, now=None):
    """Mark events consumed, idempotently, and compact when it is worth it.

    Acknowledging is what stops one event being shown twice, so it has to
    survive being called with ids already acknowledged, ids that never existed,
    and a tray that crashed between showing and acknowledging.
    """
    now = time.time() if now is None else now
    wanted = set(ids or [])
    if not wanted:
        return {"acknowledged": 0, "compacted": False}

    try:
        with open(events_path(base_dir), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return {"acknowledged": 0, "compacted": False}

    kept = []
    marked = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(event, dict) or not event.get("id"):
            continue
        if event["id"] in wanted and not event.get("acknowledged"):
            event = {**event, "acknowledged": now}
            marked += 1
        kept.append(event)

    compact = len(kept) >= COMPACT_AFTER_LINES
    if compact:
        # Drop what the tray has already shown; unacknowledged events stay,
        # because dropping one would be losing a notification outright.
        kept = [event for event in kept if not event.get("acknowledged")]
    _write_atomic(
        events_path(base_dir),
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in kept),
    )
    return {"acknowledged": marked, "compacted": compact}
