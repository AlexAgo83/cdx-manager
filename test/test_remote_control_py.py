import base64
import hashlib
import json
import os
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

from src import remote_antigravity, remote_claude, remote_codex, remote_control, ws_client
from src.errors import CdxError

FAKE_TUI = textwrap.dedent("""
    import sys, time
    # Stands in for the Claude TUI: runs until stopped, or exits when told to.
    if len(sys.argv) > 1 and sys.argv[1] == "exit":
        sys.exit(0)
    while True:
        time.sleep(0.1)
""")

FAKE_STREAM = textwrap.dedent("""
    import json, sys
    # Stands in for `claude -p --input-format stream-json`: one reply per user line.
    print(json.dumps({"type": "system", "subtype": "init", "argv": sys.argv[1:]}), flush=True)
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "control_request":
            print(json.dumps({"type": "result", "subtype": "error_during_execution", "stop_reason": "interrupted"}), flush=True)
            continue
        text = message["message"]["content"]
        print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "echo:" + text}]}}), flush=True)
        print(json.dumps({"type": "result", "subtype": "success", "result": "echo:" + text}), flush=True)
""")

FAKE_MERGING_STREAM = textwrap.dedent("""
    import json, os, select, sys, time
    # Like the real CLI: user lines that arrive while a turn runs join that turn,
    # so several sends can end with a single result.
    print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
    pending = b""
    while True:
        chunk = os.read(0, 65536)
        if not chunk:
            break
        pending += chunk
        time.sleep(0.5)  # the turn is running
        while select.select([0], [], [], 0)[0]:
            more = os.read(0, 65536)
            if not more:
                break
            pending += more
        lines, _, pending = pending.rpartition(b"\\n")
        texts = [json.loads(l)["message"]["content"] for l in lines.split(b"\\n") if l.strip()]
        reply = "echo:" + "+".join(texts)
        print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}}), flush=True)
        print(json.dumps({"type": "result", "subtype": "success", "result": reply}), flush=True)
""")


