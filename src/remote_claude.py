"""Claude remote control: switch one conversation between the TUI and a stream-json run.

Claude Code has no attach mode, so a second writer cannot share a running TUI.
The launcher therefore owns the conversation and moves it between two modes:

- local: the normal TUI. A message from `cdx send` waits until the TUI turn is
  idle, then the TUI is stopped;
- remote: `claude -p --resume <id> --input-format stream-json
  --output-format stream-json` on the same conversation, fed from the control
  endpoint. Any key in the terminal returns to the TUI with `--resume` once the
  current remote turn has finished.

Both modes write the same transcript file, so nothing is lost across switches.
"""

import glob
import json
import os
import queue
import subprocess
import sys
import threading
import time

from .remote_control import Endpoint, EventLog, state_dir

IDLE_STATES = ("done", "waiting", "limit", "failed")
INTERRUPTED_MARKER = "[Request interrupted by user"
POLL_SECONDS = 0.25
TUI_STOP_GRACE_SECONDS = 10


def transcript_path(auth_home, conversation_id):
    matches = glob.glob(os.path.join(auth_home, ".claude", "projects", "*", f"{conversation_id}.jsonl"))
    return max(matches, key=os.path.getmtime) if matches else None


def _last_line(path):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            lines = handle.read().splitlines()
        return lines[-1].decode("utf-8", "replace") if lines else ""
    except OSError:
        return ""


def tui_idle(agent_record, transcript):
    """Whether the TUI can be stopped without cutting a turn.

    The hook record is the main signal. An Esc interrupt fires no Stop hook, so
    a record still saying "working" counts as idle when the transcript's last
    entry is the interrupt marker.
    """
    state = (agent_record or {}).get("state")
    if state != "working":
        return True
    return bool(transcript) and INTERRUPTED_MARKER in _last_line(transcript)


def map_stream_event(event):
    """(event kind, fields) for the event log, or None for events it ignores."""
    kind = event.get("type")
    if kind == "assistant":
        text = "".join(part.get("text", "") for part in (event.get("message") or {}).get("content") or []
                       if isinstance(part, dict) and part.get("type") == "text")
        return ("assistant", {"text": text}) if text else None
    if kind == "result":
        subtype = event.get("subtype") or ""
        if subtype == "success" and not event.get("is_error"):
            return ("done", {"text": event.get("result")})
        if "interrupt" in subtype or event.get("stop_reason") == "interrupted":
            return ("interrupted", {})
        return ("failed", {"reason": subtype or "error", "text": event.get("result")})
    return None


