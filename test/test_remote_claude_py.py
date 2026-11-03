"""Remote Claude uses synthetic stdin-only OAuth and disposable worker homes."""

import io
import json
import os
from pathlib import Path
from unittest import mock

import pytest
from cli_test_support import CliTestBase
from test_remote_run_py import worker  # noqa: F401

from src.claude_remote_token import TOKEN_FILE, read_token, store_token
from src.cli import main
from src.errors import CdxError
from src.remote_run import preflight, run_remote
from src.session_service import create_session_service

TOKEN = 'fake-claude-setup-credential'


@pytest.fixture
def claude_worker(worker, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('FAKE_ISOLATE', '1')
    # The fake confinement runner maps only the disposable HOME. Production uses
    # bubblewrap mounts and namespaces; these assertions inspect its input.
    (tmp_path / 'bin' / 'bwrap').write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert 'CLAUDE_CODE_OAUTH_TOKEN' not in os.environ
assert 'fake-claude-setup-credential' not in str(args)
for index, arg in enumerate(args):
    if arg == '--bind' and args[index+2] == '/home/agent':
        os.environ['HOME'] = args[index+1]
        Path(os.environ['FAKE_HOME']).write_text(args[index+1])
with open(os.environ['FAKE_ARGV'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
command = args[args.index('--')+1:]
os.execv(command[0], command)
''')
    binary = tmp_path / 'bin' / 'claude'
    binary.write_text('''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
if '--version' in sys.argv:
    print('claude-code test-version')
    sys.exit(0)
token = os.environ['CLAUDE_CODE_OAUTH_TOKEN']
assert token == 'fake-claude-setup-credential'
assert token not in str(sys.argv)
assert '--bare' not in sys.argv
assert sys.argv[sys.argv.index('--permission-mode') + 1] == 'bypassPermissions'
assert '--print' in sys.argv and '--output-format' in sys.argv
assert os.environ['CLAUDE_CODE_SUBPROCESS_ENV_SCRUB'] == '1'
assert os.environ['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] == '1'
assert not any(key in os.environ for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
    'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK', 'AWS_ACCESS_KEY_ID',
    'AWS_PROFILE', 'GOOGLE_APPLICATION_CREDENTIALS', 'CLAUDE_CODE_USE_VERTEX',
    'CLAUDE_CODE_USE_FOUNDRY', 'ANTHROPIC_FOUNDRY_API_KEY', 'HTTPS_PROXY'))
home = Path(os.environ['HOME'])
assert str(home).startswith('/dev/shm/')
assert not (home / '.claude.json').exists()
assert not (home / '.claude').exists()
(home / '.claude').mkdir()
(home / '.claude' / 'trace').write_text('disposable trace')
(home / '.claude.json').write_text('{}')
assert sys.stdin.read() == ''
assert not any(token in path.read_text(errors='replace') for path in home.rglob('*') if path.is_file())
print(token, file=sys.stderr, flush=True)
print(json.dumps({'type': 'result', 'subtype': 'success', 'result': 'Done ' + token,
    'session_id': 'remote-claude-session', 'usage': {'input_tokens': 12, 'output_tokens': 4},
    'modelUsage': {'claude-sonnet-4-6': {'inputTokens': 12, 'outputTokens': 4}}}), flush=True)
if os.environ.get('FAKE_MODE') == 'long':
    time.sleep(60)
sys.exit(7 if os.environ.get('FAKE_MODE') == 'failure' else 0)
''')
    binary.chmod(0o755)
    for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                'CLAUDE_CODE_USE_BEDROCK', 'AWS_ACCESS_KEY_ID', 'AWS_PROFILE',
                'GOOGLE_APPLICATION_CREDENTIALS', 'CLAUDE_CODE_USE_VERTEX',
                'CLAUDE_CODE_USE_FOUNDRY', 'ANTHROPIC_FOUNDRY_API_KEY', 'HTTPS_PROXY'):
        monkeypatch.setenv(key, 'competing-source')
    yield worker


class RemoteClaudeTests(CliTestBase):
    @pytest.fixture(autouse=True)
    def fixture(self, claude_worker, tmp_path, monkeypatch):
        self.worker_root = claude_worker
        self.directory = tmp_path
        self.monkeypatch = monkeypatch
        self.service = create_session_service({'base_dir': str(tmp_path / 'cdx')})
        self.session = self.service['create_session']('claude-work', 'claude')

    def test_store_stdin_token_and_run_usage_without_login(self):
        out = self.make_io()
        assert main(['auth', 'claude-token', 'claude-work', '--json'], {
            **self.make_run_ctx(out, self.service), 'stdin': {'isTTY': False}, 'prompt_stdin': io.StringIO(TOKEN + '\n'),
        }) == 0
        path = Path(self.session['authHome']) / TOKEN_FILE
        assert path.stat().st_mode & 0o777 == 0o600
        assert read_token(self.session) == TOKEN
        # Atomic replacement also corrects a previously permissive mode.
        path.chmod(0o644)
        store_token(self.session, TOKEN)
        assert path.stat().st_mode & 0o777 == 0o600
        out = self.make_io()
        assert main(['run', 'claude-work', '--remote', 'worker', '--cwd', str(self.directory),
                     '--prompt', 'Work', '--json'], self.make_run_ctx(out, self.service)) == 0, out['stdout'].getvalue()
        result = json.loads(out['stdout'].getvalue())
        assert result['usage']['input_tokens'] == 12
        assert result['usage']['output_tokens'] == 4
        assert result['usage_model'] == 'claude-sonnet-4-6'
        persisted = out['stdout'].getvalue() + (self.directory / 'argv').read_text()
        for artifact in Path(self.service['base_dir']).rglob('*'):
            if artifact.is_file() and artifact != path:
                persisted += artifact.read_text(errors='replace')
        assert TOKEN not in persisted
        assert '[REDACTED]' in persisted
        assert not list(self.worker_root.glob('run-*'))
        assert not Path((self.directory / 'home').read_text()).exists()

    def test_remote_run_preserves_local_interactive_conversation(self):
        session = self.service['launch_session']('claude-work')
        conversation = session['conversation']
        path = Path(session['authHome']) / '.claude/projects/repo' / (conversation['id'] + '.jsonl')
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'type': 'assistant', 'message': {
            'role': 'assistant', 'content': 'Local interactive reply',
        }}) + '\n')
        store_token(session, TOKEN)
        out = self.make_io()
        assert main(['run', 'claude-work', '--remote', 'worker', '--cwd', str(self.directory),
                     '--prompt', 'Work', '--json'], self.make_run_ctx(out, self.service)) == 0
        run = json.loads(out['stdout'].getvalue())
        assert run['conversation_id'] != conversation['id']
        assert self.service['get_session']('claude-work')['conversation'] == conversation
        history = self.service['get_launch_history']('claude-work', limit=0)
        assert history[0]['conversation_id'] == run['conversation_id']
        out = self.make_io()
        assert main(['conversation', 'claude-work', '--json'], self.make_run_ctx(out, self.service)) == 0
        page = json.loads(out['stdout'].getvalue())
        assert page['status'] == 'ok'
        assert page['resolution_method'] == 'conversation_id'
        assert page['entries'][0]['text'] == 'Local interactive reply'

    def test_missing_token_names_storage_command_before_ssh(self):
        out = self.make_io()
        assert main(['run', 'claude-work', '--remote', 'worker', '--cwd', str(self.directory),
                     '--prompt', 'Work', '--json'], self.make_run_ctx(out, self.service)) == 1
        assert 'cdx auth claude-token claude-work' in out['stdout'].getvalue()
        assert not (self.directory / 'argv').exists()

    def test_failure_and_timeout_remove_volatile_home(self):
        for mode in ('failure', 'long'):
            with self.subTest(mode=mode):
                self._check_cleanup(mode)

    def _check_cleanup(self, mode):
        store_token(self.session, TOKEN)
        self.monkeypatch.setenv('FAKE_MODE', mode)
        version = preflight('worker', provider='claude', cwd=str(self.directory), network=False, writable=True)
        result = run_remote(self.session, 'worker', version, cwd=str(self.directory), initial_prompt='Work', timeout_seconds=1)
        assert result['returncode'] == (7 if mode == 'failure' else 124)
        assert not list(self.worker_root.glob('run-*'))
        assert not Path((self.directory / 'home').read_text()).exists()
        assert TOKEN not in json.dumps(result)
        assert TOKEN not in Path(result['stdout_path']).read_text()
        assert TOKEN not in Path(result['stderr_path']).read_text()

    def test_bare_refused(self):
        store_token(self.session, TOKEN)
        with mock.patch('src.provider_runtime._build_headless_launch_spec', return_value={'args': ['--bare']}), \
                pytest.raises(CdxError, match='--bare'):
            run_remote(self.session, 'worker', 'test', cwd=str(self.directory))


@pytest.mark.skipif(os.name != "posix", reason="POSIX token file permissions")
def test_token_file_permissions_and_symlink_refused(tmp_path):
    session = {'authHome': str(tmp_path), 'name': 'work'}
    store_token(session, TOKEN)
    path = tmp_path / TOKEN_FILE
    path.chmod(0o644)
    with pytest.raises(CdxError, match='cdx auth claude-token work'):
        read_token(session)
    path.unlink()
    other = tmp_path / 'other'
    other.write_text(TOKEN)
    other.chmod(0o600)
    path.symlink_to(other)
    with pytest.raises(CdxError, match='cdx auth claude-token work'):
        read_token(session)


@pytest.mark.skipif(not os.sys.platform.startswith('linux'), reason='Linux bubblewrap sandbox')
@pytest.mark.parametrize('network', [False, True])
def test_claude_sandbox_construction_and_inference_rules(tmp_path, monkeypatch, network):
    from src import workspace_sandbox
    monkeypatch.setattr(workspace_sandbox.shutil, 'which', lambda name, path=None: '/usr/bin/' + name)
    monkeypatch.setattr(workspace_sandbox.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('203.0.113.1', 443))])
    command, env = workspace_sandbox.sandbox_command(
        ['true'], tmp_path, network=network, provider='claude', observation_home='/dev/shm/attempt',
        claude_token_stdin=True, source={'PATH': '/usr/bin', 'CLAUDE_CODE_OAUTH_TOKEN': TOKEN,
                                       'ANTHROPIC_API_KEY': 'competing', 'AWS_PROFILE': 'competing'})
    assert TOKEN not in json.dumps(command)
    assert TOKEN not in json.dumps(env)
    assert 'ANTHROPIC_API_KEY' not in env and 'AWS_PROFILE' not in env
    assert env['XDG_CACHE_HOME'] == '/home/agent/.cache'
    assert command[0] == '/usr/bin/pasta'
    assert '/usr/bin/bwrap' in command
    assert '--bind' in command and '/dev/shm/attempt' in command
    setup = command[command.index('-c') + 1]
    compile(setup, '<network setup>', 'exec')
    if not network:
        assert '203.0.113.1' in setup and 'tcp dport 443' in setup
        assert 'policy drop' in setup
    # Exercise the generated setup with faked DNS/nft/bwrap, without network access.
    namespace = {'__name__': 'test_setup'}
    with mock.patch('subprocess.run') as nft, mock.patch('subprocess.call', return_value=0), \
            mock.patch('sys.argv', ['setup', 'nft', 'bwrap', '--', 'true']), pytest.raises(SystemExit) as result:
        exec(setup, namespace)
    assert result.value.code == 0
    rules = nft.call_args.kwargs['input']
    if not network:
        assert 'ip daddr { 203.0.113.1 } tcp dport 443 accept' in rules
        assert '1.1.1.1, 9.9.9.9' in rules and 'udp dport 53 accept' in rules
