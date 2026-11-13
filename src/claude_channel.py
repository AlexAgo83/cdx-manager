"""Stdio MCP channel that pushes `cdx send` messages into a live Claude Code TUI.

Claude Code spawns this server (`--dangerously-load-development-channels server:cdx`)
and shows each message in the running session like a typed one. Nothing stops the
TUI, so its background tasks, permissions and slash commands stay as they were.
The launcher appends one JSON object per line to the inbox file named by
CDX_CHANNEL_INBOX; this server forwards each new line as a channel event.
No dependency: the MCP SDK is not installed where cdx runs.
"""

import json
import os
import sys
import threading
import time

INBOX_ENV = "CDX_CHANNEL_INBOX"
INSTRUCTIONS = ("Messages from the operator's remote chat arrive as <channel source=\"cdx\">. "
                "Treat each one exactly like a message typed in this terminal and answer in the session.")

_lock = threading.Lock()


def _write(message):
    with _lock:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()


def event(text):
    return {"jsonrpc": "2.0", "method": "notifications/claude/channel", "params": {"content": text}}


def answer(request):
    """The JSON-RPC reply to one request from Claude Code, or None for a notification."""
    if "id" not in request:
        return None
    if request.get("method") == "initialize":
        version = (request.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return {"jsonrpc": "2.0", "id": request["id"], "result": {
            "protocolVersion": version, "capabilities": {"experimental": {"claude/channel": {}}},
            "serverInfo": {"name": "cdx", "version": "1"}, "instructions": INSTRUCTIONS}}
    if request.get("method") == "ping":
        return {"jsonrpc": "2.0", "id": request["id"], "result": {}}
    return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}


def _pump(path):
    offset = os.path.getsize(path) if os.path.exists(path) else 0  # only messages sent after start
    while True:
        try:
            with open(path, encoding="utf-8") as handle:
                handle.seek(offset)
                chunk = handle.read()
            complete = chunk[:chunk.rfind("\n") + 1]
            offset += len(complete.encode("utf-8"))
            for line in complete.splitlines():
                try:
                    text = json.loads(line).get("text")
                except (ValueError, AttributeError):
                    continue
                if isinstance(text, str) and text.strip():
                    _write(event(text))
        except OSError:
            pass
        time.sleep(0.3)


def main():
    threading.Thread(target=_pump, args=(os.environ[INBOX_ENV],), daemon=True).start()
    for line in sys.stdin:
        try:
            reply = answer(json.loads(line))
        except ValueError:
            continue
        if reply:
            _write(reply)


if __name__ == "__main__":
    main()