FAKE_AGY_STREAM = textwrap.dedent("""
    import json, signal, sys
    # Stands in for `agy --input-format stream-json --output-format stream-json -p=`.
    # A runner may start the suite with SIGINT ignored; agy (Go) handles it regardless.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    args = sys.argv[1:]
    conversation = args[args.index("--conversation") + 1] if "--conversation" in args else "agy-new"
    def emit(kind, **body):
        print(json.dumps({"event": kind, "conversation_id": conversation, kind: {"conversation_id": conversation, **body}}), flush=True)
    emit("init", argv=args)
    step = 0
    try:
        for line in sys.stdin:
            message = json.loads(line)
            assert message["event"] == "user"
            text = message["message"]["content"]
            if text == "slow":
                import time
                time.sleep(60)
            emit("step_update", step_index=step + 1, state="ACTIVE", step_type="agent_response", text_delta="echo:")
            emit("step_update", step_index=step + 1, state="DONE", step_type="agent_response", text_delta=text + "\\n")
            emit("result", status="SUCCESS", response="echo:" + text + "\\n")
            step += 2
    except KeyboardInterrupt:
        emit("result", status="ERROR", error="interrupted", finished_reason="interrupted")
        sys.exit(1)
""")

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _script(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    return path


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()

    def test_send_status_and_interrupt_reach_the_launcher(self):
        with remote_control.Endpoint(self.base_dir, "work", status_fn=lambda: {"mode": "local"}) as endpoint:
            self.assertEqual(remote_control.request(self.base_dir, "work", "status")["mode"], "local")
            self.assertTrue(remote_control.request(self.base_dir, "work", "send", "hello")["queued"])
            remote_control.request(self.base_dir, "work", "interrupt")
            self.assertEqual(endpoint.requests.get(timeout=2), {"op": "send", "text": "hello"})
            self.assertEqual(endpoint.requests.get(timeout=2), {"op": "interrupt"})
        self.assertFalse(os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))

    def test_a_request_without_the_secret_is_refused(self):
        with remote_control.Endpoint(self.base_dir, "work") as endpoint:
            with socket.create_connection(("127.0.0.1", endpoint.port), timeout=5) as conn:
                conn.sendall(b'{"op": "send", "text": "x", "secret": "guess"}\n')
                answer = json.loads(remote_control._read_line(conn))
            self.assertEqual(answer, {"ok": False, "error": "unauthorized"})
            self.assertTrue(endpoint.requests.empty())

    def test_secret_file_is_private_and_absent_from_events(self):
        with remote_control.Endpoint(self.base_dir, "work") as endpoint:
            path = remote_control.endpoint_file(self.base_dir, "work")
            if os.name != "nt":
                self.assertEqual(os.stat(path).st_mode & 0o077, 0)
                self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o077, 0)
            remote_control.EventLog(self.base_dir, "work").append("ready")
            with open(remote_control.events_file(self.base_dir, "work"), encoding="utf-8") as handle:
                self.assertNotIn(endpoint.secret, handle.read())

    def test_send_reads_the_message_from_stdin(self):
        import io
        out = []
        with remote_control.Endpoint(self.base_dir, "work") as endpoint:
            for flag in ("-", "--stdin"):
                ctx = {"service": {"base_dir": self.base_dir}, "out": out.append,
                       "prompt_stdin": io.StringIO("line one\n--not a flag\n")}
                self.assertEqual(remote_control.handle_send(["work", flag], ctx), 0)
                self.assertEqual(endpoint.requests.get(timeout=2),
                                 {"op": "send", "text": "line one\n--not a flag\n"})
            with self.assertRaises(CdxError):
                remote_control.handle_send(["work", "-"], {"service": {"base_dir": self.base_dir},
                                                           "out": out.append, "prompt_stdin": io.StringIO(" \n")})
            remote_control.handle_send(["work", "hello", "there"], {"service": {"base_dir": self.base_dir}, "out": out.append})
            self.assertEqual(endpoint.requests.get(timeout=2), {"op": "send", "text": "hello there"})
        self.assertEqual(out, ["Message queued for work.\n"] * 3)

    def test_endpoint_file_carries_the_launch_pids(self):
        with remote_control.Endpoint(self.base_dir, "work", extra={"tui_pid": 5, "server_pid": 6}):
            with open(remote_control.endpoint_file(self.base_dir, "work"), encoding="utf-8") as handle:
                info = json.load(handle)
        self.assertEqual((info["tui_pid"], info["server_pid"], info["pid"]), (5, 6, os.getpid()))

    def test_concurrent_launches_keep_their_own_endpoints(self):
        from unittest import mock

        alive = {101, 202}
        first = remote_control.Endpoint(self.base_dir, "work", status_fn=lambda: {"who": "first"})
        second = remote_control.Endpoint(self.base_dir, "work", status_fn=lambda: {"who": "second"}, extra={"tui_pid": 7})
        first.pid, second.pid = 101, 202
        out = []
        ctx = {"service": {"base_dir": self.base_dir}, "out": out.append}
        with mock.patch.object(remote_control, "_process_is_running", side_effect=lambda pid: pid in alive):
            with first:
                with second:
                    self.assertEqual(remote_control.request(self.base_dir, "work", "status")["who"], "second")
                    self.assertEqual(remote_control.request(self.base_dir, "work", "status", pid=101)["who"], "first")
                    self.assertEqual(remote_control.request(self.base_dir, "work", "status", pid=7)["who"], "second")
                    remote_control.handle_send(["work", "--pid", "101", "hi"], ctx)
                    self.assertEqual(first.requests.get(timeout=2), {"op": "send", "text": "hi"})
                    self.assertTrue(second.requests.empty())
                # The pointer goes back to the launch that is still running.
                self.assertEqual(remote_control.request(self.base_dir, "work", "status")["who"], "first")
                with open(remote_control.endpoint_file(self.base_dir, "work"), encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle)["pid"], 101)
                self.assertFalse(os.path.exists(remote_control.endpoint_file(self.base_dir, "work", 202)))
                # A crashed newest launch leaves a stale pointer: the live one is still reached.
                remote_control._write_private(remote_control.endpoint_file(self.base_dir, "work"),
                                              json.dumps({"pid": 303, "port": 1, "secret": "x"}))
                self.assertEqual(remote_control.request(self.base_dir, "work", "status")["who"], "first")
            self.assertEqual(os.listdir(remote_control.state_dir(self.base_dir)), ["work.endpoint.json"])
        with self.assertRaises(CdxError):
            remote_control.request(self.base_dir, "work", "status", pid=101)
        with self.assertRaises(CdxError):
            remote_control.handle_send(["work", "--pid", "x", "hi"], ctx)

    def test_concurrent_launches_tag_their_events_and_keep_their_own_logs(self):
        from unittest import mock

        logs = {}
        for pid in (101, 202):
            with mock.patch("os.getpid", return_value=pid):
                logs[pid] = remote_control.EventLog(self.base_dir, "work")
        logs[101].append("ready")
        logs[202].append("ready")
        logs[101].append("ended", returncode=0)

        def read(path):
            with open(path, encoding="utf-8") as handle:
                return [(entry["event"], entry["pid"]) for entry in map(json.loads, handle)]

        self.assertEqual(read(remote_control.events_file(self.base_dir, "work")),
                         [("ready", 101), ("ready", 202), ("ended", 101)])
        self.assertEqual(read(remote_control.events_file(self.base_dir, "work", 101)), [("ready", 101), ("ended", 101)])
        self.assertEqual(read(remote_control.events_file(self.base_dir, "work", 202)), [("ready", 202)])
        # A later launch that reuses a pid starts its own log afresh.
        with mock.patch("os.getpid", return_value=101):
            remote_control.EventLog(self.base_dir, "work").append("ready")
        self.assertEqual(read(remote_control.events_file(self.base_dir, "work", 101)), [("ready", 101)])
        if os.name != "nt":
            self.assertEqual(os.stat(remote_control.events_file(self.base_dir, "work", 202)).st_mode & 0o077, 0)

    def test_send_to_a_session_without_endpoint_names_the_setting(self):
        with self.assertRaises(CdxError) as caught:
            remote_control.request(self.base_dir, "work", "send", "x")
        self.assertIn("--remote-control on", str(caught.exception))


