"""Remote control of a live interactive session through provider protocols.

A remote chat client used to type into the session's terminal and read its
screen. Here the cdx launcher that owns the provider process listens on a
private per-session endpoint instead: `cdx send` hands it a message, and the
launcher delivers it through the provider's own programmatic interface
(Claude: a stream-json `--resume` run on the same conversation; Antigravity: a
stream-json `--conversation` run; Codex: a turn on the thread its TUI shares
through `codex app-server`). Every turn state and
reply it observes is appended to a per-session event log.

The endpoint is a loopback TCP listener guarded by a per-session secret on
every platform: Unix sockets are not available on all Windows setups, and one
transport keeps the three platforms on the same code path. The secret lives in
an owner-only file and never travels in argv or in the event log.
"""

import glob
import hmac
import json
import os
import queue
import secrets
import signal
import socket
import sys
import threading
from datetime import datetime, timezone

from .errors import CdxError
from .session_helpers import _process_is_running

SEND_USAGE = "Usage: cdx send <name> [--pid PID] <text> | - | --stdin | --interrupt | --status [--json]"
MAX_REQUEST_BYTES = 256 * 1024
EVENT_TEXT_LIMIT = 20000


def remote_control_enabled(session):
    return ((session or {}).get("launch") or {}).get("remote_control") is True


def state_dir(base_dir):
    path = os.path.join(base_dir, "state", "remote")
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name != "nt":
        os.chmod(path, 0o700)
    return path


def endpoint_file(base_dir, name, pid=None):
    """`<name>.endpoint.json` points at the most recent live launch; each launch
    also owns `<name>@<launcher pid>.endpoint.json` ('@' never occurs in a name)."""
    return os.path.join(state_dir(base_dir), f"{name}@{pid}.endpoint.json" if pid else f"{name}.endpoint.json")


def _read_endpoint(path):
    try:
        with open(path, encoding="utf-8") as handle:
            info = json.load(handle)
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def live_endpoints(base_dir, name):
    """Endpoint records of this session's live launches, most recent first."""
    found = []
    for path in glob.glob(os.path.join(glob.escape(os.path.join(base_dir, "state", "remote")), f"{glob.escape(name)}@*.endpoint.json")):
        info = _read_endpoint(path)
        if info and os.path.basename(path) == f"{name}@{info.get('pid')}.endpoint.json" and _process_is_running(info.get("pid")):
            try:
                found.append((os.path.getmtime(path), path, info))
            except OSError:
                continue  # The launch ended while it was listed.
    return [(path, info) for _, path, info in sorted(found, key=lambda item: item[0], reverse=True)]


def resolve_endpoint(base_dir, name, pid=None):
    """(path, info) of the launch to reach: launcher (or TUI) `pid`'s, else the most recent live one."""
    if pid is not None:
        path = endpoint_file(base_dir, name, pid)
        info = _read_endpoint(path)
        if info:
            return path, info
        # Runtime records list the provider process: accept a Codex TUI pid too.
        return next(((path, info) for path, info in live_endpoints(base_dir, name)
                     if info.get("tui_pid") == pid), (None, None))
    # The last launch to start wrote the pointer; it wins while it lives.
    path = endpoint_file(base_dir, name)
    info = _read_endpoint(path)
    live = live_endpoints(base_dir, name)
    if info and (_process_is_running(info.get("pid")) or not live):
        return path, info
    return live[0] if live else (None, None)


def events_file(base_dir, name, pid=None):
    """`<name>.events.jsonl` is shared by every launch of the session; each launch
    also writes the same lines to its own `<name>@<launcher pid>.events.jsonl`."""
    return os.path.join(state_dir(base_dir), f"{name}@{pid}.events.jsonl" if pid else f"{name}.events.jsonl")


def remote_err_file(base_dir, name, pid):
    return os.path.join(state_dir(base_dir), f"{name}@{pid}.remote.err")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_private(path, text):
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)


class EventLog:
    """Append-only JSON lines; one writer per launch (its launcher), many readers.

    Every line carries the launcher `pid`, so lines of concurrent launches in the
    shared log can be told apart; the per-launch log holds only this launch's.
    """

    def __init__(self, base_dir, name):
        self.pid = os.getpid()
        self.path = events_file(base_dir, name)
        self.launch_path = events_file(base_dir, name, self.pid)
        self.lock = threading.Lock()
        # A reused pid starts a fresh per-launch log rather than extending a dead launch's.
        _write_private(self.launch_path, "")

    def append(self, kind, **fields):
        entry = {"at": _now(), "event": kind, "pid": self.pid}
        for key, value in fields.items():
            if isinstance(value, str) and len(value) > EVENT_TEXT_LIMIT:
                value = value[:EVENT_TEXT_LIMIT]
            if value is not None:
                entry[key] = value
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self.lock:
            for path in (self.path, self.launch_path):
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as handle:
                    handle.write(line)
        return entry


class LaunchTerminated(BaseException):
    """SIGHUP (terminal closed) or SIGTERM reached the launcher while its endpoint was up.

    A BaseException so provider loops' `except Exception` cannot swallow it; the
    launcher stops its children, logs `ended`, and the endpoint removes its files.
    """

    def __init__(self, signum):
        super().__init__(signum)
        self.signal = signal.Signals(signum).name
        self.returncode = 128 + signum


def _terminate_handlers():
    def stop(signum, _frame):
        # Ignore repeats so the cleanup this starts is not cut short by a second signal.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        raise LaunchTerminated(signum)

    previous = {}
    for sig in filter(None, (getattr(signal, "SIGHUP", None), signal.SIGTERM)):
        try:
            previous[sig] = signal.signal(sig, stop)
        except (ValueError, OSError):  # not the main thread
            pass
    return previous


