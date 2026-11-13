import base64
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

from src import remote_claude, remote_codex, remote_control, ws_client
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
            result["code"] = remote_claude.run_loop(
                base_dir=self.base_dir, name="work", conversation_id="conv-1", auth_home=self.dir,
                start_tui=start_tui, remote_argv=lambda resumed: [sys.executable, self.stream, str(resumed)],
                remote_options={}, agent_record=lambda: self.record, out=self.output.append,
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

    def test_the_tui_exiting_without_messages_ends_the_launch(self):
        thread, result = self._run(exit_after=1)
        thread.join(15)
        self.assertEqual(result.get("code"), 0)
        self.assertEqual([e["event"] for e in self._events()], ["ready", "ended"])


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