class ClaudeSignalTests(unittest.TestCase):
    def test_idle_follows_the_hook_record_and_the_interrupt_marker(self):
        directory = tempfile.mkdtemp()
        transcript = _script(directory, "t.jsonl", '{"type":"user"}\n')
        self.assertTrue(remote_claude.tui_idle(None, transcript))
        self.assertTrue(remote_claude.tui_idle({"state": "done"}, transcript))
        self.assertFalse(remote_claude.tui_idle({"state": "working"}, transcript))
        with open(transcript, "a", encoding="utf-8") as handle:
            handle.write('{"type":"user","message":{"content":[{"text":"[Request interrupted by user]"}]}}\n')
        self.assertTrue(remote_claude.tui_idle({"state": "working"}, transcript))

    def test_stream_events_map_to_turn_states(self):
        self.assertEqual(remote_claude.map_stream_event(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}), ("assistant", {"text": "hi"}))
        self.assertEqual(remote_claude.map_stream_event({"type": "result", "subtype": "success", "result": "hi"}),
                         ("done", {"text": "hi"}))
        self.assertEqual(remote_claude.map_stream_event(
            {"type": "result", "subtype": "error_during_execution", "stop_reason": "interrupted"})[0], "interrupted")
        self.assertEqual(remote_claude.map_stream_event({"type": "result", "subtype": "error_max_turns"})[0], "failed")
        self.assertIsNone(remote_claude.map_stream_event({"type": "system", "subtype": "init"}))


class FakeKeys:
    """Press a key once `when()` turns true."""

    def __init__(self, when):
        self.when, self.done = when, False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def pressed(self):
        if not self.done and self.when():
            self.done = True
            return True
        return False


