"""Worker-owned Antigravity authentication and headless completion."""

import json
import os
from pathlib import Path

import pytest
from test_remote_run_py import worker  # noqa: F401

from src import workspace_sandbox
from src.provider_runtime import _build_headless_launch_spec
from src.remote_run import preflight, run_remote
from src.run_usage import extract_run_usage

TOKEN = 'fake-worker-agy-secret'


@pytest.fixture
def agy_worker(worker, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('FAKE_ISOLATE', '1')
    monkeypatch.setenv('HOME', str(tmp_path / 'worker-home'))
    token = Path.home() / workspace_sandbox.ANTIGRAVITY_TOKEN_PATH
    token.parent.mkdir(parents=True)
    token.write_text(TOKEN)
    token.chmod(0o600)
    # Fake only mount execution; production sandbox source still builds all rules.
    binary = tmp_path / 'bin' / 'bwrap'
    binary.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == '--bind' and args[i+2] == '/home/agent':
        os.environ['HOME'] = args[i+1]
        Path(os.environ['FAKE_HOME']).write_text(args[i+1])
    if arg == '--ro-bind' and args[i+2].endswith('/antigravity-oauth-token'):
        os.environ['FAKE_TOKEN_PATH'] = args[i+1]
assert 'fake-worker-agy-secret' not in str(args)
command = args[args.index('--')+1:]
os.execv(command[0], command)
''')
    agy = tmp_path / 'bin' / 'agy'
    agy.write_text('''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
if '--version' in sys.argv:
    print('agy 1.4.12')
    sys.exit(0)
assert '-p' in sys.argv and '--prompt-interactive' not in sys.argv
assert sys.argv[sys.argv.index('--output-format')+1] == 'json'
assert os.environ['AGY_CLI_DISABLE_AUTO_UPDATE'] == 'true'
assert os.environ['HOME'].startswith('/dev/shm/')
assert sys.stdin.read() == ''
token = Path(os.environ['FAKE_TOKEN_PATH']).read_text()
assert token not in str(sys.argv)
mode = os.environ.get('FAKE_MODE')
if mode == 'long':
    time.sleep(60)
print(token, file=sys.stderr)
print(json.dumps({'status': 'ERROR' if mode == 'expired' else 'SUCCESS',
 'error': 'invalid_grant' if mode == 'expired' else None,
 'refused_actions': ['write'] if mode == 'refused' else [],
 'response': 'Done ' + token, 'usage': {'input_tokens': 12, 'output_tokens': 4, 'total_tokens': 16}}))
''')
    agy.chmod(0o755)
    yield worker, token


@pytest.mark.parametrize('mode,code', [('success', None), ('refused', 'antigravity_action_refused'),
                                      ('expired', 'antigravity_session_expired')])
def test_fake_agy_attempt(agy_worker, tmp_path, monkeypatch, mode, code):
    root, token = agy_worker
    monkeypatch.setenv('FAKE_MODE', mode)
    version = preflight('worker', provider='antigravity', cwd=str(tmp_path))
    session = {'provider': 'antigravity', 'name': 'work', 'authHome': str(tmp_path / 'controller'),
               'launch': {}}
    result = run_remote(session, 'worker', version, cwd=str(tmp_path), initial_prompt='Work')
    assert result.get('provider_error') == code
    assert result['returncode'] == (1 if code else 0)
    assert extract_run_usage('antigravity', result['stdout_path'])['total_tokens'] == 16
    assert token.read_text() == TOKEN
    assert TOKEN not in json.dumps(result)
    assert TOKEN not in Path(result['stdout_path']).read_text()
    assert TOKEN not in Path(result['stderr_path']).read_text()
    assert TOKEN not in (tmp_path / 'argv').read_text()
    assert not list(root.glob('run-*'))
    assert not Path((tmp_path / 'home').read_text()).exists()


def test_missing_worker_token(agy_worker, tmp_path):
    from src.errors import CdxError
    agy_worker[1].unlink()
    with pytest.raises(CdxError, match='not signed in'):
        preflight('worker', provider='antigravity', cwd=str(tmp_path))


def test_lock_excludes_concurrent_attempts(agy_worker):
    with workspace_sandbox.antigravity_attempt() as home:
        assert Path(home).is_dir()
        assert not list(Path(home).iterdir())
        with pytest.raises(RuntimeError, match='busy'), workspace_sandbox.antigravity_attempt():
            pass
    assert not Path(home).exists()
    with workspace_sandbox.antigravity_attempt():
        pass


def test_sandbox_google_allowlist_and_mounts(agy_worker, tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_sandbox.shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    monkeypatch.setattr(workspace_sandbox.socket, 'getaddrinfo',
                        lambda *a, **kw: [(2, 1, 6, '', ('142.250.1.1', 443))])
    with workspace_sandbox.antigravity_attempt() as home:
        command, env = workspace_sandbox.sandbox_command(
            ['agy', '-p', 'Work', '--output-format', 'json'], tmp_path,
            source={'PATH': os.environ['PATH']}, network=True, provider='antigravity', observation_home=home)
    token = str(agy_worker[1])
    assert command[command.index(token)-1] == '--ro-bind'
    assert env['AGY_CLI_DISABLE_AUTO_UPDATE'] == 'true'
    assert TOKEN not in str(command) + str(env)
    setup = command[command.index('-c')+1]
    assert 'policy drop' in setup and '142.250.1.1' in setup
    assert '192.168.0.0/16' in setup and 'fc00::/7' in setup
    assert not any('PROXY' in key or 'GOOGLE' in key for key in env)


def test_explicit_print_spec():
    spec = _build_headless_launch_spec({'provider': 'antigravity', 'name': 'work', 'launch': {}}, initial_prompt='Work')
    assert spec['args'] == ['-p', 'Work', '--output-format', 'json']


def test_print_spec_preserves_model_and_extra_args(tmp_path):
    spec = _build_headless_launch_spec(
        {'provider': 'antigravity', 'name': 'gemi', 'authHome': str(tmp_path),
         'launch': {'model': 'fake-model', 'extra_args': '--fake-option'}}, initial_prompt='Work')
    assert spec['args'] == ['-p', 'Work', '--output-format', 'json', '--model', 'fake-model', '--fake-option']
    assert spec['options']['env']['HOME'] == str(tmp_path)


def test_local_run_preserves_profile_home_and_token(agy_worker, tmp_path, monkeypatch):
    from cli_test_support import CliTestBase

    from src.cli import main
    from src.session_service import create_session_service

    service = create_session_service({'base_dir': str(tmp_path / 'controller')})
    session = service['create_session']('gemi', 'antigravity')
    profile_token = Path(session['authHome']) / workspace_sandbox.ANTIGRAVITY_TOKEN_PATH
    profile_token.parent.mkdir(parents=True, exist_ok=True)
    profile_token.write_text('fake-local-profile-token')
    agy = tmp_path / 'bin' / 'agy'
    agy.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
assert os.environ['HOME'] == os.environ['FAKE_PROFILE_HOME']
assert (Path.home() / '.gemini/antigravity-cli/antigravity-oauth-token').read_text() == 'fake-local-profile-token'
assert sys.argv[1:] == ['-p', 'Work', '--output-format', 'json']
print(json.dumps({'status': 'SUCCESS', 'response': 'Local profile used'}))
''')
    monkeypatch.setenv('FAKE_PROFILE_HOME', session['authHome'])

    def refuse_worker_auth(*args, **kwargs):
        pytest.fail('Local runs must not read worker authentication or create a sandbox')

    monkeypatch.setattr(workspace_sandbox, 'antigravity_attempt', refuse_worker_auth)
    monkeypatch.setattr(workspace_sandbox, 'antigravity_token', refuse_worker_auth)
    monkeypatch.setattr(workspace_sandbox, 'sandbox_command', refuse_worker_auth)
    helper = CliTestBase()
    output = helper.make_io()
    assert main(['run', 'gemi', '--cwd', str(tmp_path), '--prompt', 'Work', '--json'],
                helper.make_run_ctx(output, service)) == 0
    assert json.loads(output['stdout'].getvalue())['exit_code'] == 0
    assert profile_token.read_text() == 'fake-local-profile-token'
    assert agy_worker[1].read_text() == TOKEN


