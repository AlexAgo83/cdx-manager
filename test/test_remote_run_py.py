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
from src.remote_run import needs_refresh, preflight, run_remote, ssh_command, temporary_auth, worker_input
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
    ssh.write_text(r'''#!/usr/bin/env python3
import json, os, shlex, sys
from pathlib import Path
with open(os.environ['FAKE_ARGV'], 'a') as f:
    f.write(json.dumps(sys.argv) + '\n')
if os.environ.get('FAKE_MODE') == 'unreachable':
    sys.exit(255)
os.environ['FAKE_REMOTE'] = 'yes'
command = sys.argv[-1]
if os.environ.get('FAKE_LANDING') == 'cmd':
    assert len(command.encode('utf-16-le')) // 2 <= 8191
    # cmd.exe does not use POSIX single-quote grouping. For this fixed command
    # shape, only double quotes group the Python bootstrap argument.
    args = shlex.split(command, posix=False)
    assert args[:4] == ['wsl.exe', '-d', 'Ubuntu', '--'], 'python3 is not available in cmd.exe'
    args = args[4:]
    assert args[:3] == ['python3', '-u', '-c']
    assert args[3].startswith('"') and args[3].endswith('"')
    args[3] = args[3][1:-1]
else:
    args = shlex.split(command)
# Only fixture storage names change. Source remains on stdin, and the original
# controller argv is logged above before this small fake bootstrap is installed.
original_loads = json.loads
def fixture_loads(value, *extra, **kwargs):
    result = original_loads(value, *extra, **kwargs)
    if isinstance(result, str) and 'def storage():' in result:
        result = result.replace('cdx-remote-', os.environ['FAKE_PREFIX'] + '-')
        if os.environ.get('FAKE_ISOLATE'):
            import ast
            first, rest = result.split('\n', 1)
            sandbox = ast.literal_eval(first.partition(' = ')[2])
            sandbox = sandbox.replace('home / ".nvm",', 'Path(' + repr(str(Path(os.environ['FAKE_ARGV']).parent / 'bin')) + '), home / ".nvm",')
            sandbox = sandbox.replace('path=os.defpath +', 'path=os.environ["PATH"] +')
            sandbox = sandbox.replace('return env', "env.update({key: value for key, value in source.items() if key.startswith('FAKE_')}); return env")
            result = 'SANDBOX_SOURCE = ' + repr(sandbox) + '\n' + rest
    return result
json.loads = fixture_loads
sys.argv = ['-c', args[-1]]
exec(args[3])
''')
    codex = bindir / 'codex'
    codex.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
if '--version' in sys.argv:
    print('codex-cli ' + ('0.other' if os.environ.get('FAKE_REMOTE') and os.environ.get('FAKE_MODE') == 'mismatch' else '0.166.0'))
    sys.exit(0)