class ClaudeLoopTests(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.dir = tempfile.mkdtemp()
        self.tui = _script(self.dir, "tui.py", FAKE_TUI)
        self.stream = _script(self.dir, "stream.py", FAKE_STREAM)
        self.tui_starts = []
        self.record = {"state": "working"}
        self.output = []

    def _events(self):
        try:
            with open(remote_control.events_file(self.base_dir, "work"), encoding="utf-8") as handle:
                return [json.loads(line) for line in handle]
        except OSError:
            return []

    def _run(self, exit_after=2):
        def start_tui(resume):
            self.tui_starts.append(resume)
            # The second TUI (back from remote mode) exits on its own: the operator quit.
            mode = "exit" if len(self.tui_starts) >= exit_after else "run"
            return subprocess.Popen([sys.executable, self.tui, mode])

        result = {}

        def target():
            adapter = remote_claude.ClaudeAdapter(
                "conv-1", self.dir, lambda resumed: [sys.executable, self.stream, str(resumed)], lambda: self.record)
            result["code"] = remote_claude.run_loop(
                base_dir=self.base_dir, name="work", adapter=adapter,
                start_tui=start_tui, remote_options={}, out=self.output.append,
                keys=FakeKeys(lambda: any(e["event"] == "done" for e in self._events())),
            )

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread, result

    def _wait(self, predicate, seconds=20):
        end = time.time() + seconds
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.1)
        self.fail(f"timed out; events={self._events()}")

    def test_a_message_waits_for_an_idle_turn_runs_remotely_then_returns_to_the_tui(self):
        thread, result = self._run()
        self._wait(lambda: os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))
        remote_control.request(self.base_dir, "work", "send", "ping")
        self._wait(lambda: any(e["event"] == "queued" for e in self._events()))
        time.sleep(0.6)
        self.assertNotIn("working", [e["event"] for e in self._events()], "a busy TUI turn is never cut")
        self.record = {"state": "done"}
        thread.join(30)
        self.assertEqual(result.get("code"), 0)
        events = [e["event"] for e in self._events()]
        self.assertEqual(events[:3], ["ready", "queued", "working"])
        self.assertIn("done", events)
        self.assertEqual(self.tui_starts, [False, True], "the TUI comes back with --resume")
        replies = [e.get("text") for e in self._events() if e["event"] == "assistant"]
        self.assertEqual(replies, ["echo:ping"])
        self.assertTrue(any("› ping" in line for line in self.output))

    def test_messages_sent_during_a_turn_still_return_to_the_tui(self):
        # 2026-11-13: two messages sent mid-turn were folded into one result, the
        # turn counter never reached zero and the session never left remote mode.
        self.stream = _script(self.dir, "merging.py", FAKE_MERGING_STREAM)
        thread, result = self._run()
        self._wait(lambda: os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))
        for text in ("one", "two", "three"):
            remote_control.request(self.base_dir, "work", "send", text)
        self._wait(lambda: sum(e["event"] == "queued" for e in self._events()) == 3)
        self.record = {"state": "done"}
        thread.join(30)
        self.assertEqual(result.get("code"), 0, "the key press returns to the TUI")
        replies = [e.get("text") for e in self._events() if e["event"] == "assistant"]
        self.assertEqual(replies, ["echo:one", "echo:two", "echo:three"], "one message per turn, as in Happy")

    def test_the_tui_exiting_without_messages_ends_the_launch(self):
        thread, result = self._run(exit_after=1)
        thread.join(15)
        self.assertEqual(result.get("code"), 0)
        self.assertEqual([e["event"] for e in self._events()], ["ready", "ended"])


