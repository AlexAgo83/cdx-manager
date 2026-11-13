"""Minimal WebSocket client (RFC 6455) for a loopback JSON-RPC peer.

Just enough for `codex app-server`: text frames, fragmentation, ping/pong and
close, over plain TCP to 127.0.0.1. Kept in the standard library so cdx gains
no dependency for one local connection.
"""

import base64
import hashlib
import os
import socket
import struct
import threading

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketClosed(Exception):
    pass


class WebSocket:
    def __init__(self, host, port, path="/", headers=None, timeout=10):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.send_lock = threading.Lock()
        key = base64.b64encode(os.urandom(16)).decode()
        lines = [f"GET {path} HTTP/1.1", f"Host: {host}:{port}", "Upgrade: websocket", "Connection: Upgrade",
                 f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13"]
        lines += [f"{name}: {value}" for name, value in (headers or {}).items()]
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketClosed("handshake closed")
            response += chunk
        head, self._buffer = response.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise WebSocketClosed(f"handshake refused: {status.decode(errors='replace')}")
        expected = base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest())
        if expected not in head:
            raise WebSocketClosed("handshake accept mismatch")
        self.sock.settimeout(None)

    def _recv_exact(self, size):
        while len(self._buffer) < size:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise WebSocketClosed("connection closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data

    def _send_frame(self, opcode, payload):
        header = bytes([0x80 | opcode])
        size = len(payload)
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", size)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        with self.send_lock:
            self.sock.sendall(header + mask + masked)

    def send_text(self, text):
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self):
        """The next complete text message; answers pings, raises on close."""
        parts = []
        while True:
            first, second = self._recv_exact(2)
            opcode, final = first & 0x0F, bool(first & 0x80)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self._recv_exact(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if second & 0x80 else None
            payload = self._recv_exact(size)
            if mask:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise WebSocketClosed("closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode in (0x1, 0x0):
                parts.append(payload)
                if final:
                    return b"".join(parts).decode("utf-8")

    def close(self):
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