if os.environ.get('FAKE_ISOLATE'):
    assert sys.argv.count('--dangerously-bypass-approvals-and-sandbox') == 1
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
sessions.mkdir(exist_ok=True)
usage = {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 0}
(sessions / 'rollout-test-remote-thread.jsonl').write_text('\\n'.join(json.dumps(row) for row in [
    {'type': 'session_meta', 'payload': {'id': 'remote-thread'}},
    {'type': 'turn_context', 'timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
     'payload': {'model': os.environ.get('FAKE_MODEL', 'gpt-5.3-codex'), 'turn_id': 'remote-turn'}},
    {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': usage}}}
]) + '\\n')
evidence_mode = os.environ.get('FAKE_EVIDENCE')
extra = None
if evidence_mode == 'mismatch':
    extra = {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': {**usage, 'input_tokens': 99}}}}
if evidence_mode == 'mixed':
    extra = {'type': 'turn_context', 'timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             'payload': {'model': 'gpt-5.4', 'turn_id': 'second-turn'}}
if evidence_mode == 'old':
    extra = {'type': 'turn_context', 'timestamp': '2000-01-01T00:00:00Z', 'payload': {'model': 'gpt-5.3-codex'}}
if extra:
    with (sessions / 'rollout-test-remote-thread.jsonl').open('a') as transcript:
        transcript.write(json.dumps(extra) + '\\n')
if os.environ.get('FAKE_MODE') == 'large':
    with (sessions / 'rollout-test-remote-thread.jsonl').open('a') as transcript:
        transcript.write(json.dumps({'type': 'event_msg', 'payload': {'message': 'x' * (17 * 1024 * 1024)}}) + '\\n')
if os.environ.get('FAKE_MODE') == 'no_evidence':
    (sessions / 'rollout-test-remote-thread.jsonl').unlink()
if os.environ.get('FAKE_MODE') != 'live':
    print(json.dumps({'type': 'turn.completed', 'usage': usage}), flush=True)
print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Remote completed'}}), flush=True)
if os.environ.get('FAKE_MODE') in ('long', 'live'):
    time.sleep(60)
sys.exit(7 if os.environ.get('FAKE_MODE') == 'failure' else 0)
''')
    for tool_name, script in {
        'pasta': "import os, sys; args=sys.argv[sys.argv.index('--')+1:]; os.execv(args[0], args)",
        'nft': "import sys; sys.stdin.read()",
        'bwrap': """import os, sys
args = sys.argv[1:]
for index, arg in enumerate(args):
    if arg == '--ro-bind' and args[index+2] == '/home/agent/.codex/auth.json':
        os.environ['CODEX_HOME'] = str(__import__('pathlib').Path(args[index+1]).parent)
command = args[args.index('--')+1:]
os.execv(command[0], command)
""",
    }.items():
        path = bindir / tool_name
        path.write_text('#!/usr/bin/env python3\n' + script + '\n')
        path.chmod(0o755)
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

    def test_remote_budget_prices_exact_rollout(self):
        for isolated in (False, True):
            for mode in ('success', 'large'):
                with self.subTest(isolated=isolated, mode=mode):
                    __import__('shutil').rmtree(self.directory / 'cdx', ignore_errors=True)
                    self._check_remote_budget_prices_exact_rollout(isolated, mode)

    def _check_remote_budget_prices_exact_rollout(self, isolated, mode):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', mode)
        self.monkeypatch.setenv('FAKE_LANDING', 'cmd')
        if isolated:
            self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        out = self.make_io()
        flags = ['--isolate-workspace'] if isolated else []
        assert main(['run', 'work', '--remote', 'worker', '--remote-prefix', 'wsl.exe -d Ubuntu --',
                     *flags, '--cwd', str(self.directory), '--prompt', 'Work', '--budget', '10', '--json'],
                    self.make_run_ctx(out, service)) == 0
        result = json.loads(out['stdout'].getvalue())
        assert result['usage_model'] == 'gpt-5.3-codex'
        assert result['usage_models'] == ['gpt-5.3-codex']
        assert result['cost_status'] == 'estimated'
        assert result['cost_usd'] > 0
        assert result['budget_status'] == 'estimated'
        evidence = result['usage_evidence']
        assert evidence['thread_id'] == 'remote-thread'
        assert evidence['models'] == ['gpt-5.3-codex']
        assert evidence['turns'][0]['turn_id'] == 'remote-turn'
        assert evidence['attempt_id'] == result['attempt_id']
        assert evidence['stdout_path'] == result['stdout_path']
        assert 'cdx.remote.usage' not in pathlib.Path(evidence['stdout_path']).read_text()
        assert RunRegistry(service['base_dir']).get(result['run_id'])['cost_usd'] == result['cost_usd']
        assert not list(self.worker_root.glob('run-*'))

    def test_measured_remote_budget_stops_running_provider(self):
        for mode in ('long', 'live'):
            with self.subTest(mode=mode):
                __import__('shutil').rmtree(self.directory / 'cdx', ignore_errors=True)
                self._check_measured_remote_budget_stops_running_provider(mode)

    def _check_measured_remote_budget_stops_running_provider(self, mode):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', mode)
        self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        out = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', '--isolate-workspace', '--cwd', str(self.directory),
                     '--prompt', 'Work', '--budget', '0.000001', '--timeout-seconds', '10', '--json'],
                    self.make_run_ctx(out, service)) == 125
        result = json.loads(out['stdout'].getvalue())
        assert result['error']['code'] == 'budget_exceeded'
        assert result['budget_status'] == 'exceeded'
        assert result['usage_model'] == 'gpt-5.3-codex'
        assert result['error']['spent_usd'] >= 0.000001
        assert not list(self.worker_root.glob('run-*'))

    def test_completed_remote_without_evidence_never_prices_requested_model(self):
        for budget in (False, True):
            with self.subTest(budget=budget):
                __import__('shutil').rmtree(self.directory / 'cdx', ignore_errors=True)
                self._check_completed_remote_without_evidence(budget)

    def _check_completed_remote_without_evidence(self, budget):
        service, _, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', 'no_evidence')
        out = self.make_io()
        flags = ['--budget', '10'] if budget else []
        assert main(['run', 'work', '--remote', 'worker', '--model', 'gpt-5.3-codex', '--cwd', str(self.directory),
                     '--prompt', 'Work', *flags, '--json'], self.make_run_ctx(out, service)) == (125 if budget else 0)
        result = json.loads(out['stdout'].getvalue())
        assert result['usage_model'] is None
        assert result['usage_models'] == []
        assert result['cost_usd'] is None
        assert result['cost_reason'] == 'model_not_observed'
        assert result['budget_status'] == ('unverifiable' if budget else 'not_requested')
        record = RunRegistry(service['base_dir']).get(result['run_id'])
        assert record['status'] == ('failed' if budget else 'succeeded')
        if budget:
            assert result['error']['code'] == 'budget_unverifiable'
        assert 'Remote completed' in pathlib.Path(result['stdout_path']).read_text()
        assert not list(self.worker_root.glob('run-*'))

    def test_remote_rejects_inconsistent_evidence_and_unknown_prices(self):
        for mode, reason in (('mismatch', 'model_not_observed'), ('old', 'model_not_observed'),
                             ('mixed', 'mixed_models_without_counters'), ('unknown', 'model_price_unknown')):
            with self.subTest(mode=mode):
                __import__('shutil').rmtree(self.directory / 'cdx', ignore_errors=True)
                service, _, _ = self.setup_session()
                self.monkeypatch.setenv('FAKE_EVIDENCE', mode)
                self.monkeypatch.setenv('FAKE_MODEL', 'unpriced-serving-model' if mode == 'unknown' else 'gpt-5.3-codex')
                out = self.make_io()
                assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory), '--prompt', 'Work', '--json'],
                            self.make_run_ctx(out, service)) == 0
                result = json.loads(out['stdout'].getvalue())
                assert result['cost_usd'] is None
                assert result['cost_reason'] == reason
                assert result['usage_model'] == ('unpriced-serving-model' if mode == 'unknown' else None)
                assert not list(self.worker_root.glob('run-*'))

    def test_posix_landing_and_large_stdin_payload(self):
        self._check_landing('posix')

    def test_windows_landing_prefix_and_large_stdin_payload(self):
        self._check_landing('cmd')

    def _check_landing(self, landing):
        service, _, auth = self.setup_session()
        self.monkeypatch.setenv('FAKE_LANDING', landing)
        prefix = ['--remote-prefix', 'wsl.exe -d Ubuntu --'] if landing == 'cmd' else []
        prompt = 'Long prompt with quotes " and apostrophes \' ' * 250
        out = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', *prefix, '--cwd', str(self.directory),
                     '--prompt', prompt, '--json'], self.make_run_ctx(out, service)) == 0
        commands = [json.loads(line)[-1] for line in (self.directory / 'argv').read_text().splitlines()]
        assert len(commands) == 2
        for command in commands:
            assert len(command) < 256
            assert 'def main' not in command
            assert prompt not in command
            assert command.startswith('wsl.exe -d Ubuntu -- ' if landing == 'cmd' else 'python3 ')
            for value in auth['tokens'].values():
                assert value not in command
        assert len(worker_input()) > 8191
        assert not list(self.worker_root.glob('run-*'))

    def test_windows_landing_requires_prefix(self):
        self.monkeypatch.setenv('FAKE_LANDING', 'cmd')
        with pytest.raises(CdxError, match='unreachable'):
            preflight('worker')

    def test_isolation_unavailable_refuses_before_credentials(self):
        service, _, _ = self.setup_session()
        # An empty checkout path is rejected regardless of installed tools.
        with mock.patch('src.remote_run.temporary_auth', side_effect=AssertionError('credential accessed')):
            out = self.make_io()
            assert main(['run', 'work', '--remote', 'worker', '--cwd', str(self.directory / 'missing'),
                         '--isolate-workspace', '--prompt', 'Work', '--json'], self.make_run_ctx(out, service)) != 0
        assert 'isolation unavailable' in out['stdout'].getvalue()
        assert len((self.directory / 'argv').read_text().splitlines()) == 1
        assert not list(self.worker_root.glob("*"))

    def test_isolated_remote_cli_run(self):
        service, session, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        original = pathlib.Path(session['authHome'], 'auth.json').read_bytes()
        output = self.make_io()
        assert main(['run', 'work', '--remote', 'worker', '--isolate-workspace', '--permission', 'full', '--cwd', str(self.directory),
                     '--prompt', 'Work', '--json'], self.make_run_ctx(output, service)) == 0
        assert RunRegistry(service['base_dir']).get(json.loads(output['stdout'].getvalue())['run_id'])['status'] == 'succeeded'
        assert pathlib.Path(session['authHome'], 'auth.json').read_bytes() == original
        assert not list(self.worker_root.glob('run-*'))

    def test_isolated_remote_snapshot_and_cleanup(self):
        for mode in ('success', 'failure', 'long'):
            self._isolated_remote_snapshot_and_cleanup(mode)

    def _isolated_remote_snapshot_and_cleanup(self, mode):
        if (self.directory / 'cdx').exists():
            __import__('shutil').rmtree(self.directory / 'cdx')
        _, session, auth = self.setup_session()
        self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        self.monkeypatch.setenv('FAKE_MODE', mode)
        session['launch'] = {**(session.get('launch') or {}), 'isolate_workspace': True}
        original = pathlib.Path(session['authHome'], 'auth.json').read_bytes()
        version = preflight('worker', isolate_workspace=True, cwd=str(self.directory))
        result = run_remote(session, 'worker', version, cwd=str(self.directory), initial_prompt='Work',
                            timeout_seconds=1 if mode == 'long' else 5)
        assert result['timed_out'] == (mode == 'long')
        assert result['returncode'] == {'success': 0, 'failure': 7, 'long': 124}[mode]
        assert pathlib.Path(session['authHome'], 'auth.json').read_bytes() == original
        assert not list(self.worker_root.glob('run-*'))
        assert auth['tokens']['refresh_token'] not in (self.directory / 'argv').read_text()

    def test_scheduled_auth_refresh_can_lock_during_remote_mission(self):
        from src.codex_usage import codex_auth_lock
        service, session, _ = self.setup_session()
        self.monkeypatch.setenv('FAKE_MODE', 'long')
        self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        session['launch'] = {**(session.get('launch') or {}), 'isolate_workspace': True}
        original = pathlib.Path(session['authHome'], 'auth.json').read_text()
        refreshed = []

        def diagnostic(profile):
            with codex_auth_lock(profile['authHome'], strict=True) as acquired:
                assert acquired
                replacement = credential(lifetime=9 * 86400)
                replacement['tokens']['refresh_token'] = 'RENEWED-CONTROLLER-ONLY'
                pathlib.Path(profile['authHome'], 'auth.json').write_text(json.dumps(replacement))
                refreshed.append(True)
            return {'ok': True}

        def check(_):
            if not (self.directory / 'home').exists():
                return False
            output = self.make_io()
            assert main(['auth', 'refresh', 'work', '--json'], {
                **self.make_run_ctx(output, service), 'fetchCodexRateLimitDiagnostic': diagnostic,
            }) == 0
            assert json.loads(output['stdout'].getvalue())['results'][0]['outcome'] == 'valid'
            home = pathlib.Path((self.directory / 'home').read_text())
            copy = json.loads((home / 'auth.json').read_text())
            assert copy['tokens']['refresh_token'] == ''
            assert copy['tokens']['access_token'] == json.loads(original)['tokens']['access_token']
            assert 'RENEWED-CONTROLLER-ONLY' not in json.dumps(copy)
            return True

        result = run_remote(session, 'worker', preflight('worker', isolate_workspace=True, cwd=str(self.directory)), cwd=str(self.directory),
                            initial_prompt='Work', budget_check=check, timeout_seconds=5)
        assert result['budget_exceeded']
        assert refreshed == [True]
        assert json.loads(pathlib.Path(session['authHome'], 'auth.json').read_text())['tokens']['refresh_token'] == 'RENEWED-CONTROLLER-ONLY'
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
        self.monkeypatch.setenv('FAKE_ISOLATE', '1')
        session['launch'] = {**(session.get('launch') or {}), 'isolate_workspace': True}
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
    parsed = _parse_run_args(['work', '--remote', 'worker', '--remote-prefix', 'wsl.exe -d Ubuntu --',
                              '--isolate-workspace', '--cwd', '/work', '--prompt', 'Work', '--detach', '--json'])
    argv = _detached_child_argv(parsed, '/prompt', 'work', '/work')
    assert argv[argv.index('--remote') + 1] == 'worker'
    assert argv[argv.index('--remote-prefix') + 1] == 'wsl.exe -d Ubuntu --'
    assert '--isolate-workspace' in argv


@pytest.mark.parametrize('target', ['', '   '])
def test_empty_remote_never_runs_locally(target):
    with pytest.raises(CdxError, match='nonempty SSH target'):
        _parse_run_args(['work', '--remote', target, '--cwd', '/work', '--prompt', 'Work', '--json'])


@pytest.mark.parametrize('prefix', ['', 'wsl.exe & echo unsafe', 'wsl.exe "Ubuntu"'])
def test_invalid_prefix_rejected(prefix):
    with pytest.raises(CdxError):
        _parse_run_args(['work', '--remote-prefix', prefix, '--cwd', '/work', '--prompt', 'Work', '--json'])
    if prefix:
        with pytest.raises(CdxError, match='Invalid --remote-prefix'):
            ssh_command('worker', 'probe', prefix)


@pytest.mark.parametrize('command', [
    "wsl.exe -d Ubuntu -- python3 -u -c 'print(1)' probe",
    'wsl.exe -d Ubuntu -- python3 -c "' + 'x' * 8192 + '" probe',
])
def test_fake_cmd_rejects_posix_quoting_and_oversized_commands(worker, monkeypatch, command):
    monkeypatch.setenv('FAKE_LANDING', 'cmd')
    result = subprocess.run(['ssh', 'worker', command], input=b'', capture_output=True)
    assert result.returncode != 0


def test_preflight_reports_missing_isolation_dependencies():
    with mock.patch('src.remote_run.subprocess.check_output', return_value=b'codex-cli test'), \
            mock.patch('src.remote_run.subprocess.run', return_value=subprocess.CompletedProcess([], 127, b'', b'')):
        with pytest.raises(CdxError, match='isolation unavailable') as error:
            preflight('worker', isolate_workspace=True, cwd='/checkout')
    assert error.value.code == 'remote_unavailable'