def _agy_index(auth_home, rows):
    """A conversation_summaries.db with agy 1.5.8's columns that the adapter reads."""
    import sqlite3

    path = remote_antigravity.summaries_path(auth_home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS conversation_summaries (conversation_id text PRIMARY KEY, "
                           "last_modified_time datetime NOT NULL, workspace_uris text NOT NULL, "
                           "status text NOT NULL DEFAULT '', not_fully_idle numeric NOT NULL DEFAULT false)")
        connection.executemany("INSERT OR REPLACE INTO conversation_summaries VALUES (?, ?, ?, ?, ?)", rows)


class AntigravitySignalTests(unittest.TestCase):
    def test_recorded_stream_maps_to_turn_states(self):
        adapter = remote_antigravity.AntigravityAdapter("/nowhere", "/work/project", "agy", [])
        with open(os.path.join(FIXTURES, "antigravity_stream_json.jsonl"), encoding="utf-8") as handle:
            mapped = [m for m in (adapter.map_event(json.loads(line)) for line in handle) if m]
        self.assertEqual(mapped, [
            ("assistant", {"text": "OK"}), ("done", {"text": "OK"}),
            ("assistant", {"text": "KIWI7"}), ("done", {"text": "KIWI7"}),
            ("interrupted", {}),
        ])
        self.assertEqual(adapter.conversation_id, "181c9c61-e8d6-40e1-b37a-71da1ca669f9", "the first id sticks")
        self.assertEqual(adapter.map_event({"event": "result", "result": {"status": "ERROR", "error": "quota",
                                                                           "finished_reason": "error"}}),
                         ("failed", {"reason": "error", "text": "quota"}))

    def test_the_tui_conversation_is_the_newest_in_its_directory_since_launch(self):
        from datetime import datetime, timezone

        home, work = tempfile.mkdtemp(), tempfile.mkdtemp()
        adapter = remote_antigravity.AntigravityAdapter(home, work, "agy", ["--sandbox"],
                                                        since=datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc))
        self.assertIsNone(adapter.discover(), "no index yet: agy has not written a conversation")
        self.assertTrue(adapter.tui_idle())
        self.assertEqual(adapter.argv(), ["agy", "--sandbox", "--input-format", "stream-json",
                                          "--output-format", "stream-json", "-p="])
        uri = json.dumps([pathlib.Path(work).as_uri()])
        _agy_index(home, [
            ("older", "2026-11-13 09:59:59.9+00:00", uri, remote_antigravity.IDLE_STATUS, 0),
            ("elsewhere", "2026-11-13 10:05:00.1+00:00", json.dumps(["file:///other"]), "", 0),
            ("mine", "2026-11-13 10:01:00.5+00:00", uri, "CASCADE_RUN_STATUS_RUNNING", 0),
        ])
        self.assertEqual(adapter.discover(), "mine")
        self.assertFalse(adapter.tui_idle(), "a running turn is never cut")
        _agy_index(home, [("mine", "2026-11-13 10:02:00+00:00", uri, remote_antigravity.IDLE_STATUS, 1)])
        self.assertFalse(adapter.tui_idle(), "not fully idle yet")
        _agy_index(home, [("mine", "2026-11-13 10:02:00+00:00", uri, remote_antigravity.IDLE_STATUS, 0)])
        self.assertTrue(adapter.tui_idle())
        self.assertEqual(adapter.argv()[:4], ["agy", "--sandbox", "--conversation", "mine"])


