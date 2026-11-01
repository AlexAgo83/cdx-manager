"""Worker confinement uses the shipped local implementation and fails closed."""

import io
import json
import pathlib
import subprocess
import sys
from unittest import mock

import pytest

from src import remote_worker
from src.remote_run import worker_input


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    source = pathlib.Path('src/workspace_sandbox.py').read_text()
    monkeypatch.setattr(remote_worker, 'SANDBOX_SOURCE', source, raising=False)
    monkeypatch.setattr(pathlib.Path, 'home', classmethod(lambda cls: tmp_path))
    home = tmp_path / 'credential'
    home.mkdir()
    (home / 'auth.json').write_text('{}')
    (home / 'sessions').mkdir()
    tree = tmp_path / 'checkout'
    tree.mkdir()
    payload = {'cwd': str(tree), 'network': False, 'writable': True, 'isolate_workspace': True,
               'args': ['exec', '-s', 'workspace-write', '--', 'Work'], 'config': 'model = "test-model"\n'}
    return payload, home


def test_worker_frame_contains_exact_local_sandbox_source():
    namespace = {'__name__': 'test_worker'}
    exec(json.loads(worker_input()), namespace)
    assert namespace['SANDBOX_SOURCE'] == pathlib.Path('src/workspace_sandbox.py').read_text()


@pytest.mark.parametrize('writable', [True, False])
def test_remote_isolation_probe_uses_local_mounts_network_and_clean_env(sandbox, writable):
    payload, home = sandbox
    payload['writable'] = writable
    env = {'PATH': '/usr/bin', 'OPENAI_API_KEY': 'secret', 'CODEX_HOME': '/operator', 'GH_TOKEN': 'secret'}
    with mock.patch('shutil.which', side_effect=lambda name, path=None: '/usr/bin/' + name):
        command, clean = remote_worker.isolation_probe_command(payload, home, env)
    assert command[0] == '/usr/bin/pasta'
    assert '--share-net' not in command
    assert '--unshare-pid' in command
    assert '--cap-drop' in command
    assert clean['CODEX_HOME'] == '/home/agent/.codex'
    assert clean['HOME'] == '/home/agent'
    assert not any(value == 'secret' for value in clean.values())
    mount = command.index(payload['cwd'])
    assert command[mount - 1] == ('--bind' if writable else '--ro-bind')
    # The sole deliberate credential exposure is the read-only provider file.
    mount = command.index(str(home / 'auth.json'))
    assert command[mount - 1:mount + 2] == ['--ro-bind', str(home / 'auth.json'), '/home/agent/.codex/auth.json']
    assert str(home) not in command
    assert '/operator' not in command
    assert command[-2:] == ['/usr/bin/codex', '--version']
    assert 'Work' not in command


@pytest.mark.parametrize('missing', ['bwrap', 'pasta', 'nft', 'python3', 'codex'])
def test_isolation_missing_dependency_refuses(sandbox, missing):
    payload, home = sandbox
    with mock.patch('shutil.which', side_effect=lambda name, path=None: None if name == missing else '/usr/bin/' + name):
        with pytest.raises(RuntimeError):
            remote_worker.isolation_probe_command(payload, home, {'PATH': '/usr/bin'})


def test_preflight_exercises_sandbox_without_real_credentials(sandbox):
    payload, home = sandbox
    stdout = io.TextIOWrapper(io.BytesIO())
    with mock.patch('shutil.which', side_effect=lambda name, path=None: '/usr/bin/' + name), \
            mock.patch.object(remote_worker.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'codex-cli test\n')) as run, \
            mock.patch.object(sys, 'stdout', stdout):
        assert remote_worker.probe(home.parent, payload) == 127
    command = run.call_args.args[0]
    assert command[0] == '/usr/bin/pasta'
    assert command[-1] == '--version'
    assert 'Work' not in command
    assert str(home / 'auth.json') not in command
    assert not list(home.parent.glob('probe-*'))


def test_preflight_namespace_failure_refuses_and_cleans_up(sandbox):
    payload, home = sandbox
    with mock.patch('shutil.which', side_effect=lambda name, path=None: '/usr/bin/' + name), \
            mock.patch.object(remote_worker.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'', b'namespace denied')):
        with pytest.raises(RuntimeError, match='isolation unavailable'):
            remote_worker.probe(home.parent, payload)
    assert not list(home.parent.glob('probe-*'))


def test_worker_refuses_real_isolated_payload_before_auth_access(tmp_path):
    payload = {'isolate_workspace': True}
    with mock.patch.object(remote_worker, 'storage', return_value=tmp_path), \
            mock.patch.object(sys, 'argv', ['worker', 'run']), \
            mock.patch.object(sys, 'stdin', io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode() + b'\n'))), \
            mock.patch.object(remote_worker, 'allocate', side_effect=AssertionError('credential home allocated')):
        assert remote_worker.main() == 127