@pytest.mark.parametrize('record', [{}, {'status': 'ERROR'}, {'status': 'SUCCESS', 'actions': [{'status': 'DENIED'}]}])
def test_json_status_is_required_and_nested_refusals_fail(tmp_path, record):
    from src.run_usage import antigravity_outcome
    output, error = tmp_path / 'stdout', tmp_path / 'stderr'
    output.write_text(json.dumps(record))
    error.write_text('')
    assert antigravity_outcome({'stdout_path': str(output), 'stderr_path': str(error), 'returncode': 0})['returncode'] == 1


@pytest.mark.parametrize('unsafe', ['permissions', 'symlink'])
def test_unsafe_token_is_rejected(agy_worker, tmp_path, unsafe):
    token = agy_worker[1]
    if unsafe == 'permissions':
        token.chmod(0o644)
    else:
        target = tmp_path / 'target'
        token.rename(target)
        token.symlink_to(target)
    with pytest.raises(RuntimeError, match='unsafe'):
        workspace_sandbox.antigravity_token()


def test_remote_timeout_removes_attempt_home(agy_worker, tmp_path, monkeypatch):
    monkeypatch.setenv('FAKE_MODE', 'long')
    session = {'provider': 'antigravity', 'name': 'work', 'authHome': str(tmp_path / 'controller'), 'launch': {}}
    result = run_remote(session, 'worker', 'agy 1.4.12', cwd=str(tmp_path), initial_prompt='Work', timeout_seconds=0.5)
    assert result['returncode'] == 124 and result['timed_out']
    assert not list(agy_worker[0].glob('run-*'))
    assert not Path((tmp_path / 'home').read_text()).exists()