class AntigravityLoopTests(ClaudeLoopTests):
    def test_messages_sent_during_a_turn_still_return_to_the_tui(self):
        self.skipTest("Claude stream-json behaviour")

    """The same switch loop with the Antigravity adapter and a fake agy."""

    def setUp(self):
        super().setUp()
        self.stream = _script(self.dir, "agy.py", FAKE_AGY_STREAM)
        self.adapter = remote_antigravity.AntigravityAdapter(self.dir, self.dir, sys.executable, [self.stream])

    def _run(self, exit_after=2, keys_when=None):
        def start_tui(resume):
            self.tui_starts.append(self.adapter.conversation_id if resume else None)
            mode = "exit" if len(self.tui_starts) >= exit_after else "run"
            return subprocess.Popen([sys.executable, self.tui, mode])

        result = {}

        def target():
            result["code"] = remote_claude.run_loop(
                base_dir=self.base_dir, name="work", adapter=self.adapter, start_tui=start_tui,
                remote_options={}, out=self.output.append,
                keys=FakeKeys(keys_when or (lambda: any(e["event"] == "done" for e in self._events()))),
            )

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread, result

    def test_a_message_waits_for_an_idle_turn_runs_remotely_then_returns_to_the_tui(self):
        uri = json.dumps([pathlib.Path(self.dir).as_uri()])
        stamp = time.strftime("%Y-%m-%d %H:%M:%S+00:00", time.gmtime(time.time() + 5))
        _agy_index(self.dir, [("agy-tui", stamp, uri, "CASCADE_RUN_STATUS_RUNNING", 0)])
        thread, result = self._run()
        self._wait(lambda: os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))
        remote_control.request(self.base_dir, "work", "send", "ping")
        self._wait(lambda: any(e["event"] == "queued" for e in self._events()))
        time.sleep(0.6)
        self.assertNotIn("working", [e["event"] for e in self._events()], "a busy TUI turn is never cut")
        _agy_index(self.dir, [("agy-tui", stamp, uri, remote_antigravity.IDLE_STATUS, 0)])
        thread.join(30)
        self.assertEqual(result.get("code"), 0)
        events = self._events()
        self.assertEqual([e["event"] for e in events][:3], ["ready", "queued", "working"])
        self.assertEqual([e.get("text") for e in events if e["event"] == "assistant"], ["echo:ping"])
        self.assertEqual(self.tui_starts, [None, "agy-tui"], "the TUI comes back on the same conversation")

    def test_a_message_to_a_fresh_tui_names_the_conversation_from_the_run(self):
        thread, result = self._run()
        self._wait(lambda: os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))
        remote_control.request(self.base_dir, "work", "send", "ping")
        thread.join(30)
        self.assertEqual(result.get("code"), 0)
        self.assertEqual(self.tui_starts, [None, "agy-new"])

    @unittest.skipIf(os.name == "nt", "SIGINT delivery to a child differs on Windows")
    def test_an_interrupt_ends_the_turn_and_the_next_message_reaches_a_new_run(self):
        thread, result = self._run(keys_when=lambda: [e["event"] for e in self._events()].count("done") == 1)
        self._wait(lambda: os.path.exists(remote_control.endpoint_file(self.base_dir, "work")))
        remote_control.request(self.base_dir, "work", "send", "slow")
        self._wait(lambda: any(e["event"] == "working" for e in self._events()))
        time.sleep(1)
        remote_control.request(self.base_dir, "work", "interrupt")
        self._wait(lambda: any(e["event"] == "interrupted" for e in self._events()))
        remote_control.request(self.base_dir, "work", "send", "again")
        thread.join(30)
        self.assertEqual(result.get("code"), 0)
        events = [e["event"] for e in self._events()]
        self.assertNotIn("failed", events)
        self.assertEqual([e.get("text") for e in self._events() if e["event"] == "assistant"], ["echo:again"])
        with open(remote_control.remote_err_file(self.base_dir, "work", os.getpid()), encoding="utf-8") as handle:
            self.assertIn("--conversation agy-new", handle.readline(), "the new run continues the conversation")


SIGNAL_LAUNCHER = textwrap.dedent("""
    import os, subprocess, sys
    sys.path.insert(0, sys.argv[1])
    from src import remote_claude, remote_codex
    provider, base_dir, tui, child_pids, fake = sys.argv[2:]

    class Keys:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def pressed(self):
            return False

    def spawn(*_):
        child = subprocess.Popen([sys.executable, tui, "run"])
        with open(child_pids, "a", encoding="utf-8") as handle:
            handle.write(f"{child.pid}\\n")
        return child

    if provider == "claude":
        adapter = remote_claude.ClaudeAdapter("conv-1", base_dir, lambda resumed: [sys.executable, fake],
                                              lambda: {"state": "working"})
        code = remote_claude.run_loop(base_dir=base_dir, name="work", adapter=adapter, start_tui=spawn,
                                      remote_options={}, out=lambda text: None, keys=Keys())
    else:
        code = remote_codex.run(base_dir=base_dir, name="work", cwd=base_dir, codex_command=fake,
                                server_env=None, start_tui=spawn)
    sys.exit(code)
""")

FAKE_APP_SERVER = textwrap.dedent("""\
    #!/usr/bin/env python3
    import socket, sys, time
    # Stands in for `codex app-server --listen ws://127.0.0.1:PORT`: accepts and idles.
    port = int(sys.argv[sys.argv.index("--listen") + 1].rsplit(":", 1)[1])
    server = socket.create_server(("127.0.0.1", port))
    while True:
        time.sleep(0.1)
""")


