"""Remote text generation uses a fixed worker API without credentials or terminal parsing."""

import http.client
import http.server
import json
import pathlib
import socket
import sys
import threading
from unittest import mock

import pytest
from cli_test_support import CliTestBase
from test_remote_run_py import worker  # noqa: F401

from src import ollama_remote, remote_run, workspace_sandbox
from src.cli import main
from src.run_registry import RunRegistry, final_message

pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux remote worker')


@pytest.fixture
def api(monkeypatch):
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, body, dict(self.headers)))
            if body['model'] == 'missing':
                self.send_response(404)
                result = {'error': 'model not found'}
            else:
                self.send_response(200)
                result = ({'capabilities': ['completion']} if self.path == '/api/show' else
                          {'model': 'local:latest', 'done': True, 'message': {'role': 'assistant', 'content': 'Generated text'},
                           'prompt_eval_count': 17, 'eval_count': 9})
            if body['model'] == 'cloud':
                result = {'remote_host': 'https://example.invalid', 'remote_model': 'cloud'}
            elif body['model'] == 'embedding':
                result = {'capabilities': ['embedding']}
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

    with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        monkeypatch.setattr(ollama_remote, 'OLLAMA_PORT', server.server_port)
        original = remote_run.worker_input

        def frame():
            return original().replace(b'OLLAMA_PORT = 11434', f'OLLAMA_PORT = {server.server_port}'.encode())

        monkeypatch.setattr(remote_run, 'worker_input', frame)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            yield calls
        finally:
            server.shutdown()
            thread.join()


class RemoteOllamaTests(CliTestBase):
    @pytest.fixture(autouse=True)
    def fixture(self, worker, api, tmp_path, monkeypatch):  # noqa: F811
        self.directory = tmp_path
        self.calls = api
        self.monkeypatch = monkeypatch

    def test_success_usage_and_prompt_content(self):
        self._success()

    def test_isolated_success(self):
        original_frame = remote_run.worker_input
        def frame():
            source = json.loads(original_frame())
            first, rest = source.split('\n', 1)
            import ast
            sandbox = ast.literal_eval(first.partition(' = ')[2])
            sandbox += FAKE_SANDBOX
            return json.dumps('SANDBOX_SOURCE = ' + repr(sandbox) + '\n' + rest).encode() + b'\n'
        self.monkeypatch.setattr(remote_run, 'worker_input', frame)
        self._success(isolated=True)
        captured = json.loads((self.directory / 'sandbox-call.json').read_text())
        assert captured['provider'] == 'ollama'
        assert captured['network'] is False and captured['writable'] is False
        assert not pathlib.Path(captured['ollama_relay']).exists()

    def _success(self, isolated=False):
        from src.session_service import create_session_service
        service = create_session_service({'base_dir': str(self.directory / 'cdx')})
        service['create_session']('local', 'ollama')
        service['set_launch_settings']('local', {'model': 'local:latest'})
        prompt = self.directory / 'controller-only.txt'
        prompt.write_text('Explain this code.\nDo not run tools.')
        out = self.make_io()
        with mock.patch('src.remote_run.temporary_auth', side_effect=AssertionError('No authentication')):
            assert main(['run', 'local', '--remote', 'worker', '--cwd', str(self.directory),
                         '--prompt-file', str(prompt), *(['--isolate-workspace'] if isolated else []), '--json'], self.make_run_ctx(out, service)) == 0
        result = json.loads(out['stdout'].getvalue())
        assert result['result'] == 'Generated text'
        assert result['execution_mode'] == 'text_generation'
        assert 'does not edit' in result['execution_note']
        assert result['usage']['input_tokens'] == result['usage']['prompt_eval_count'] == 17
        assert result['usage']['output_tokens'] == result['usage']['eval_count'] == 9
        assert result['usage']['total_tokens'] == 26
        record = RunRegistry(service['base_dir']).get(result['run_id'])
        assert final_message(record) == 'Generated text'
        chat = [body for path, body, _ in self.calls if path == '/api/chat']
        assert chat == [{'model': 'local:latest', 'stream': False,
                         'messages': [{'role': 'user', 'content': prompt.read_text()}]}]
        assert all('Authorization' not in headers for _, _, headers in self.calls)
        argv = (self.directory / 'argv').read_text()
        assert 'Explain this code' not in argv and str(prompt) not in argv

    def test_missing_model(self):
        from src.errors import CdxError
        with pytest.raises(CdxError, match='Remote Ollama unavailable'):
            remote_run.preflight('worker', provider='ollama', model='missing', cwd=str(self.directory))
        assert all(path == '/api/show' for path, _, _ in self.calls)

    def test_cloud_and_embedding_models_are_refused(self):
        from src.errors import CdxError
        for model in ('cloud', 'embedding'):
            with pytest.raises(CdxError, match='Remote Ollama unavailable'):
                remote_run.preflight('worker', provider='ollama', model=model, cwd=str(self.directory))
        assert all(path == '/api/show' for path, _, _ in self.calls)

    def test_unreachable_server(self):
        from src.errors import CdxError
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.monkeypatch.setattr(remote_run, 'worker_input',
                                 lambda: original_worker_input().replace(b'OLLAMA_PORT = 11434', f'OLLAMA_PORT = {port}'.encode()))
        with pytest.raises(CdxError, match='Remote Ollama unavailable'):
            remote_run.preflight('worker', provider='ollama', model='local', cwd=str(self.directory))



