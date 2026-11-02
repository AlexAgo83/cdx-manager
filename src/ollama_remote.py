"""Worker-owned Ollama relay and a text-only HTTP client, shipped over SSH."""

import http.client
import http.server
import json
import os
import pathlib
import signal
import socketserver
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager

OLLAMA_HOST = '127.0.0.1'
OLLAMA_PORT = 11434
MAX_BODY = 8 * 1024 * 1024

CLIENT = r'''
import http.client
import json
import socket
import sys

class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(300)
        self.sock.connect(sys.argv[1])

try:
    payload = json.load(sys.stdin)
    def request(path, body):
        connection = Connection('localhost', timeout=300)
        try:
            connection.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            data = json.loads(response.read(8 * 1024 * 1024))
            if response.status != 200 or not isinstance(data, dict) or data.get('error'):
                raise ValueError('Ollama request failed')
            return data
        finally:
            connection.close()
    model = payload['model']
    info = request('/api/show', {'model': model})
    if info.get('remote_host') or info.get('remote_model'):
        raise ValueError('A local model is required')
    if 'capabilities' in info and 'completion' not in info['capabilities']:
        raise ValueError('Text completion is required')
    if payload.get('probe'):
        print('ollama-http')
    else:
        result = request('/api/chat', {'model': model, 'stream': False,
                         'messages': [{'role': 'user', 'content': payload['prompt']}]})
        if result.get('done') is not True or not isinstance(result.get('message', {}).get('content'), str):
            raise ValueError('Incomplete Ollama response')
        print(json.dumps(result))
except Exception:
    print('Ollama text generation failed: check the local model and worker loopback API.', file=sys.stderr)
    sys.exit(1)
'''


@contextmanager
def relay(directory, model):
    """Expose only a fixed loopback destination and a fixed model over a private socket."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid body')
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or data.get('model') != model:
                    raise ValueError('Invalid model')
                if self.path == '/api/show':
                    allowed = set(data) == {'model'}
                elif self.path == '/api/chat':
                    messages = data.get('messages')
                    allowed = (set(data) == {'model', 'stream', 'messages'} and data.get('stream') is False
                               and isinstance(messages, list) and len(messages) == 1
                               and isinstance(messages[0], dict) and set(messages[0]) == {'role', 'content'}
                               and messages[0]['role'] == 'user' and isinstance(messages[0]['content'], str))
                else:
                    allowed = False
                if not allowed:
                    raise ValueError('Forbidden call')
            except (ValueError, TypeError, OSError):
                self.send_error(403, 'Relay call refused')
                return
            connection = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=300)
            try:
                # No proxies, redirects, forwarded headers or client-selected destination.
                connection.request('POST', self.path, json.dumps(data), {'Content-Type': 'application/json'})
                response = connection.getresponse()
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise ValueError('Oversized response')
                self.send_response(response.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (OSError, ValueError, http.client.HTTPException):
                self.send_error(502, 'Ollama unavailable')
            finally:
                connection.close()

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    path = str(pathlib.Path(directory) / 'api.sock')
    with Server(path, Handler) as server:
        os.chmod(path, 0o600)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield path
        finally:
            server.shutdown()
            thread.join()


def run(payload, sandbox_source, probe=False):
    """Run a single HTTP completion; no shell tools or model files enter the sandbox."""
    model = payload.get('model')
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError('Remote Ollama requires an installed model')
    with tempfile.TemporaryDirectory(prefix='cdx-ollama-') as directory, relay(directory, model) as path:
        command = [sys.executable, '-I', '-c', CLIENT, path]
        env = None
        if payload.get('isolate_workspace'):
            namespace = {'__name__': 'cdx_workspace_sandbox'}
            exec(compile(sandbox_source, 'workspace_sandbox.py', 'exec'), namespace)
            command = ['python3', '-I', '-c', CLIENT, '/run/cdx-ollama/api.sock']
            command, env = namespace['sandbox_command'](
                command, pathlib.Path(payload['cwd']), network=False, writable=False,
                provider='ollama', ollama_relay=directory)
        child = subprocess.Popen(command, cwd=payload['cwd'], env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)

        def stop(*_):
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        def disconnected():
            while os.read(0, 1):
                pass
            stop()

        previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        if not probe:
            threading.Thread(target=disconnected, daemon=True).start()
        try:
            output, error = child.communicate(json.dumps({'model': model, 'prompt': payload.get('prompt'), 'probe': probe}).encode(),
                                              timeout=30 if probe else None)
            if probe:
                sys.stdout.write(output.decode())
            else:
                print(json.dumps({'stream': 'stdout', 'data': output.decode()}), flush=True)
            sys.stderr.write(error.decode())
            return child.returncode
        finally:
            stop()
            child.wait()
            for sig, handler in previous.items():
                signal.signal(sig, handler)
