"""The snapshot a tray companion reads, and the display state it renders.

A tray consumer needs three things the CLI status rows do not give it: one
urgency state for a closed icon, a per-session line short enough for a menu, and
an honest word for "this number is old". This module derives all three from the
rows `cdx status` already produces, so the companion never talks to a provider.

The refresh policy is the load-bearing part. `src/codex_usage.py` serializes
live probes on `codex_auth_lock` because Codex rotates its OAuth refresh token,
and the launcher holds that lock for a whole interactive session. A background
consumer polling for fresh quota would either be locked out or race the token,
so the tray reads the cache and says so. `auth_locked` is a first-class state
here, not an error.
"""
from datetime import datetime, timezone

from .session_status import (
    CLAUDE_STATUS_CACHE_TTL_SECONDS,
    CODEX_STATUS_CACHE_TTL_SECONDS,
    STATUS_CACHE_TTL_SECONDS,
)
from .status_view import _format_reset_time

SCHEMA_NAME = "cdx.tray.snapshot"
SCHEMA_MAJOR = 1
SCHEMA_MINOR = 3

# Below this much remaining capacity a session cannot usefully take work. Shared
# with the ranking's own usability threshold so the tray and `cdx next` do not
# disagree about what "blocked" means.
CRITICAL_PCT = 5
LOW_PCT = 25

ICON_OK = "ok"
ICON_LOW = "low"
ICON_CRITICAL = "critical"
ICON_UNKNOWN = "unknown"

FRESH = "fresh"
STALE = "stale"
AUTH_LOCKED = "auth_locked"
UNKNOWN = "unknown"

_PROVIDER_TTL = {
    "codex": CODEX_STATUS_CACHE_TTL_SECONDS,
    "claude": CLAUDE_STATUS_CACHE_TTL_SECONDS,
}


def ttl_seconds_for(provider):
    return _PROVIDER_TTL.get(provider, STATUS_CACHE_TTL_SECONDS)


