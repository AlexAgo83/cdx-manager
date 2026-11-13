"""Codex remote control: one app-server shared by the TUI and `cdx send`.

`codex app-server` serves several clients on one thread. The launcher starts it
on a loopback WebSocket guarded by a capability token, attaches the TUI with
`--remote`, and joins as a second client to start turns on the TUI's thread.
The TUI renders those turns live, so the terminal never stops showing the
conversation. Turn and item notifications feed the session's event log.
"""

import itertools
import json
import os
import queue
import secrets
import socket
import subprocess
import threading
import time

from .remote_control import Endpoint, EventLog, LaunchTerminated, _write_private, state_dir
from .ws_client import WebSocket, WebSocketClosed

TOKEN_ENV = "CDX_CODEX_REMOTE_TOKEN"
STARTUP_SECONDS = 20
POLL_SECONDS = 0.25
THREAD_WAIT_SECONDS = 120


class NoThreadYet(RuntimeError):
    """The TUI has not opened its thread yet (still on a startup screen)."""


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def server_argv(command, port, token_file):
    return [command, "app-server", "--listen", f"ws://127.0.0.1:{port}",
            "--ws-auth", "capability-token", "--ws-token-file", token_file]


def tui_args(args, port):
    # The update prompt would hold the TUI on a startup screen with no thread for
    # remote turns to land in; cdx updates Codex on its own schedule.
    return [*args, "-c", "check_for_update_on_startup=false",
            "--remote", f"ws://127.0.0.1:{port}", "--remote-auth-token-env", TOKEN_ENV]


def map_notification(message, buffers):
    """(event kind, fields) for the event log, or None."""
    method, params = message.get("method"), message.get("params") or {}
    if method == "turn/started":
        return ("working", {"turn_id": (params.get("turn") or {}).get("id")})
    if method == "item/agentMessage/delta":
        buffers.setdefault(params.get("itemId"), []).append(params.get("delta") or "")
        return None
    if method == "item/completed":
        item = params.get("item") or {}
        if item.get("type") == "agentMessage":
            text = item.get("text") or "".join(buffers.pop(item.get("id"), []))
            return ("assistant", {"text": text}) if text else None
        return None
    if method == "turn/completed":
        turn = params.get("turn") or {}
        status = turn.get("status")
        if status == "completed":
            return ("done", {"turn_id": turn.get("id")})
        if status == "interrupted":
            return ("interrupted", {"turn_id": turn.get("id")})
        error = turn.get("error") or {}
        return ("failed", {"turn_id": turn.get("id"), "reason": error.get("message") or status})
    if method and method.endswith("requestApproval"):
        return ("permission", {"reason": method})
    return None