@unittest.skipIf(os.name == "nt", "closing the hosting terminal is a POSIX signal (SIGHUP/SIGTERM)")
class LauncherSignalTests(unittest.TestCase):
    def _launch_and_signal(self, provider, sig):
        import signal

        base_dir, work = tempfile.mkdtemp(), tempfile.mkdtemp()
        tui = _script(work, "tui.py", FAKE_TUI)
        child_pids = os.path.join(work, "children")
        fake = _script(work, "app-server", FAKE_APP_SERVER)
        os.chmod(fake, 0o755)
        launcher = _script(work, "launcher.py", SIGNAL_LAUNCHER)
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # This test process is the other live launch the pointer must return to.
        with remote_control.Endpoint(base_dir, "work"):
            proc = subprocess.Popen([sys.executable, launcher, repo, provider, base_dir, tui, child_pids, fake])
            try:
                own = remote_control.endpoint_file(base_dir, "work", proc.pid)
                end = time.time() + 20
                while not (os.path.exists(own) and os.path.exists(child_pids)) and time.time() < end:
                    time.sleep(0.1)
                with open(remote_control.endpoint_file(base_dir, "work"), encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle)["pid"], proc.pid, "the new launch owns the pointer")
                proc.send_signal(sig)
                self.assertEqual(proc.wait(30), 128 + sig)
            finally:
                if proc.poll() is None:
                    proc.kill()
            self.assertFalse(os.path.exists(own))
            self.assertFalse(any(path.endswith((".codex-token", ".tmp")) for path in os.listdir(remote_control.state_dir(base_dir))))
            with open(remote_control.endpoint_file(base_dir, "work"), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["pid"], os.getpid(), "the pointer goes back to the live launch")
        with open(remote_control.events_file(base_dir, "work", proc.pid), encoding="utf-8") as handle:
            last = json.loads(handle.readlines()[-1])
        self.assertEqual((last["event"], last["pid"], last["signal"], last["returncode"]),
                         ("ended", proc.pid, signal.Signals(sig).name, 128 + sig))
        with open(child_pids, encoding="utf-8") as handle:
            for pid in map(int, handle.read().split()):
                with self.assertRaises(ProcessLookupError, msg="the launch's TUI is stopped"):
                    os.kill(pid, 0)

    def test_claude_launch_cleans_up_on_hangup_and_terminate(self):
        import signal

        for sig in (signal.SIGHUP, signal.SIGTERM):
            with self.subTest(sig=sig):
                self._launch_and_signal("claude", sig)

    def test_codex_launch_cleans_up_on_hangup(self):
        import signal

        self._launch_and_signal("codex", signal.SIGHUP)


class CodexMappingTests(unittest.TestCase):
    def test_notifications_map_to_turn_states_and_text(self):
        buffers = {}
        self.assertEqual(remote_codex.map_notification(
            {"method": "turn/started", "params": {"turn": {"id": "t1"}}}, buffers), ("working", {"turn_id": "t1"}))
        self.assertIsNone(remote_codex.map_notification(
            {"method": "item/agentMessage/delta", "params": {"itemId": "i1", "delta": "PAP"}}, buffers))
        remote_codex.map_notification({"method": "item/agentMessage/delta", "params": {"itemId": "i1", "delta": "AYE"}}, buffers)
        self.assertEqual(remote_codex.map_notification(
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "id": "i1"}}}, buffers),
            ("assistant", {"text": "PAPAYE"}))
        self.assertEqual(remote_codex.map_notification(
            {"method": "turn/completed", "params": {"turn": {"id": "t1", "status": "interrupted"}}}, buffers)[0], "interrupted")
        self.assertEqual(remote_codex.map_notification(
            {"method": "turn/completed", "params": {"turn": {"id": "t1", "status": "failed", "error": {"message": "x"}}}},
            buffers), ("failed", {"turn_id": "t1", "reason": "x"}))
        self.assertEqual(remote_codex.map_notification(
            {"method": "item/commandExecution/requestApproval", "params": {}}, buffers)[0], "permission")

    def test_tui_args_attach_with_a_token_from_the_environment(self):
        args = remote_codex.tui_args(["--cd", "/w"], 4242)
        self.assertEqual(args[-4:], ["--remote", "ws://127.0.0.1:4242", "--remote-auth-token-env", remote_codex.TOKEN_ENV])
        self.assertIn("capability-token", remote_codex.server_argv("codex", 4242, "/t"))