class KeyWatcher:
    """Report a keypress on the controlling terminal, on POSIX and Windows."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdin
        self._saved = None

    def __enter__(self):
        if os.name != "nt" and self.stream.isatty():
            import termios
            import tty
            fd = self.stream.fileno()
            self._saved = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        return self

    def __exit__(self, *exc):
        if self._saved is not None:
            import termios
            termios.tcsetattr(self.stream.fileno(), termios.TCSADRAIN, self._saved)
        return False

    def pressed(self):
        if not self.stream.isatty():
            return False
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                while msvcrt.kbhit():
                    msvcrt.getwch()
                return True
            return False
        import select
        ready, _, _ = select.select([self.stream], [], [], 0)
        if ready:
            os.read(self.stream.fileno(), 1024)
            return True
        return False


class RemoteRun:
    """One `claude -p` stream-json process fed with user messages."""

    def __init__(self, argv, options, log, out, stderr_path=None):
        self.log, self.out = log, out
        self.turns = 0
        self.lock = threading.Lock()
        self.stderr_path = stderr_path
        # stderr goes to a private file: it is the only trace of a run that dies
        # before writing any stream-json event.
        stderr = open(stderr_path, "w", encoding="utf-8") if stderr_path else subprocess.DEVNULL
        if stderr_path:
            stderr.write("cdx remote run: " + " ".join(argv) + "\n")
            stderr.flush()
        # On Windows a child sharing the console can read its input and swallow the
        # keypress that returns the session to the terminal; give it its own.
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=stderr, text=True, encoding="utf-8", **flags, **options)
        if stderr_path:
            stderr.close()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def busy(self):
        with self.lock:
            return self.turns > 0

    def last_error(self):
        try:
            with open(self.stderr_path, encoding="utf-8", errors="replace") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            return lines[-1][:500] if lines else "no error output"
        except (OSError, TypeError):
            return "no error output"

    def send(self, text):
        with self.lock:
            self.turns += 1
        self.log.append("working", source="remote", prompt=text)
        self.out(f"\n› {text}\n")
        self._write({"type": "user", "message": {"role": "user", "content": text}})

    def interrupt(self):
        self._write({"type": "control_request", "request_id": f"cdx-{time.time_ns()}",
                     "request": {"subtype": "interrupt"}})

    def _write(self, payload):
        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def _read(self):
        for line in self.proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            mapped = map_stream_event(event)
            if not mapped:
                continue
            kind, fields = mapped
            self.log.append(kind, source="remote", **fields)
            if kind == "assistant":
                self.out(f"● {fields['text']}\n")
            elif kind in ("done", "interrupted", "failed"):
                with self.lock:
                    self.turns = max(0, self.turns - 1)
                if kind != "done":
                    self.out(f"[cdx] remote turn {kind}\n")

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            return self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            return self.proc.wait()


def _stop_tui(child):
    if child.poll() is not None:
        return
    if os.name == "nt":
        # The TUI often runs behind an npm .cmd shim: terminating the shim leaves
        # claude.exe alive, still reading the console. Stop the whole tree; the
        # turn is idle, so the transcript is already written.
        subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    child.terminate()
    try:
        child.wait(timeout=TUI_STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def run_loop(*, base_dir, name, conversation_id, auth_home, start_tui, remote_argv,
             remote_options, agent_record, out=None, keys=None):
    """Drive the conversation until the TUI exits on its own. Returns its returncode.

    start_tui(resume: bool) -> Popen; remote_argv(resume: bool) -> argv list;
    agent_record() -> the session's hook record (or None).
    """
    out = out or (lambda text: (sys.stdout.write(text), sys.stdout.flush()))
    log = EventLog(base_dir, name)
    mode = {"value": "local"}
    pending = []

    def status():
        return {"mode": mode["value"], "pending": len(pending), "conversation_id": conversation_id}

    with Endpoint(base_dir, name, status_fn=status) as endpoint, (keys or KeyWatcher()) as watcher:
        log.append("ready", conversation_id=conversation_id)
        resume = False
        while True:
            # Local: the TUI owns the terminal until a message can take over.
            mode["value"] = "local"
            child = start_tui(resume)
            while True:
                code = child.poll()
                if code is not None and not pending:
                    log.append("ended", returncode=code)
                    return code
                try:
                    request = endpoint.requests.get(timeout=POLL_SECONDS)
                except queue.Empty:
                    request = None
                if request and request["op"] == "send":
                    pending.append(request["text"])
                    log.append("queued", source="remote", prompt=request["text"])
                if pending and (code is not None or tui_idle(
                        agent_record(), transcript_path(auth_home, conversation_id))):
                    _stop_tui(child)
                    break
            # Remote: stream-json on the same conversation until a key is pressed.
            mode["value"] = "remote"
            out("\n[cdx] Remote control: this session is driven by `cdx send`. "
                "Press any key to return to the terminal.\n")
            resumed = transcript_path(auth_home, conversation_id) is not None
            run = RemoteRun(remote_argv(resumed), remote_options, log, out,
                            stderr_path=os.path.join(state_dir(base_dir), f"{name}.remote.err"))
            for text in pending:
                run.send(text)
            pending.clear()
            leaving = False
            while True:
                if run.proc.poll() is not None:
                    log.append("failed", source="remote", reason=f"exit {run.proc.returncode}")
                    break
                if watcher.pressed():
                    leaving = True
                    out("[cdx] Returning to the terminal after the current turn.\n")
                try:
                    request = endpoint.requests.get(timeout=POLL_SECONDS)
                except queue.Empty:
                    request = None
                if request and request["op"] == "send":
                    run.send(request["text"])
                elif request and request["op"] == "interrupt":
                    run.interrupt()
                    log.append("interrupt_requested", source="remote")
                if leaving and not run.busy():
                    break
            run.close()
            resume = True
            log.append("local")
