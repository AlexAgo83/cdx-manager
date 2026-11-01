"""Remote execution with a local fake SSH and provider, never operator secrets."""

import base64
import json
import os
import pathlib
import signal
import subprocess
import time
from datetime import datetime, timezone
from unittest import mock

import pytest
from cli_test_support import CliTestBase

from src.cli import main
from src.cli_args import _parse_run_args
from src.commands.runs import _detached_child_argv
from src.errors import CdxError
from src.remote_run import needs_refresh, preflight, run_remote, temporary_auth
from src.run_registry import RunRegistry


def credential(now=None, age=0, lifetime=240 * 3600):
    now = time.time() if now is None else now
    body = base64.urlsafe_b64encode(json.dumps({'exp': now + lifetime}).encode()).decode().rstrip('=')
    return {'tokens': {'access_token': 'access.' + body + '.signature', 'id_token': 'expired-id-secret',
                       'account_id': 'account-identifier', 'refresh_token': 'ROTATING-SECRET-NEVER-SEND'},
            'last_refresh': datetime.fromtimestamp(now - age, timezone.utc).isoformat()}


@pytest.mark.parametrize(('age', 'lifetime', 'refresh'), [
    (7 * 86400, 86400, False), (7 * 86400 + 1, 86400, True),
    (0, 86400 - 1, True), (0, 86400 + 1, False),
])
def test_refresh_thresholds(tmp_path, age, lifetime, refresh):
    now = int(time.time())
    old = credential(now, age, lifetime)
    path = tmp_path / 'auth.json'
    path.write_text(json.dumps(old))
    assert needs_refresh(old, now) is refresh
    with mock.patch('src.remote_run.refresh_auth', side_effect=lambda home: path.write_text(json.dumps(credential(now)))) as probe:
        result = temporary_auth(str(tmp_path), now)
    assert probe.call_count == int(refresh)
    assert result['tokens']['refresh_token'] == ''
    assert old['tokens']['refresh_token'] not in json.dumps(result)
    assert set(result) == {'tokens', 'last_refresh'}
    assert set(result['tokens']) == {'access_token', 'id_token', 'account_id', 'refresh_token'}


def test_failed_refresh_aborts(tmp_path):
    (tmp_path / 'auth.json').write_text(json.dumps(credential(age=8 * 86400)))
    with mock.patch('src.remote_run.refresh_auth'), pytest.raises(CdxError, match='did not produce'):
        temporary_auth(str(tmp_path))


@pytest.fixture
def worker(tmp_path, monkeypatch):
    import uuid
    if not os.sys.platform.startswith("linux"):
        pytest.skip("The fake worker requires Linux memory-backed storage")
    name = 'cdx-test-remote-' + uuid.uuid4().hex
    root = pathlib.Path('/dev/shm') / (name + '-' + str(os.getuid()))
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    ssh = bindir / 'ssh'
    ssh.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ['FAKE_ARGV'], 'a') as f:
    f.write(json.dumps(sys.argv) + '\\n')
if os.environ.get('FAKE_MODE') == 'unreachable':
    sys.exit(255)
