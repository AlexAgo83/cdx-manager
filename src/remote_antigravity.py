"""Antigravity adapter for the remote-control switch loop in remote_claude.

The piloted mode is `agy --input-format stream-json --output-format stream-json
-p=` (agy 1.5.8): one NDJSON `{"event": "user", ...}` line per turn on stdin,
`init`, `step_update` and `result` events on stdout. `--conversation <id>`
continues a conversation in either mode.

cdx cannot name the conversation when it starts the TUI, so the id is read
afterwards from agy's own conversation index (the newest conversation in the
launch directory since the launch), or from the piloted run's `init` event when
the TUI never started one. The same index says whether the TUI's turn is idle.
"""

import json
import os
import signal
import sqlite3
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

IDLE_STATUS = "CASCADE_RUN_STATUS_IDLE"


def summaries_path(auth_home):
    return os.path.join(auth_home, ".gemini", "antigravity-cli", "conversation_summaries.db")


def _rows(auth_home, query, args=()):
    """Rows from agy's conversation index, [] when it does not exist yet, None when unreadable."""
    path = summaries_path(auth_home)
    if not os.path.isfile(path):
        return []
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        try:
            return connection.execute(query, args).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return None


def _in_workspace(uris, cwd):
    try:
        listed = json.loads(uris or "[]")
    except ValueError:
        return False
    target = os.path.realpath(cwd)
    return any(os.path.realpath(unquote(urlparse(uri).path)) == target
               for uri in listed if isinstance(uri, str) and uri.startswith("file://"))


def find_conversation(auth_home, cwd, since):
    """The id of the newest conversation in `cwd` changed at or after `since` (UTC), or None.

    shortcut: two agy TUIs of one profile in the same directory at once are
    told apart only by recency; record the id from agy if it ever exposes one.
    """
    edge = since.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = _rows(auth_home, "SELECT conversation_id, workspace_uris FROM conversation_summaries "
                            "WHERE substr(last_modified_time, 1, 19) >= ? ORDER BY last_modified_time DESC", (edge,))
    for conversation_id, uris in rows or []:
        if _in_workspace(uris, cwd):
            return conversation_id
    return None


def conversation_idle(auth_home, conversation_id):
    """Whether the conversation has no running turn. Unknown (unreadable index) counts as busy."""
    if not conversation_id:
        return True
    rows = _rows(auth_home, "SELECT status, not_fully_idle FROM conversation_summaries "
                            "WHERE conversation_id = ?", (conversation_id,))
    if rows is None:
        return False
    if not rows:
        return True
    status, not_fully_idle = rows[0]
    return status == IDLE_STATUS and not not_fully_idle


class AntigravityAdapter:
    """What the switch loop needs to know about the Antigravity CLI."""

    interrupt_ends_run = True

    def __init__(self, auth_home, cwd, command, args, since=None):
        self.auth_home, self.cwd, self.command, self.args = auth_home, cwd, command, list(args)
        self.since = since or datetime.now(timezone.utc)
        self.conversation_id = None
        self._replies = {}

    def discover(self):
        """The TUI's conversation id once agy has written it; it never changes afterwards."""
        if not self.conversation_id:
            self.conversation_id = find_conversation(self.auth_home, self.cwd, self.since)
        return self.conversation_id

    def tui_idle(self):
        return conversation_idle(self.auth_home, self.discover())

    def argv(self):
        target = ["--conversation", self.discover()] if self.discover() else []
        return [self.command, *self.args, *target,
                "--input-format", "stream-json", "--output-format", "stream-json", "-p="]

    def map_event(self, event):
        kind = event.get("event")
        body = event.get(kind) if isinstance(event.get(kind), dict) else {}
        identifier = event.get("conversation_id") or body.get("conversation_id")
        if identifier and not self.conversation_id:
            self.conversation_id = identifier
        if kind == "step_update" and body.get("step_type") == "agent_response":
            # Text arrives as deltas; the reply is whole once its step is DONE.
            index = body.get("step_index")
            self._replies[index] = self._replies.get(index, "") + (body.get("text_delta") or "")
            if body.get("state") == "DONE":
                text = self._replies.pop(index).strip()
                return ("assistant", {"text": text}) if text else None
            return None
        if kind == "result":
            self._replies.clear()
            status = body.get("status") or ""
            if status == "SUCCESS":
                return ("done", {"text": (body.get("response") or "").strip()})
            if status == "CANCELLED" or body.get("finished_reason") == "interrupted":
                return ("interrupted", {})
            return ("failed", {"reason": body.get("finished_reason") or status.lower() or "error",
                               "text": body.get("error")})
        return None

    def user_message(self, text):
        return {"event": "user", "message": {"role": "user", "content": text}}

    def interrupt(self, proc, _write):
        """agy 1.5.8 ignores any stream input but `user`; SIGINT ends the turn as `interrupted`
        and the run with it, so the loop starts a new run on the same conversation."""
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGINT)