class Client:
    """The launcher's JSON-RPC connection to the shared app-server."""

    def __init__(self, port, token, log):
        self.ws = WebSocket("127.0.0.1", port, headers={"Authorization": f"Bearer {token}"})
        self.log = log
        self.ids = itertools.count(1)
        self.replies = {}
        self.cond = threading.Condition()
        self.buffers = {}
        self.thread_id = None
        self.turn_id = None
        threading.Thread(target=self._read, daemon=True).start()
        self.call("initialize", {"clientInfo": {"name": "cdx", "title": "cdx remote control", "version": "1"}})
        self.ws.send_text(json.dumps({"method": "initialized"}))

    def _read(self):
        try:
            while True:
                message = json.loads(self.ws.recv_text())
                if "id" in message and "method" not in message:
                    with self.cond:
                        self.replies[message["id"]] = message
                        self.cond.notify_all()
                    continue
                if message.get("method") == "turn/started":
                    self.turn_id = ((message.get("params") or {}).get("turn") or {}).get("id")
                mapped = map_notification(message, self.buffers)
                if mapped:
                    self.log.append(mapped[0], source="remote", **mapped[1])
        except (WebSocketClosed, OSError, ValueError):
            with self.cond:
                self.replies["closed"] = True
                self.cond.notify_all()

    def call(self, method, params, timeout=30):
        request_id = next(self.ids)
        self.ws.send_text(json.dumps({"id": request_id, "method": method, "params": params}))
        end = time.time() + timeout
        with self.cond:
            while request_id not in self.replies:
                remaining = end - time.time()
                if remaining <= 0 or self.replies.get("closed"):
                    raise RuntimeError(f"{method}: no answer from codex app-server")
                self.cond.wait(remaining)
            reply = self.replies.pop(request_id)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result") or {}

    def tui_thread(self, cwd):
        """(thread id, subscribed) for the thread the TUI has loaded.

        A thread rooted at the session cwd wins. A fresh TUI thread has no
        rollout until its first turn, so it cannot be resumed (subscribed to)
        yet; it still accepts turn/start, and send() subscribes right after.
        """
        ids = [entry if isinstance(entry, str) else entry.get("id")
               for entry in self.call("thread/loaded/list", {}).get("data") or []]
        best, unresumed = None, None
        for thread_id in ids:
            try:
                thread = self.call("thread/resume", {"threadId": thread_id}).get("thread") or {}
            except RuntimeError:
                unresumed = unresumed or thread_id
                continue
            roots = [env.get("cwd") for env in thread.get("environments") or []] + [thread.get("cwd")]
            if best is None or cwd in roots:
                best = thread_id
                if cwd in roots:
                    break
        return (best, True) if best else (unresumed, False)

    def send(self, text, cwd):
        subscribed = True
        if not self.thread_id:
            self.thread_id, subscribed = self.tui_thread(cwd)
        if not self.thread_id:
            raise NoThreadYet("the TUI has no thread loaded yet (still on a startup screen?)")
        self.log.append("queued", source="remote", prompt=text)
        self.call("turn/start", {"threadId": self.thread_id, "input": [{"type": "text", "text": text}]})
        if not subscribed:
            self.log.append("working", source="remote")
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    self.call("thread/resume", {"threadId": self.thread_id}, timeout=5)
                    break
                except RuntimeError:
                    time.sleep(POLL_SECONDS)

    def interrupt(self):
        if self.thread_id and self.turn_id:
            self.call("turn/interrupt", {"threadId": self.thread_id, "turnId": self.turn_id})

    def close(self):
        self.ws.close()


def run(*, base_dir, name, cwd, codex_command, server_env, start_tui):
    """Serve the session until the TUI exits. Returns the TUI's returncode.

    start_tui(port, token) -> Popen of the TUI attached with tui_args().
    """
    log = EventLog(base_dir, name)
    token = secrets.token_urlsafe(32)
    token_file = os.path.join(state_dir(base_dir), f"{name}@{os.getpid()}.codex-token")
    _write_private(token_file, token)
    port = free_port()
    server = subprocess.Popen(server_argv(codex_command, port, token_file), env=server_env, cwd=cwd,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client, pending, tui = None, [], None
    try:
        deadline = time.time() + STARTUP_SECONDS
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if server.poll() is not None or time.time() > deadline:
                    raise RuntimeError("codex app-server did not start") from None
                time.sleep(POLL_SECONDS)
        tui = start_tui(port, token)
        # The pids let `cdx conversation --pid <tui>` find the rollout the server writes.
        with Endpoint(base_dir, name, status_fn=lambda: {"mode": "shared", "pending": len(pending)},
                      extra={"tui_pid": tui.pid, "server_pid": server.pid}) as endpoint:
            log.append("ready")
            while tui.poll() is None:
                try:
                    request = endpoint.requests.get(timeout=POLL_SECONDS)
                except queue.Empty:
                    request = None
                if request:
                    pending.append({**request, "since": time.time()})
                if not pending:
                    continue
                current = pending[0]
                try:
                    client = client or Client(port, token, log)
                    if current["op"] == "send":
                        client.send(current["text"], cwd)
                    else:
                        client.interrupt()
                    pending.pop(0)
                except NoThreadYet as error:
                    # The TUI is still on a startup screen (trust, update, hooks):
                    # keep the message until it opens its thread, within a bound.
                    if time.time() - current["since"] > THREAD_WAIT_SECONDS:
                        log.append("failed", source="remote", reason=str(error))
                        pending.pop(0)
                    else:
                        time.sleep(1)
                except (RuntimeError, OSError, WebSocketClosed) as error:
                    log.append("failed", source="remote", reason=str(error))
                    pending.pop(0)
            log.append("ended", returncode=tui.returncode)
            return tui.returncode
    except LaunchTerminated as stop:
        if tui is not None and tui.poll() is None:
            tui.terminate()
            try:
                tui.wait(timeout=10)
            except subprocess.TimeoutExpired:
                tui.kill()
        log.append("ended", returncode=stop.returncode, signal=stop.signal)
        return stop.returncode
    finally:
        if client:
            client.close()
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        try:
            os.unlink(token_file)
        except OSError:
            pass