original_worker_input = remote_run.worker_input


@pytest.mark.parametrize('path,body', [
    ('/api/pull', {'model': 'local'}), ('/api/delete', {'model': 'local'}),
    ('/api/push', {'model': 'local'}), ('http://192.168.1.1/api/show', {'model': 'local'}),
    ('/api/show?url=http://localhost', {'model': 'local'}), ('/api/show', {'model': 'other'}),
    ('/api/chat', {'model': 'local', 'stream': True, 'messages': []}),
    ('/api/show', {'model': 'local', 'destination': 'http://localhost'}),
])
def test_relay_refuses_calls(api, tmp_path, path, body):
    class Connection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(socket_path)

    with ollama_remote.relay(tmp_path, 'local') as socket_path:
        connection = Connection('localhost')
        connection.request('POST', path, json.dumps(body))
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
    assert not api


def test_sandbox_ollama_has_only_relay_mount(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_sandbox, 'CACHE', tmp_path / 'cache')
    monkeypatch.setattr(workspace_sandbox.shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    command, env = workspace_sandbox.sandbox_command(
        ['python3', '-c', 'pass'], tmp_path, network=False, provider='ollama', ollama_relay='/private/relay')
    assert command[0] == '/usr/bin/bwrap'
    assert '--unshare-all' in command
    assert '/private/relay' in command and '/run/cdx-ollama' in command
    assert '.ollama' not in ' '.join(command)
    assert 'OLLAMA_HOST' not in env
    with pytest.raises(RuntimeError, match='supervisor-owned relay'):
        workspace_sandbox.sandbox_command(['python3'], tmp_path, network=False, provider='ollama')


def test_isolated_worker_uses_relay_and_read_only_tree(tmp_path, api, monkeypatch):
    real_source = pathlib.Path('src/workspace_sandbox.py').read_text()
    # Replace confinement only: exercise the actual worker, HTTP client and relay.
    source = real_source + FAKE_SANDBOX
    payload = {'provider': 'ollama', 'model': 'local', 'prompt': 'Content', 'cwd': str(tmp_path), 'isolate_workspace': True}
    # Probe mode also exercises the exact isolated launch path, without inference.
    assert ollama_remote.run(payload, source, probe=True) == 0
    captured = json.loads((tmp_path / 'sandbox-call.json').read_text())
    assert captured['provider'] == 'ollama'
    assert captured['network'] is False and captured['writable'] is False
    assert not pathlib.Path(captured['ollama_relay']).exists()


FAKE_SANDBOX = """
def sandbox_command(command, tree, **kwargs):
    import json
    Path(tree, 'sandbox-call.json').write_text(json.dumps(kwargs))
    command[-1] = kwargs['ollama_relay'] + '/api.sock'
    return command, clean_env(os.environ)
"""