def parse_iso(value):
    """Rows carry local-offset ISO strings; comparison needs a real instant."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _age_seconds(updated_at, now):
    moment = parse_iso(updated_at)
    if moment is None:
        return None
    return max(0.0, (now - moment).total_seconds())


def session_freshness(row, now):
    """How much this row's numbers can be trusted, and whether that is fixable.

    A running session holds the provider auth lock, so its quota cannot be
    refreshed until it exits. Reporting that as `stale` would invite the user to
    hit refresh forever; `auth_locked` tells them why it will not help.
    """
    age = _age_seconds(row.get("updated_at"), now)
    if age is None:
        return UNKNOWN, None
    if age <= ttl_seconds_for(row.get("provider")):
        return FRESH, age
    return (AUTH_LOCKED if row.get("active") else STALE), age


def icon_state_for_pct(available_pct):
    if available_pct is None:
        return ICON_UNKNOWN
    if available_pct < CRITICAL_PCT:
        return ICON_CRITICAL
    if available_pct < LOW_PCT:
        return ICON_LOW
    return ICON_OK


def _eligible(row):
    return row.get("enabled", True) is not False


def _ago(seconds):
    """How long ago, in the shortest form that stays unambiguous.

    `None` when nothing was ever reported: "never" is a state the caller already
    names, and inventing an age for it would be worse than saying nothing.
    """
    if seconds is None:
        return None
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def menu_session(row, now):
    """One menu line. Everything the tray shows once the user opens it."""
    freshness, age = session_freshness(row, now)
    return {
        "name": row.get("session_name"),
        "label": row.get("label"),
        "provider": row.get("provider"),
        "available_pct": row.get("available_pct"),
        "remaining_5h_pct": row.get("remaining_5h_pct"),
        "remaining_week_pct": row.get("remaining_week_pct"),
        "reset_at": row.get("reset_at"),
        # The same wording `cdx status` uses — "in 5h", "passed 3h ago" — rather
        # than a second vocabulary for the same idea. An absolute stamp costs a
        # dozen characters per row and still makes the reader do the subtraction
        # that matters: how long until it comes back.
        "reset_in": _format_reset_time(row.get("reset_at")),
        "updated_ago": _ago(age),
        "active": bool(row.get("active")),
        "state": icon_state_for_pct(row.get("available_pct")),
        "freshness": freshness,
        "age_seconds": None if age is None else int(age),
        "updated_at": row.get("updated_at"),
    }


def _by_urgency(sessions):
    """Most constrained first, so the menu opens on what the icon is warning about.

    The order the rows arrive in is the store's, which is not the order a person
    reads for. With a dozen accounts the one at 1% sat tenth, below five at
    100%, while the closed icon showed critical — the menu contradicted the
    thing that made you open it.

    Same ranking the icon uses, for the same reason: severity first, then least
    remaining, and never-reported last. A session that never reported is not
    urgent, it is unknown, and putting it on top would bury real news.
    """
    severity = {ICON_CRITICAL: 0, ICON_LOW: 1, ICON_OK: 2, ICON_UNKNOWN: 3}
    return sorted(
        sessions,
        key=lambda s: (
            severity[s["state"]],
            s["available_pct"] if s["available_pct"] is not None else 101,
            s["name"] or "",
        ),
    )


def _worst(sessions):
    """The session whose state the closed icon should show.

    Ordered by severity, then by least remaining capacity, so a tie between two
    critical sessions still names the one closest to empty. Unknown loses to
    every known state: an icon that cries wolf because one session never
    reported is worse than one that shows the worst thing it actually knows.
    """
    severity = {ICON_CRITICAL: 0, ICON_LOW: 1, ICON_OK: 2, ICON_UNKNOWN: 3}
    return min(
        sessions,
        key=lambda s: (
            severity[s["state"]],
            s["available_pct"] if s["available_pct"] is not None else 101,
        ),
    )


_STATE_WORDS = {
    ICON_OK: "capacity ok",
    ICON_LOW: "capacity low",
    ICON_CRITICAL: "capacity critical",
    ICON_UNKNOWN: "capacity unknown",
}

_FRESHNESS_WORDS = {
    STALE: "figures are stale",
    AUTH_LOCKED: "cannot refresh while a session runs",
    UNKNOWN: "never reported",
}


def tooltip_for(worst):
    """What the closed icon may say on hover.

    Deliberately without the session name. `req_035` AC3 forbids exposing
    accounts before the menu is opened and `req_038` AC4 asks the tooltip to
    name the limiting source and its reset; a tooltip appears on hover, without
    a click, and shows up in a screen share. Naming the provider and the reset
    satisfies the second without breaking the first. The session name is one
    click away in the menu.

    It is also the accessibility path: every state the glyph conveys is written
    here in words, so nothing depends on telling two shapes apart.
    """
    if worst is None:
        return "CDX · no enabled sessions"
    parts = [_STATE_WORDS.get(worst["state"], worst["state"])]
    if worst["available_pct"] is not None:
        parts.append(f"{int(worst['available_pct'])}% left")
    note = _FRESHNESS_WORDS.get(worst["freshness"])
    if note:
        parts.append(note)
    if worst.get("reset_at"):
        parts.append(f"resets {worst['reset_at']}")
    return "CDX · " + " · ".join(parts)


def build_snapshot(rows, now, cdx_version, refreshable=True, plugins=None, terminal=None):
    """The whole contract, from the rows `cdx status` already returns.

    `icon` carries no session name, account, or figure: it is what shows while
    the menu is closed, and `req_035` AC3 forbids leaking anything there.
    """
    sessions = _by_urgency([menu_session(row, now) for row in rows if _eligible(row)])
    if not sessions:
        icon = {
            "state": ICON_UNKNOWN,
            "reason": "no_sessions",
            "session_count": 0,
            "tooltip": tooltip_for(None),
        }
    else:
        worst = _worst(sessions)
        icon = {
            "state": worst["state"],
            "reason": worst["freshness"],
            "session_count": len(sessions),
            # Everything the closed icon is allowed to say, in words.
            "tooltip": tooltip_for(worst),
        }
    return {
        "schema": {"name": SCHEMA_NAME, "major": SCHEMA_MAJOR, "minor": SCHEMA_MINOR},
        "cdx_version": cdx_version,
        "generated_at": now.isoformat(),
        "icon": icon,
        "sessions": sessions,
        "refreshable": bool(refreshable),
        "actions": ["refresh", "open_terminal"],
        # Zero or more bounded cards from enabled integrations. A minor-version
        # addition: a companion that predates it ignores the key and shows
        # exactly what it showed before.
        "plugins": list(plugins or []),
        # Which terminal a session row should open, or None for the platform's
        # own. Carried here rather than kept by the companion, because every
        # other durable tray preference already lives in CDX and a second store
        # is a second thing to keep in step.
        "terminal": terminal,
    }


def read_snapshot(payload):
    """Read a snapshot that may be newer than this reader.

    A companion and the CLI are updated separately, so version drift is the
    normal state. An unknown major version keeps every field this reader
    understands and adds one hint, rather than refusing to render.
    """
    schema = (payload or {}).get("schema") or {}
    major = schema.get("major")
    if schema.get("name") != SCHEMA_NAME or not isinstance(major, int):
        return {"ok": False, "reason": "not_a_cdx_tray_snapshot", "snapshot": None, "update_hint": None}
    known = {
        key: payload.get(key)
        for key in ("schema", "cdx_version", "generated_at", "icon", "sessions", "refreshable", "actions")
        if key in payload
    }
    hint = None
    if major > SCHEMA_MAJOR:
        hint = f"This CDX reads tray snapshot v{SCHEMA_MAJOR}; the snapshot is v{major}. Update CDX to see everything."
    return {"ok": True, "reason": None, "snapshot": known, "update_hint": hint}
