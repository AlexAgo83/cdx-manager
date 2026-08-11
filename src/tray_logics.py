"""The bundled Logics card: what is blocked, what is next, and nothing else.

Built from `logics-manager status --format json` and from nothing else. Not for
lack of richer sources — the repository is right there — but because a tray card
that read documents would be a second implementation of Logics' own view, drifting
from it at its own pace. One command, one contract, and when it changes the card
breaks loudly in one place instead of quietly in several.

Two rows at most, and the choice of which two is the whole design: the first
blocked document, because it is what stops work, and the highest-priority active
task, because it is what to do instead. A tray menu that listed everything would
be a worse `logics-manager status`, run more often.
"""
import json
import os
import subprocess
import time

from .logics_view import resolve_logics_manager
from .tray_plugins import ADAPTER_TIMEOUT_SECONDS, CARD_TTL_SECONDS

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def logics_card(env=None, now=None, cache=None, runner=None, executable=None, directories=None):
    """One card, or None when there is nothing truthful to show.

    None covers every unhappy case on purpose — not installed, not a Logics
    repository, a command that failed or timed out, output that is not the JSON
    we expect. A card saying "Logics is unhappy" would be noise in a menu the
    user opened to look at quota.
    """
    now = time.time() if now is None else now
    cached = _from_cache(cache, now)
    if cached is not None:
        return cached
    status = _status(env=env, runner=runner, executable=executable, directories=directories)
    card = _card_from_status(status)
    _to_cache(cache, now, card)
    return card


def _from_cache(cache, now):
    """A card is reused for its TTL, so a tray polling every 30 seconds does not
    make Logics pay that rate. A manual refresh passes no cache and so bypasses
    this entirely, which is what makes the refresh action mean something."""
    if not isinstance(cache, dict):
        return None
    stamped = cache.get("logics")
    if not isinstance(stamped, dict):
        return None
    if now - stamped.get("at", 0) > CARD_TTL_SECONDS:
        return None
    return stamped.get("card")


def _to_cache(cache, now, card):
    if isinstance(cache, dict):
        cache["logics"] = {"at": now, "card": card}


def _repository_root(directory):
    directory = os.path.realpath(directory or "")
    while directory and directory != os.path.dirname(directory):
        if os.path.exists(os.path.join(directory, ".git")):
            return directory
        directory = os.path.dirname(directory)
    return directory if os.path.exists(os.path.join(directory, ".git")) else None


def _status(env=None, runner=None, executable=None, directories=None):
    """`logics-manager status --format json`, or None however it failed.

    Resolved through CDX's own lookup rather than a path the tray knows: on a
    Windows host serving CDX from WSL, the tray is not where `logics-manager`
    lives, and the only process that can find it is this one.
    """
    executable = executable or resolve_logics_manager(env or {})
    if not executable:
        return None
    roots = sorted({root for root in (_repository_root(path) for path in (directories or [])) if root})
    if directories is not None and not roots:
        return None
    payloads = []
    for root in roots or [None]:
        try:
            completed = (runner or subprocess.run)(
                [executable, "status", "--format", "json"], capture_output=True,
                text=True, timeout=ADAPTER_TIMEOUT_SECONDS, check=False, **({"cwd": root} if root else {}),
            )
            payload = json.loads(completed.stdout) if getattr(completed, "returncode", 1) == 0 else None
        except (OSError, subprocess.SubprocessError, TypeError, ValueError):
            return None if not payloads else payloads
        if isinstance(payload, dict):
            payloads.append((root, payload))
    return payloads if roots else (payloads[0][1] if payloads else None)


def _card_from_status(status):
    if isinstance(status, list):
        cards = [(root, _card_from_status(payload), len(payload.get("blocked_docs") or [])) for root, payload in status]
        cards = [(root, card, blocked) for root, card, blocked in cards if card]
        if not cards:
            return None
        root, card, _ = sorted(cards, key=lambda item: (-item[2], -len(item[1]["rows"]), item[0] or ""))[0]
        repository_count = len(cards)
        blocked_count = sum(item[2] for item in cards)
        card["summary"] = f"{repository_count} repositories · {blocked_count} blocked"
        prefix = os.path.basename(root or "")
        for row in card["rows"]:
            row["label"] = f"{prefix}: {row['label']}"
        return card
    if not isinstance(status, dict):
        return None
    blocked = [doc for doc in (status.get("blocked_docs") or []) if isinstance(doc, dict)]
    active = [task for task in (status.get("active_tasks") or []) if isinstance(task, dict)]
    if not blocked and not active:
        # Nothing blocked and nothing in flight is not a state worth a row. The
        # summary still says so, because "0 blocked" is the good news a user
        # opening the menu wants to confirm.
        return {
            "title": "Logics",
            "summary": "Nothing blocked, nothing in progress",
            "rows": [],
            "actions": ["logics.open", "logics.refresh"],
        }
    rows = []
    if blocked:
        rows.append(_row(blocked[0], "blocked"))
    if active:
        rows.append(_row(_most_urgent(active), "next"))
    return {
        "title": "Logics",
        "summary": f"{len(blocked)} blocked · {len(active)} in progress",
        "rows": [row for row in rows if row],
        "actions": ["logics.open", "logics.refresh"],
    }


def _most_urgent(tasks):
    """High before medium before low, and least finished first inside a priority.

    Progress breaks the tie because a task at 90% needs a push and one at 0%
    needs a decision, and the tray has room to point at one of them.
    """
    def rank(task):
        priority = str(task.get("priority") or "").strip().lower()
        return (_PRIORITY_ORDER.get(priority, len(_PRIORITY_ORDER)), _progress(task))

    return sorted(tasks, key=rank)[0]


def _progress(task):
    value = task.get("progress")
    return value if isinstance(value, (int, float)) else 0


def _row(doc, kind):
    ref = doc.get("ref")
    title = doc.get("title") or ref
    if not isinstance(ref, str) or not ref or not isinstance(title, str):
        return None
    return {"label": f"{kind}: {title}", "action": f"logics.focus:{ref}"}
