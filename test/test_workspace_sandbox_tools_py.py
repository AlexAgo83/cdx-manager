"""Real Git/RTK probes use disposable repositories and synthetic secrets only."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src import workspace_sandbox
from src.remote_run import worker_input

pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux bubblewrap confinement')


@pytest.fixture(params=['local', 'shipped-worker'])
def implementation(request):
    if request.param == 'local':
        return workspace_sandbox
    namespace = {'__name__': 'sandbox_tools_worker'}
    exec(json.loads(worker_input()), namespace)
    sandbox = {'__name__': 'sandbox_tools'}
    exec(namespace['SANDBOX_SOURCE'], sandbox)
    import types
    return types.SimpleNamespace(**sandbox)


@pytest.fixture
def repository(tmp_path):
    source = tmp_path / 'private' / 'source'
    source.mkdir(parents=True, mode=0o700)
    tree = tmp_path / 'mission'
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
               GIT_AUTHOR_NAME='Sandbox Test', GIT_AUTHOR_EMAIL='sandbox@example.invalid',
               GIT_COMMITTER_NAME='Sandbox Test', GIT_COMMITTER_EMAIL='sandbox@example.invalid')

    def git(*args):
        return subprocess.run(['git', '-C', str(source), *args], env=env, check=True, capture_output=True, text=True).stdout

    git('init')
    (source / 'tracked.txt').write_text('original\n' * 100)
    git('add', 'tracked.txt')
    git('commit', '-m', 'sandbox history')
    git('branch', 'history-branch')
    git('gc', '--prune=now')
    git('pack-refs', '--all')
    git('worktree', 'add', '-b', 'mission', str(tree))
    # Host includes and authenticated remote URLs must not enter the Git view.
    git('config', 'include.path', '/sandbox-must-not-read-host-config')
    git('config', 'remote.origin.url', 'ssh://synthetic-secret@example.invalid/repo')
    key = tmp_path / 'operator' / '.ssh' / 'id_ed25519'
    key.parent.mkdir(parents=True)
    key.write_text('SYNTHETIC PRIVATE KEY: never an operator secret\n')
    return source, tree, key


@pytest.mark.parametrize('writable', [True, False])
def test_tool_mounts_and_environment(repository, tmp_path, implementation, monkeypatch, writable):
    source, tree, key = repository
    cache = tmp_path / 'cache'
    monkeypatch.setattr(workspace_sandbox, 'CACHE', cache)
    # Shipped code carries its own globals.
    implementation.sandbox_command.__globals__['CACHE'] = cache
    monkeypatch.setattr(shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    args, env = implementation.sandbox_command(['git', 'status'], tree, network=False, writable=writable,
                                               source={'PATH': '/usr/bin', 'RTK_DB_PATH': str(key), 'SSH_AUTH_SOCK': str(key)})
    assert env['PATH'].endswith(str(Path.home() / '.local/bin'))
    assert env['RTK_DB_PATH'] == '/cache/rtk/history.db'
    assert (cache / 'rtk').is_dir()
    assert 'SSH_AUTH_SOCK' not in env
    assert env['GIT_DIR'] == '/home/agent/.git'
    assert env['GIT_COMMON_DIR'] == '/home/agent/.git'
    assert env['GIT_WORK_TREE'] == str(tree)
    assert str(source / '.git') not in args
    assert str(source / '.git' / 'config') not in args
    assert str(source / '.git' / 'objects') in args
    assert str(source / '.git' / 'refs') in args
    assert str(source / '.git' / 'packed-refs') in args
    assert str(key) not in args
    assert '--bind' not in args[args.index(str(tree)) + 1:]


def test_real_git_with_selected_metadata(repository, tmp_path, implementation, monkeypatch):
    """Check the metadata subset with real Git even on namespace-less runners."""
    _, tree, _ = repository
    cache = tmp_path / 'cache'
    monkeypatch.setattr(workspace_sandbox, 'CACHE', cache)
    implementation.sandbox_command.__globals__['CACHE'] = cache
    monkeypatch.setattr(shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    args, env = implementation.sandbox_command(['git', 'status'], tree, network=False)
    view = tmp_path / 'git-view'
    view.mkdir()
    for index, arg in enumerate(args):
        if arg == '--ro-bind' and args[index + 2].startswith('/home/agent/.git/'):
            origin = Path(args[index + 1])
            target = view / Path(args[index + 2]).relative_to('/home/agent/.git')
            if origin.is_dir():
                shutil.copytree(origin, target)
            else:
                shutil.copyfile(origin, target)
    env.update(GIT_DIR=str(view), GIT_COMMON_DIR=str(view))
    for command in (['log', '-1'], ['show', 'HEAD'], ['diff'], ['status'], ['blame', 'tracked.txt'],
                    ['branch', '-a'], ['rev-parse', '--show-toplevel']):
        result = subprocess.run(['git', *command], cwd=tree, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
    result = subprocess.run(['git', 'remote', '-v'], cwd=tree, env=env, text=True, capture_output=True, check=True)
    assert result.stdout == ''


@pytest.mark.parametrize('writable', [True, False])
def test_real_sandbox_git_rtk_and_secret_boundary(repository, tmp_path, implementation, monkeypatch, writable):
    required = os.environ.get('CDX_REQUIRE_SANDBOX_TESTS') == '1'

    def unavailable(reason):
        if required:
            pytest.fail(reason)
        pytest.skip(reason)

    if not shutil.which('bwrap'):
        unavailable('bubblewrap is unavailable')
    source, tree, key = repository
    cache = tmp_path / 'cache'
    monkeypatch.setattr(workspace_sandbox, 'CACHE', cache)
    implementation.sandbox_command.__globals__['CACHE'] = cache
    probe_args, probe_env = implementation.sandbox_command(['true'], tree, network=False)
    probe = subprocess.run(probe_args, env=probe_env, capture_output=True, text=True, timeout=15)
    if probe.returncode and ('Operation not permitted' in probe.stderr or 'No permissions' in probe.stderr):
        unavailable('bubblewrap namespaces unavailable: ' + probe.stderr.strip())
    assert probe.returncode == 0, probe.stderr
    rtk = shutil.which('rtk') or str(Path.home() / '.local/bin/rtk')
    if not Path(rtk).is_file():
        unavailable('install real rtk in ~/.local/bin or PATH')
    # PATH deliberately omits ~/.local/bin, as on noninteractive SSH launches.
    tool_env = {'PATH': os.defpath, 'GH_TOKEN': 'synthetic-secret', 'GIT_CONFIG_GLOBAL': str(key)}
    script = r'''
import os, pathlib, sqlite3, subprocess, sys

def git(*args):
    return subprocess.check_output(['git', *args], text=True, stderr=subprocess.STDOUT)

assert 'sandbox history' in git('log', '-1', '--oneline')
assert 'original' in git('show', 'HEAD:tracked.txt')
assert 'Sandbox Test' in git('blame', 'tracked.txt')
assert 'history-branch' in git('branch', '-a')
assert git('rev-parse', '--show-toplevel').strip() == os.getcwd()
assert git('status', '--porcelain') == ''
assert git('diff') == ''
if sys.argv[3] == 'True':
    pathlib.Path('tracked.txt').write_text('changed\n')
    assert '+changed' in git('diff')
    assert 'tracked.txt' in git('status', '--porcelain')
else:
    try:
        pathlib.Path('tracked.txt').write_text('changed\n')
    except OSError:
        pass
    else:
        raise AssertionError('review checkout is writable')
assert git('remote', '-v') == ''
assert git('config', '--get', 'credential.helper').strip() == ''
assert subprocess.run(['git', 'config', '--get', 'include.path']).returncode == 1
assert subprocess.run(['git', 'add', 'tracked.txt'], capture_output=True).returncode != 0
for name in (sys.argv[1], '/home/agent/.ssh/id_ed25519', '/home/agent/.gitconfig', sys.argv[2]):
    try:
        pathlib.Path(name).read_bytes()
    except (OSError, PermissionError):
        pass
    else:
        raise AssertionError('host path readable: ' + name)
subprocess.run(['rtk', '--version'], check=True)
subprocess.run(['rtk', 'git', 'log', '--oneline'], check=True)
subprocess.run(['rtk', 'git', 'status'], check=True)
subprocess.run(['rtk', 'gain'], check=True)
db = pathlib.Path(os.environ['RTK_DB_PATH'])
assert db.is_file()
with sqlite3.connect(db) as connection:
    assert connection.execute('select count(*) from commands').fetchone()[0] > 0
'''
    args, env = implementation.sandbox_command(
        ['python3', '-c', script, str(key), str(source / '.git/config'), str(writable)], tree,
        network=False, writable=writable, source=tool_env)
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (cache / 'rtk/history.db').is_file()