class Endpoint:
    """The launcher side: accept authenticated requests and queue them."""

    def __init__(self, base_dir, name, status_fn=None, extra=None):
        self.base_dir, self.name = base_dir, name
        self.pid = os.getpid()
        self.extra = extra or {}
        self.secret = secrets.token_urlsafe(32)
        self.requests = queue.Queue()
        self.status_fn = status_fn or (lambda: {})
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(8)
        self.port = self._server.getsockname()[1]
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._serve, name=f"cdx-remote-{name}", daemon=True)

    def __enter__(self):
        record = json.dumps({**self.extra, "port": self.port, "secret": self.secret, "pid": self.pid})
        _write_private(endpoint_file(self.base_dir, self.name, self.pid), record)
        _write_private(endpoint_file(self.base_dir, self.name), record)
        self._thread.start()
        self._handlers = _terminate_handlers()
        return self

    def __exit__(self, *exc):
        for sig, handler in self._handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, TypeError):  # TypeError: a handler set outside Python
                pass
        self._stopped.set()
        try:
            self._server.close()
        except OSError:
            pass
        try:
            os.unlink(endpoint_file(self.base_dir, self.name, self.pid))
        except OSError:
            pass
        # Only touch the pointer while it is ours: hand it to the most recent
        # other live launch, or remove it when none is left.
        pointer = endpoint_file(self.base_dir, self.name)
        if (_read_endpoint(pointer) or {}).get("pid") == self.pid:
            others = [info for _, info in live_endpoints(self.base_dir, self.name) if info.get("pid") != self.pid]
            try:
                if others:
                    _write_private(pointer, json.dumps(others[0]))
                else:
                    os.unlink(pointer)
            except OSError:
                pass
        return False

    def _serve(self):
        while not self._stopped.is_set():
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        with conn:
            conn.settimeout(10)
            try:
                request = json.loads(_read_line(conn))
            except (OSError, ValueError) as error:
                _reply(conn, {"ok": False, "error": f"bad request: {error}"})
                return
            if not hmac.compare_digest(str(request.get("secret", "")), self.secret):
                _reply(conn, {"ok": False, "error": "unauthorized"})
                return
            op = request.get("op")
            if op == "status":
                _reply(conn, {"ok": True, **self.status_fn()})
            elif op == "send" and isinstance(request.get("text"), str) and request["text"].strip():
                self.requests.put({"op": "send", "text": request["text"]})
                _reply(conn, {"ok": True, "queued": True})
            elif op == "interrupt":
                self.requests.put({"op": "interrupt"})
                _reply(conn, {"ok": True})
            else:
                _reply(conn, {"ok": False, "error": "unknown operation"})


def _read_line(conn):
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
    return data.decode("utf-8")


def _reply(conn, payload):
    try:
        conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    except OSError:
        pass


def request(base_dir, name, op, text=None, timeout=10, pid=None):
    """The client side used by `cdx send`."""
    _, info = resolve_endpoint(base_dir, name, pid)
    if not info:
        if pid is not None:
            raise CdxError(f"No remote-control launch of {name} with launcher pid {pid}.")
        raise CdxError(f"Session {name} is not running with remote control. "
                       f"Turn it on with: cdx set {name} --remote-control on, then relaunch it.")
    payload = {"op": op, "secret": info.get("secret")}
    if text is not None:
        payload["text"] = text
    try:
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=timeout) as conn:
            conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            answer = json.loads(_read_line(conn) or "{}")
    except (OSError, ValueError, KeyError) as error:
        raise CdxError(f"Session {name} did not answer on its control endpoint ({error}). Is it still running?") from error
    if not answer.get("ok"):
        raise CdxError(f"Session {name} refused the request: {answer.get('error', 'unknown error')}")
    return answer


def handle_send(rest, ctx):
    from .cli_helpers import _json_success, _write_json

    json_flag = "--json" in rest
    args = [arg for arg in rest if arg != "--json"]
    if not args:
        raise CdxError(SEND_USAGE)
    name, tail = args[0], args[1:]
    pid = None
    if tail[:1] == ["--pid"]:
        try:
            pid = int(tail[1])
        except (IndexError, ValueError):
            raise CdxError(SEND_USAGE) from None
        tail = tail[2:]
    base_dir = ctx["service"]["base_dir"]

    if tail == ["--interrupt"]:
        answer, message = request(base_dir, name, "interrupt", pid=pid), f"Interrupt sent to {name}."
    elif tail == ["--status"]:
        answer, message = request(base_dir, name, "status", pid=pid), f"Status of {name}."
    elif tail in (["-"], ["--stdin"]):
        # Keeps the message out of argv, which other local users can read.
        text = (ctx.get("prompt_stdin") or sys.stdin).read()
        if not text.strip():
            raise CdxError("cdx send: stdin was empty.")
        answer, message = request(base_dir, name, "send", text, pid=pid), f"Message queued for {name}."
    elif tail and not tail[0].startswith("--"):
        answer, message = request(base_dir, name, "send", " ".join(tail), pid=pid), f"Message queued for {name}."
    else:
        raise CdxError(SEND_USAGE)
    if json_flag:
        _write_json(ctx, _json_success("send", message, **{k: v for k, v in answer.items() if k != "ok"}))
    else:
        details = {k: v for k, v in answer.items() if k not in ("ok", "queued")}
        ctx["out"](message + (f" {json.dumps(details)}" if details else "") + "\n")
    return 0
