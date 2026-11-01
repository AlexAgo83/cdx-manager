"""Isolated attempts never mount or update the controller's rotating credential."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from test_remote_run_py import credential

from src import provider_runtime, remote_run, workspace_sandbox
from src.codex_usage import codex_auth_lock
from src.errors import CdxError

pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux memory-backed isolation')


@pytest.mark.parametrize('outcome', ['fresh', 'success', 'failure', 'start_failure', 'setup_stop', 'stop', 'timeout', 'expiry'])
def test_private_snapshot_cleanup_and_controller_independence(tmp_path, monkeypatch, outcome):
    profile = tmp_path / 'profile'
    profile.mkdir()
    real = profile / 'auth.json'
    initial = credential(age=0 if outcome == 'fresh' else 8 * 86400)
    real.write_text(json.dumps(initial))
    original_bytes = real.read_bytes()
    session = {'provider': 'codex', 'authHome': str(profile), 'launch': {'isolate_workspace': True}}
    mounted = []
    refreshed = initial if outcome == 'fresh' else credential()
    replacement = credential(lifetime=9 * 86400)
    replacement['tokens']['refresh_token'] = 'NEW-CONTROLLER-REFRESH'

    def refresh(home):
        assert outcome != 'fresh'
        assert home == str(profile)
        with codex_auth_lock(home) as acquired:
            assert not acquired
        real.write_text(json.dumps(refreshed))

    def snapshot_check():
        assert json.loads(mounted[0].read_text())['tokens']['refresh_token'] == ''
        assert json.loads(mounted[0].read_text())['tokens']['access_token'] == refreshed['tokens']['access_token']

    class Child:
        returncode = None

        def wait(self, timeout=None):
            snapshot_check()
            # A scheduled controller refresh can acquire the lock during the run.
            with codex_auth_lock(str(profile), strict=True) as acquired:
                assert acquired
                if outcome == 'failure':
                    real.write_text(json.dumps(replacement))
            snapshot_check()
            if outcome == 'stop' and self.returncode is None:
                raise KeyboardInterrupt()
            if outcome == 'timeout' and self.returncode is None:
                raise subprocess.TimeoutExpired('codex', timeout)
            if self.returncode is None:
                self.returncode = 7 if outcome == 'failure' else 0

        def terminate(self):
            self.returncode = -15

        kill = terminate

    def spawn(argv, **kwargs):
        index = argv.index('/home/agent/.codex/auth.json')
        path = Path(argv[index - 1])
        mounted.append(path)
        assert argv[index - 2] == '--ro-bind'
        assert path != real
        assert str(path).startswith('/dev/shm/')
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert str(real) not in argv
        assert refreshed['tokens']['refresh_token'] not in json.dumps(kwargs['env'])
        snapshot_check()
        if outcome == 'setup_stop':
            os.kill(os.getpid(), signal.SIGTERM)
        if outcome == 'start_failure':
            raise OSError('Synthetic launch failure')
        return Child()

    monkeypatch.setattr(workspace_sandbox.shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    monkeypatch.setattr(remote_run, 'refresh_auth', refresh)
    # Expire only the supervisor's deadline; snapshot preparation still uses real time.
    if outcome == 'expiry':
        original_expiry = remote_run.token_expiry
        calls = []

        def expire(token):
            calls.append(token)
            return 1 if len(calls) == 2 else original_expiry(token)

        monkeypatch.setattr(remote_run, 'token_expiry', expire)
    with mock.patch.object(provider_runtime, '_build_headless_launch_spec', return_value={
        'command': 'codex', 'args': ['exec', '-s', 'workspace-write', '--', 'Work'],
        'label': 'Codex', 'options': {'env': {'PATH': '/usr/bin'}}
    }):
        if outcome in ('stop', 'setup_stop', 'start_failure', 'expiry'):
            with pytest.raises(CdxError) as error:
                provider_runtime._run_headless_provider_command(session, cwd=str(tmp_path), spawn=spawn)
            if outcome == 'expiry':
                assert error.value.code == 'remote_credential_expired'
        else:
            result = provider_runtime._run_headless_provider_command(
                session, cwd=str(tmp_path), spawn=spawn, timeout_seconds=0 if outcome == 'timeout' else None)
            assert result['returncode'] == {'fresh': 0, 'success': 0, 'failure': 7, 'timeout': -15}[outcome]
            assert result['timed_out'] == (outcome == 'timeout')
    if outcome == 'fresh':
        assert real.read_bytes() == original_bytes
    assert mounted and not mounted[0].parent.exists()
    assert json.loads(real.read_text()) == (replacement if outcome == 'failure' else refreshed)


def test_sandbox_rejects_full_profile(tmp_path, monkeypatch):
    (tmp_path / 'auth.json').write_text(json.dumps(credential()))
    monkeypatch.setattr(workspace_sandbox.shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    with pytest.raises(RuntimeError, match='rotating sandbox credential'):
        workspace_sandbox.sandbox_command(['codex'], tmp_path, network=False, provider='codex', auth_home=str(tmp_path))


def test_nonisolated_local_run_keeps_profile(tmp_path, monkeypatch):
    real = tmp_path / 'auth.json'
    real.write_text(json.dumps(credential()))
    session = {'provider': 'codex', 'authHome': str(tmp_path)}
    monkeypatch.setattr(remote_run, 'temporary_auth', lambda *_: pytest.fail('Nonisolated credentials changed'))

    def attempt(profile, *args, **kwargs):
        assert profile is session
        assert json.loads(real.read_text())['tokens']['refresh_token']
        assert kwargs.get('observation_home') is None
        return 'normal'

    monkeypatch.setattr(provider_runtime, '_run_headless_provider_attempt', attempt)
    assert provider_runtime._run_headless_provider_command(session) == 'normal'