def _ws_echo_server():
    """A one-connection WebSocket server that checks the bearer token and echoes one message."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    seen = {}

    def serve():
        conn, _ = server.accept()
        head = b""
        while b"\r\n\r\n" not in head:
            head += conn.recv(4096)
        text = head.decode()
        seen["auth"] = "Authorization: Bearer tok" in text
        key = [line.split(": ", 1)[1] for line in text.split("\r\n") if line.lower().startswith("sec-websocket-key")][0]
        accept = base64.b64encode(hashlib.sha1((key + ws_client._GUID).encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        first, second = conn.recv(2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", conn.recv(2))[0]
        mask = conn.recv(4)
        payload = b""
        while len(payload) < size:
            payload += conn.recv(size - len(payload))
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        conn.sendall(bytes([0x89, 0]))  # a ping the client must answer transparently
        reply = b"echo:" + payload
        conn.sendall(bytes([0x81, 126]) + struct.pack("!H", len(reply)) + reply if len(reply) > 125
                     else bytes([0x81, len(reply)]) + reply)
        conn.recv(64)
        conn.close()
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1], seen


class WebSocketClientTests(unittest.TestCase):
    def test_roundtrip_with_bearer_token_ping_and_long_payload(self):
        port, seen = _ws_echo_server()
        ws = ws_client.WebSocket("127.0.0.1", port, headers={"Authorization": "Bearer tok"})
        message = json.dumps({"id": 1, "text": "x" * 300})
        ws.send_text(message)
        self.assertEqual(ws.recv_text(), "echo:" + message)
        ws.close()
        self.assertTrue(seen["auth"])


if __name__ == "__main__":
    unittest.main()


class AntigravityLaunchTests(unittest.TestCase):
    """provider_runtime hands an opted-in Antigravity launch to the switch loop."""

    def _session(self, home, remote=True):
        return {"name": "agy-demo", "provider": "antigravity", "authHome": home,
                "launch": {"remote_control": remote, "permission": "review"}}

    def test_only_an_opted_in_terminal_launch_is_taken_over(self):
        from unittest import mock

        from src import provider_runtime

        home, base = tempfile.mkdtemp(), tempfile.mkdtemp()
        with mock.patch.object(provider_runtime, "_stream_is_tty", return_value=True):
            plan = provider_runtime._remote_antigravity_plan(self._session(home), "launch", home, {}, base)
            self.assertIsNone(provider_runtime._remote_antigravity_plan(self._session(home, False), "launch", home, {}, base))
            self.assertIsNone(provider_runtime._remote_antigravity_plan(self._session(home), "login", home, {}, base))
        self.assertTrue(plan["command"].endswith("agy") or plan["command"] == "agy")
        self.assertEqual(plan["args"], ["--sandbox"])
        self.assertEqual(plan["options"]["cwd"], home)
        self.assertEqual(plan["options"]["env"]["HOME"], home)

    def test_the_tui_returns_on_the_conversation_the_loop_found(self):
        from unittest import mock

        from src import provider_runtime

        home, base = tempfile.mkdtemp(), tempfile.mkdtemp()
        spawned, seen = [], {}

        def fake_loop(**kwargs):
            adapter = kwargs["adapter"]
            seen["adapter"] = adapter
            kwargs["start_tui"](False)
            adapter.conversation_id = "conv-agy"
            kwargs["start_tui"](True)
            return 0

        with mock.patch.object(provider_runtime, "_stream_is_tty", return_value=True), \
                mock.patch.object(remote_claude, "run_loop", side_effect=fake_loop), \
                mock.patch.dict(os.environ, {"CDX_SCRIPT_ARGS": "", "CDX_SCRIPT_BIN": "script"}):
            provider_runtime._run_interactive_provider_process(
                self._session(home), "launch", spawn=lambda argv, **options: spawned.append(argv) or mock.Mock(pid=1),
                cwd=home, remote_base_dir=base)
        self.assertIsInstance(seen["adapter"], remote_antigravity.AntigravityAdapter)
        self.assertNotIn("--conversation", " ".join(spawned[0]))
        self.assertIn("--conversation conv-agy", " ".join(spawned[1]))