def test_successful_response_can_discuss_sign_in(tmp_path):
    from src.run_usage import antigravity_outcome
    output, error = tmp_path / 'stdout', tmp_path / 'stderr'
    output.write_text(json.dumps({'status': 'SUCCESS', 'response': 'To sign in, follow these steps.'}))
    error.write_text('')
    assert antigravity_outcome({'stdout_path': str(output), 'stderr_path': str(error), 'returncode': 0})['returncode'] == 0


def test_concurrent_fake_agy_attempt_is_refused(agy_worker, tmp_path, monkeypatch):
    import concurrent.futures
    import time

    monkeypatch.setenv('FAKE_MODE', 'long')
    session = {'provider': 'antigravity', 'name': 'work', 'authHome': str(tmp_path / 'controller'), 'launch': {}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(run_remote, session, 'worker', 'agy 1.4.12', cwd=str(tmp_path),
                            initial_prompt='Work', timeout_seconds=3)
        deadline = time.monotonic() + 2
        while not (tmp_path / 'home').exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (tmp_path / 'home').exists()
        second = run_remote(session, 'worker', 'agy 1.4.12', cwd=str(tmp_path), initial_prompt='Work')
        assert second['provider_error'] == 'antigravity_session_busy'
        assert second['returncode'] != 0
        assert first.result()['returncode'] == 124
    assert not list(agy_worker[0].glob('run-*'))


@pytest.mark.parametrize('mode,code', [('success', None), ('refused', 'antigravity_action_refused'),
                                      ('expired', 'antigravity_session_expired')])
def test_cli_records_usage_and_alertable_outcome(agy_worker, tmp_path, monkeypatch, mode, code):
    from cli_test_support import CliTestBase

    from src.cli import main
    from src.run_registry import RunRegistry, final_message
    from src.session_service import create_session_service

    monkeypatch.setenv('FAKE_MODE', mode)
    helper = CliTestBase()
    service = create_session_service({'base_dir': str(tmp_path / 'controller')})
    service['create_session']('work', 'antigravity')
    output = helper.make_io()
    assert main(['run', 'work', '--remote', 'worker', '--cwd', str(tmp_path), '--prompt', 'Work', '--json'],
                helper.make_run_ctx(output, service)) == (1 if code else 0)
    result = json.loads(output['stdout'].getvalue())
    assert result['usage']['total_tokens'] == 16
    record = RunRegistry(service['base_dir']).get(result['run_id'])
    assert record['status'] == ('failed' if code else 'succeeded')
    if code:
        assert result['error']['code'] == code
    else:
        assert final_message(record) == 'Done [REDACTED]'
    assert TOKEN not in output['stdout'].getvalue()