os.environ['FAKE_REMOTE'] = 'yes'
command = sys.argv[-1].replace('cdx-remote-', os.environ['FAKE_PREFIX'] + '-')
os.execl('/bin/sh', 'sh', '-c', command)
''')
    codex = bindir / 'codex'
    codex.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
if '--version' in sys.argv:
    print('codex-cli ' + ('0.other' if os.environ.get('FAKE_REMOTE') and os.environ.get('FAKE_MODE') == 'mismatch' else '0.166.0'))
    sys.exit(0)
home = pathlib.Path(os.environ['CODEX_HOME'])
auth = json.loads((home / 'auth.json').read_text())
assert str(home).startswith('/dev/shm/')
assert (home / 'auth.json').stat().st_mode & 0o777 == 0o600
assert home.stat().st_mode & 0o777 == 0o700
assert auth['tokens']['refresh_token'] == ''
assert 'cli_auth_credentials_store = "file"' in (home / 'config.toml').read_text()
assert not any(value in arg for value in auth['tokens'].values() if value for arg in sys.argv)
assert not any(value in item for value in auth['tokens'].values() if value for item in os.environ.values())
assert sys.stdin.read() == ''
pathlib.Path(os.environ['FAKE_HOME']).write_text(str(home))
print(auth['tokens']['access_token'], flush=True)
print(auth['tokens']['id_token'], file=sys.stderr, flush=True)
print(json.dumps({'type': 'thread.started', 'thread_id': 'remote-thread'}), flush=True)
sessions = home / 'sessions'
sessions.mkdir()
usage = {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 0}
(sessions / 'rollout.jsonl').write_text('\\n'.join(json.dumps(row) for row in [
    {'type': 'session_meta', 'payload': {'id': 'remote-thread'}},
    {'type': 'turn_context', 'payload': {'model': 'gpt-5.3-codex'}},
    {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': usage}}}
]) + '\\n')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 0}}), flush=True)
print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Remote completed'}}), flush=True)
if os.environ.get('FAKE_MODE') == 'long':
    time.sleep(60)
sys.exit(7 if os.environ.get('FAKE_MODE') == 'failure' else 0)
''')
    ssh.chmod(0o755)
    codex.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('FAKE_ARGV', str(tmp_path / 'argv'))
    monkeypatch.setenv('FAKE_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('FAKE_PREFIX', name)
    yield root
    import shutil
    shutil.rmtree(root, ignore_errors=True)


class RemoteCommandTests(CliTestBase):
    @pytest.fixture(autouse=True)
    def fixture(self, worker, tmp_path, monkeypatch):
        self.worker_root = worker
        self.directory = tmp_path
        self.monkeypatch = monkeypatch

    def setup_session(self):
        from src.session_service import create_session_service
        service = create_session_service({'base_dir': str(self.directory / 'cdx')})
        session = self._authenticated_codex_session(service)
        auth = credential()
        pathlib.Path(session['authHome'], 'auth.json').write_text(json.dumps(auth))
        return service, session, auth

    def test_registry_status_report_and_no_secrets(self):
        service, session, auth = self.setup_session()
        out = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work',
                     '--label', 'remote', '--json'], self.make_run_ctx(out, service)) == 0
        result = json.loads(out['stdout'].getvalue())
        record = RunRegistry(service['base_dir']).get(result['run_id'])
        assert record['status'] == 'succeeded'
        assert record['remote'] == 'worker'
        assert result['usage']['input_tokens'] == 10
        assert result['usage_model'] == 'gpt-5.3-codex'
        assert result['cost_usd'] is not None
        for action in ('run-status', 'run-report', 'run-tail'):
            output = self.make_io()
            assert main([action, result['run_id'], '--json'], self.make_run_ctx(output, service)) == 0
        persisted = out['stdout'].getvalue() + (self.directory / 'argv').read_text()
        for path in pathlib.Path(service['base_dir']).rglob('*'):
            if path.is_file() and path.name != 'auth.json':
                persisted += path.read_text(errors='replace')
        for value in auth['tokens'].values():
            assert value not in persisted
        assert json.loads(pathlib.Path(session['authHome'], 'auth.json').read_text()) == auth
        assert not list(self.worker_root.glob('run-*'))

    def test_failure_cleanup_and_no_retry(self):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', 'failure')
        out = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work', '--json'],
                    self.make_run_ctx(out, service)) == 7
        assert len((self.directory / 'argv').read_text().splitlines()) == 2
        assert not list(self.worker_root.glob('run-*'))

    def test_provider_refusal(self):
        service, _, _ = self.setup_session()
        for provider in ('claude', 'ollama', 'antigravity'):
            service['create_session']('other-' + provider, provider)
            out = self.make_io()
            assert main(['run', 'other-' + provider, '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work', '--json'],
                        self.make_run_ctx(out, service)) != 0
            assert 'only available for Codex' in out['stdout'].getvalue()
        assert not (self.directory / 'argv').exists()

    def test_stop_cleanup(self):
        service, session, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', 'long')
        script = ('from src.remote_run import run_remote; import json; '
                  'run_remote(json.loads(' + repr(json.dumps(session)) + '), "worker", "codex-cli 0.166.0", '
                  'cwd=' + repr(str(self.directory)) + ', initial_prompt="Work")')
        child = subprocess.Popen([os.sys.executable, '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not (self.directory / 'home').exists():
                assert child.poll() is None
                assert time.monotonic() < deadline
                time.sleep(0.05)
            child.send_signal(signal.SIGTERM)
            child.communicate(timeout=15)
            assert not list(self.worker_root.glob('run-*'))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()

    def test_budget_and_timeout_cleanup(self):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', 'long')
        for flag, value, code in (('--budget', '0.000001', 125), ('--timeout-seconds', '1', 124)):
            out = self.make_io()
            assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work',
                         flag, value, '--json'], self.make_run_ctx(out, service)) == code
            assert not list(self.worker_root.glob('run-*'))

    def test_rotating_token_in_payload_is_refused(self):
        _, session, auth = self.setup_session()
        with pytest.raises(CdxError, match='Refusing to send a refresh token'):
            run_remote(session, 'worker', 'codex-cli 0.166.0', cwd=str(self.directory),
                       initial_prompt=auth['tokens']['refresh_token'])
        assert not (self.directory / 'argv').exists()

    def test_sweep(self):
        _, session, _ = self.setup_session()
        self.worker_root.mkdir(mode=0o700)
        dead = self.worker_root / 'run-dead'
        dead.mkdir()
        (dead / 'auth.json').write_text('dead credential')
        run_remote(session, 'worker', preflight('worker'), cwd=str(self.directory), initial_prompt='Work')
        assert not list(self.worker_root.glob('run-*'))

    def test_expiration_is_named_without_retry(self):
        _, session, _ = self.setup_session()
        with mock.patch('src.remote_run.temporary_auth', return_value={
            **credential(lifetime=-1), 'tokens': {**credential(lifetime=-1)['tokens'], 'refresh_token': ''}
        }), pytest.raises(CdxError) as error:
            run_remote(session, 'worker', preflight('worker'), cwd=str(self.directory), initial_prompt='Work')
        assert error.value.code == 'remote_credential_expired'
        assert not list(self.worker_root.glob('run-*'))

    def test_refresh_holds_controller_auth_lock(self):
        from src.codex_usage import codex_auth_lock
        _, session, _ = self.setup_session()
        path = pathlib.Path(session['authHome'], 'auth.json')
        path.write_text(json.dumps(credential(age=8 * 86400)))

        def refresh(home):
            with codex_auth_lock(home) as acquired:
                assert not acquired
            path.write_text(json.dumps(credential()))

        with mock.patch('src.remote_run.refresh_auth', side_effect=refresh) as refresh_call:
            run_remote(session, 'worker', preflight('worker'), cwd=str(self.directory), initial_prompt='Work')
        assert refresh_call.call_count == 1

    def test_nonempty_refresh_aborts_before_ssh(self):
        _, session, auth = self.setup_session()
        with mock.patch('src.remote_run.temporary_auth', return_value=auth), pytest.raises(CdxError, match='Refusing'):
            run_remote(session, 'worker', 'codex-cli 0.166.0', cwd=str(self.directory), initial_prompt='Work')
        assert not (self.directory / 'argv').exists()

    def test_sweep_preserves_live_homes(self):
        import fcntl
        _, session, _ = self.setup_session()
        self.worker_root.mkdir(mode=0o700)
        active = self.worker_root / 'run-active'
        active.mkdir()
        with open(active / '.live', 'w') as live:
            fcntl.flock(live, fcntl.LOCK_EX)
            run_remote(session, 'worker', preflight('worker'), cwd=str(self.directory), initial_prompt='Work')
            assert active.is_dir()
        run_remote(session, 'worker', preflight('worker'), cwd=str(self.directory), initial_prompt='Work')
        assert not list(self.worker_root.glob('run-*'))

    def test_detached_registry_completion(self):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('CDX_HOME', service['base_dir'])
        out = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work',
                     '--detach', '--json'], self.make_run_ctx(out, service)) == 0
        result = json.loads(out['stdout'].getvalue())
        assert result['detached'] is True
        deadline = time.monotonic() + 15
        registry = RunRegistry(service['base_dir'])
        while registry.get(result['run_id'])['status'] == 'running':
            assert time.monotonic() < deadline
            time.sleep(0.1)
        assert registry.get(result['run_id'])['status'] == 'succeeded'
        assert not list(self.worker_root.glob('run-*'))

    def test_busy_is_shared(self):
        service, _, _ = self.setup_session()
        registry = RunRegistry(service['base_dir'])
        kwargs = dict(kind='assistant', session='work', provider='codex', model=None, cwd=str(self.directory))
        registry.start('remote', remote='worker', **kwargs)
        with pytest.raises(CdxError, match='busy'):
            registry.start('local', **kwargs)
        with pytest.raises(CdxError, match='busy'):
            registry.start('another-remote', remote='other-worker', **kwargs)


@pytest.mark.parametrize('mode,code', [('unreachable', 'remote_unavailable'), ('mismatch', 'remote_version_mismatch')])
def test_preflight_failure(worker, monkeypatch, mode, code):
    monkeypatch.setenv('FAKE_MODE', mode)
    with pytest.raises(CdxError) as error:
        preflight('worker')
    assert error.value.code == code
    assert not list(worker.glob('run-*'))


def test_detached_forwards_remote():
    parsed = _parse_run_args(['work', '--remote', 'worker', '--cwd', '/work', '--prompt', 'Work', '--detach', '--json'])
    argv = _detached_child_argv(parsed, '/prompt', 'work', '/work')
    assert argv[argv.index('--remote') + 1] == 'worker'


@pytest.mark.parametrize('target', ['', '   '])
def test_empty_remote_never_runs_locally(target):
    with pytest.raises(CdxError, match='nonempty SSH target'):
        _parse_run_args(['work', '--remote', target, '--cwd', '/work', '--prompt', 'Work', '--json'])
