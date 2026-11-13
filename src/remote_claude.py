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

The loop itself is provider-agnostic: a small adapter says when the TUI is idle,
which piloted command to run, and how to read and write its stream. Claude's
adapter is below; Antigravity's is in remote_antigravity.
"""

import glob
import json
import os
import queue
import re
import subprocess
import sys
import threading

from .remote_control import Endpoint, EventLog, LaunchTerminated, remote_err_file

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


class ClaudeAdapter:
    """What the switch loop needs to know about Claude Code."""

    def __init__(self, conversation_id, auth_home, remote_argv, agent_record):
        self.conversation_id = conversation_id
        self.auth_home, self.remote_argv, self.agent_record = auth_home, remote_argv, agent_record

    def _transcript(self):
        return transcript_path(self.auth_home, self.conversation_id)

    def tui_idle(self):
        return tui_idle(self.agent_record(), self._transcript())

    def argv(self):
        return self.remote_argv(self._transcript() is not None)

    def map_event(self, event):
        return map_stream_event(event)

    def user_message(self, text):
        return {"type": "user", "message": {"role": "user", "content": text}}

    # The CLI ignored the stream-json interrupt control request in a live test
    # (2026-11-13, Claude Code 2.1.323). Like Happy, whose SDK abort ends the
    # child process, stop the run; the next message resumes the conversation.
    interrupt_ends_run = True

    def interrupt(self, proc, _write):
        proc.terminate()


# Replies a terminal sends on its own (focus in/out, colour-scheme and cursor
# reports, OSC/DCS answers) are not keypresses: an HQ xterm emits them when the
# operator merely opens the terminal view.
_TERMINAL_REPLY = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|P[^\x1b]*\x1b\\)")


def typed(data):
    """Whether raw terminal input holds a real keypress, not only terminal replies."""
    return bool(_TERMINAL_REPLY.sub(b"", data))


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
            try:
                termios.tcsetattr(self.stream.fileno(), termios.TCSADRAIN, self._saved)
            except (termios.error, OSError):  # the terminal is gone (hangup)
                pass
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
            return typed(os.read(self.stream.fileno(), 1024))
        return False


class RemoteRun:
    """One piloted stream-json process fed with user messages."""

    def __init__(self, argv, options, log, out, adapter, stderr_path=None):
        self.log, self.out, self.adapter = log, out, adapter
        # As in Happy (slopus/happy claudeRemote.ts): one message per turn, the
        # next one is written only after the `result` that ends the current turn.
        self.thinking = False
        self.waiting = []
        self.interrupted = False
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
            return self.thinking or bool(self.waiting)

    def last_error(self):
        try:
            with open(self.stderr_path, encoding="utf-8", errors="replace") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            return lines[-1][:500] if lines else "no error output"
        except (OSError, TypeError):
            return "no error output"

    def send(self, text):
        self.log.append("working", source="remote", prompt=text)
        self.out(f"\n› {text}\n")
        with self.lock:
            if self.thinking:
                self.waiting.append(text)
                return
            self.thinking = True
        self._write(self.adapter.user_message(text))

    def carry(self, texts):
        """Deliver messages a stopped run had not written yet, already logged and shown."""
        texts = list(texts)
        if not texts:
            return
        with self.lock:
            self.waiting.extend(texts[1:])
            self.thinking = True
        self._write(self.adapter.user_message(texts[0]))

    def interrupt(self):
        self.interrupted = True
        self.adapter.interrupt(self.proc, self._write)

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
            mapped = self.adapter.map_event(event)
            if not mapped:
                continue
            kind, fields = mapped
            self.log.append(kind, source="remote", **fields)
            if kind == "assistant":
                self.out(f"● {fields['text']}\n")
            elif kind in ("done", "interrupted", "failed"):
                with self.lock:
                    nxt = self.waiting.pop(0) if self.waiting else None
                    self.thinking = nxt is not None
                if nxt is not None:
                    self._write(self.adapter.user_message(nxt))
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


def run_loop(*, base_dir, name, adapter, start_tui, remote_options, out=None, keys=None):
    """Drive the conversation until the TUI exits on its own. Returns its returncode.

    start_tui(resume: bool) -> Popen; adapter: ClaudeAdapter or another provider's
    (tui_idle(), argv(), map_event(), user_message(), interrupt() and a
    conversation_id attribute that may stay None until the provider names it).
    """
    out = out or (lambda text: (sys.stdout.write(text), sys.stdout.flush()))
    log = EventLog(base_dir, name)
    mode = {"value": "local"}
    pending = []

    def status():
        return {"mode": mode["value"], "pending": len(pending), "conversation_id": adapter.conversation_id}

    child = run = None
    try:
        with Endpoint(base_dir, name, status_fn=status) as endpoint, (keys or KeyWatcher()) as watcher:
            log.append("ready", conversation_id=adapter.conversation_id)
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
                    if pending and (code is not None or adapter.tui_idle()):
                        _stop_tui(child)
                        break
                # Remote: stream-json on the same conversation until a key is pressed.
                mode["value"] = "remote"
                out("\n[cdx] Remote control: this session is driven by `cdx send`. "
                    "Press any key to return to the terminal.\n")

                def start_run():
                    return RemoteRun(adapter.argv(), remote_options, log, out, adapter,
                                     stderr_path=remote_err_file(base_dir, name, os.getpid()))

                def restart(old):
                    # A provider that stops a turn by ending its run (Antigravity)
                    # stays remote: the next message goes to a new run.
                    try:
                        old.proc.wait(timeout=TUI_STOP_GRACE_SECONDS)
                    except subprocess.TimeoutExpired:
                        old.proc.kill()
                    old.reader.join(5)
                    if old.thinking:  # killed before it could report the turn
                        log.append("interrupted", source="remote")
                    old.close()
                    new = start_run()
                    new.carry(old.waiting)
                    return new

                ends_on_interrupt = getattr(adapter, "interrupt_ends_run", False)
                run = start_run()
                for text in pending:
                    run.send(text)
                pending.clear()
                leaving = False
                while True:
                    if run.proc.poll() is not None:
                        if not (run.interrupted and ends_on_interrupt):
                            log.append("failed", source="remote", reason=f"exit {run.proc.returncode}")
                            break
                        if leaving:
                            break
                        run = restart(run)
                    if watcher.pressed() and not leaving:
                        leaving = True
                        out("[cdx] Returning to the terminal after the current turn.\n")
                    try:
                        request = endpoint.requests.get(timeout=POLL_SECONDS)
                    except queue.Empty:
                        request = None
                    if request and request["op"] == "send":
                        if run.interrupted and ends_on_interrupt:
                            run = restart(run)
                        run.send(request["text"])
                    elif request and request["op"] == "interrupt":
                        run.interrupt()
                        log.append("interrupt_requested", source="remote")
                    if leaving and not run.busy():
                        break
                run.close()
                resume = True
                log.append("local")
    except LaunchTerminated as stop:
        # The terminal closed (SIGHUP) or the launcher was asked to stop: the
        # endpoint has removed its files; stop what is still running and say so.
        for proc in (child, run and run.proc):
            if proc is not None:
                _stop_tui(proc)
        log.append("ended", returncode=stop.returncode, signal=stop.signal)
        return stop.returncode
