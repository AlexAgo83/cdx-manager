"""Synthetic regressions for exact handoff recovery, without provider launches."""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.context_store import read_context, write_context
from src.errors import CdxError
from src.handoff import (
    HandoffSourceError,
    inspect_transcript,
    launch_prompt,
    load_entry,
    prepare_entry,
    resolve_source,
    source_candidates,
)

ID = '11111111-1111-4111-8111-111111111111'
OTHER_ID = '22222222-2222-4222-8222-222222222222'


def native(root, provider, workspace, identity=ID, *, sidechain=False):
    home = root / provider
    if provider == 'codex':
        path = home / 'sessions/2026/09/21' / f'rollout-2026-09-21T00-00-00-{identity}.jsonl'
        record = {'type': 'session_meta', 'payload': {'id': identity, 'cwd': str(workspace),
                  'source': {'subagent': {}} if sidechain else 'cli'}}
    else:
        path = home / '.claude/projects/project' / f'{identity}.jsonl'
        record = {'type': 'user', 'sessionId': identity, 'cwd': str(workspace), 'isSidechain': sidechain,
                  'message': {'role': 'user', 'content': 'Start the work'}}
    record['timestamp'] = '2026-09-21T09:00:00Z'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) + '\n')
    return {'name': provider, 'provider': provider, 'authHome': str(home), 'conversation': {'id': identity}}, path


@pytest.mark.parametrize('provider', ['codex', 'claude'])
def test_identity_wins_over_mtime_and_no_missing_identity_fallback(tmp_path, provider):
    session, exact = native(tmp_path, provider, tmp_path)
    _, old = native(tmp_path, provider, tmp_path, OTHER_ID)
    os.utime(exact, (1, 1))
    os.utime(old, (9999999999, 9999999999))
    assert resolve_source(session, str(tmp_path))['path'] == str(exact)
    exact.unlink()
    with pytest.raises(HandoffSourceError) as failure:
        resolve_source(session, str(tmp_path))
    assert [c['conversation_id'] for c in failure.value.candidates] == [OTHER_ID]
    assert resolve_source(session, str(tmp_path), OTHER_ID)['path'] == str(old)
    session.pop('conversation')
    with pytest.raises(HandoffSourceError):
        resolve_source(session, str(tmp_path))  # Even a single candidate needs explicit selection.


@pytest.mark.parametrize('provider', ['codex', 'claude'])
def test_workspace_subagents_and_non_transcripts_are_excluded(tmp_path, provider):
    session, path = native(tmp_path, provider, tmp_path / 'other')
    with pytest.raises(HandoffSourceError):
        resolve_source(session, str(tmp_path))
    native(tmp_path, provider, tmp_path, sidechain=True)
    with pytest.raises(HandoffSourceError):
        resolve_source(session, str(tmp_path))
    _, good = native(tmp_path, provider, tmp_path, OTHER_ID)
    nested = good.parent / 'subagents' / good.name
    nested.parent.mkdir()
    good.rename(nested)
    (path.parent / 'history.jsonl').write_text('{"message":"not a conversation"}\n')
    assert source_candidates(session, str(tmp_path)) == []


def test_long_transcript_tools_early_decisions_and_partial_tail_remain_accessible(tmp_path):
    session, path = native(tmp_path, 'codex', tmp_path)
    with path.open('a') as handle:
        handle.write(json.dumps({'type': 'response_item', 'payload': {'type': 'function_call_output',
                          'output': 'early authorization evidence ' + 'x' * 150000}}) + '\n')
    complete = path.read_bytes()
    with path.open('ab') as handle:
        handle.write(b'{"partial":')
    source = resolve_source(session, str(tmp_path))
    assert source['extent_bytes'] == len(complete)
    target = {'name': 'target', 'provider': 'claude', 'authHome': str(tmp_path / 'target')}
    entry_path, entry = prepare_entry(str(tmp_path), target, str(tmp_path), session, source)
    assert os.path.getsize(entry_path) < 8000
    assert open(entry['transcript']['path'], 'rb').read(source['extent_bytes']) == complete
    with path.open('ab') as handle:
        handle.write(b'true}\n')
    assert load_entry(str(tmp_path), target, str(tmp_path))[0] == entry_path
    path.write_bytes(b'X' + path.read_bytes()[1:])
    with pytest.raises(CdxError, match='changed'):
        load_entry(str(tmp_path), target, str(tmp_path))


def test_malformed_complete_records_and_missing_metadata_fail(tmp_path):
    _, path = native(tmp_path, 'claude', tmp_path)
    with path.open('ab') as handle:
        handle.write(b'not json\n')
    with pytest.raises(CdxError, match='malformed'):
        inspect_transcript(str(path), 'claude')
    path.write_text('{"type":"user"}\n')
    with pytest.raises(CdxError, match='identity and workspace'):
        inspect_transcript(str(path), 'claude')


def test_entries_are_isolated_notes_preserved_and_prompt_is_instruction_first(tmp_path):
    base = str(tmp_path)
    session, path = native(tmp_path, 'claude', tmp_path)
    source = resolve_source(session, base)
    target = {'name': 'target', 'provider': 'codex', 'authHome': str(tmp_path / 'target')}
    write_context(base, 'Older optional notes', base)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prepared = list(pool.map(lambda _: prepare_entry(base, target, base, session, source), range(2)))
    assert prepared[0][0] != prepared[1][0]
    assert all(os.path.isfile(p) for p, _ in prepared)
    assert read_context(base, base) == 'Older optional notes\n'
    prompt = launch_prompt(*prepared[0])
    assert prompt.index('AGENTS.md') < prompt.index('Recover the task') < prompt.index('Verify the current') < prompt.index('checkpoint')
    for term in ('CLAUDE.md', 'LOGICS.md', 'logics/instructions.md', 'authorization', 'bounded', 'compaction', 'extent_bytes'):
        assert term in prompt
    assert load_entry(base, target, str(tmp_path / 'other')) is None
    path.unlink()
    with pytest.raises(CdxError, match='unavailable'):
        load_entry(base, target, base)


def test_notes_only_requires_notes_and_never_claims_native_recovery(tmp_path):
    base = str(tmp_path)
    target = {'name': 'target', 'provider': 'claude', 'authHome': str(tmp_path / 'target')}
    with pytest.raises(CdxError, match='No prepared'):
        prepare_entry(base, target, base)
    write_context(base, 'old notes', base)
    path, entry = prepare_entry(base, target, base)
    assert entry['mode'] == 'notes-only' and entry['transcript'] is None
    assert load_entry(base, target, base) == (path, entry)


def test_explicit_terminal_is_degraded_and_must_belong_to_source(tmp_path):
    session = {'name': 'local', 'provider': 'ollama', 'authHome': str(tmp_path)}
    with pytest.raises(HandoffSourceError, match='No supported native'):
        resolve_source(session, str(tmp_path))
    path = tmp_path / 'log/cdx-session.log'
    path.parent.mkdir()
    path.write_text('terminal capture')
    source = resolve_source(session, str(tmp_path), terminal_path=str(path))
    assert source['mode'] == 'degraded' and source['conversation_id'] is None
    with pytest.raises(HandoffSourceError, match='must belong'):
        resolve_source(session, str(tmp_path), terminal_path=str(tmp_path / 'unrelated.log'))


@pytest.fixture
def command_context(tmp_path, monkeypatch):
    from src.commands import launch

    session, path = native(tmp_path, 'claude', tmp_path)
    target = {'name': 'target', 'provider': 'codex', 'authHome': str(tmp_path / 'target')}
    sessions = {session['name']: session, target['name']: target}
    output, launches = [], []
    ctx = {'service': {'base_dir': str(tmp_path), 'get_session': sessions.get},
           'cwd': str(tmp_path), 'stdin_is_tty': False, 'options': {}, 'out': output.append}
    monkeypatch.setattr(launch, 'handle_launch', lambda *args, **kwargs: launches.append((args, kwargs)) or 0)
    return launch.handle_handoff, ctx, output, launches, session, target, path


def test_command_json_prepares_without_launch_auth_or_notes_mutation(command_context, tmp_path):
    command, ctx, output, launches, source, target, path = command_context
    write_context(str(tmp_path), 'Standing notes', str(tmp_path))
    auth = tmp_path / 'target/auth.json'
    auth.parent.mkdir()
    auth.write_text('synthetic auth sentinel')
    assert command([source['name'], target['name'], '--json'], ctx) == 0
    payload = json.loads(output[-1])
    assert payload['handoff']['transcript']['conversation_id'] == ID
    assert payload['handoff']['transcript']['path'] == str(path)
    assert 'Start the work' not in output[-1]
    assert not launches
    assert read_context(str(tmp_path), str(tmp_path)) == 'Standing notes\n'
    assert auth.read_text() == 'synthetic auth sentinel'
    assert command([target['name']], ctx) == 0
    assert launches[-1][1]['directory'] == os.path.realpath(tmp_path)
    assert payload['context']['target_path'] in launches[-1][1]['initial_prompt']


def test_command_missing_source_reports_candidates_and_changes_nothing(command_context, tmp_path):
    command, ctx, output, launches, source, target, _path = command_context
    source['conversation']['id'] = OTHER_ID
    before = sorted(p for p in tmp_path.rglob('*'))
    assert command([source['name'], target['name'], '--json'], ctx) == 1
    payload = json.loads(output[-1])
    assert payload['error']['code'] == 'handoff_source_unresolved'
    assert payload['candidates'][0]['conversation_id'] == ID
    assert payload['candidates'][0]['last_event_at'] == '2026-09-21T09:00:00+00:00'
    assert not launches and sorted(p for p in tmp_path.rglob('*')) == before
    assert command([source['name'], target['name'], '--source-conversation', ID, '--json'], ctx) == 0
    assert json.loads(output[-1])['handoff']['transcript']['provenance'] == 'explicit_identity'


@pytest.mark.parametrize('answer', ['', '0', '99', 'abc', KeyboardInterrupt, EOFError])
def test_command_selection_cancel_or_invalid_is_a_noop(command_context, tmp_path, answer):
    command, ctx, _output, launches, source, target, _path = command_context
    source.pop('conversation')
    ctx['stdin_is_tty'] = True

    def ask(_prompt):
        if isinstance(answer, type):
            raise answer()
        return answer

    ctx['options']['input'] = ask
    before = list(tmp_path.rglob('*'))
    with pytest.raises(CdxError, match='cancelled'):
        command([source['name'], target['name']], ctx)
    assert not launches and list(tmp_path.rglob('*')) == before


def test_command_interactive_selection_and_stale_entry_does_not_fall_back(command_context, tmp_path):
    command, ctx, _output, launches, source, target, path = command_context
    source.pop('conversation')
    ctx['stdin_is_tty'] = True
    ctx['options']['input'] = lambda _prompt: '1'
    assert command([source['name'], target['name']], ctx) == 0
    assert len(launches) == 1
    write_context(str(tmp_path), 'Stale summary', str(tmp_path))
    path.unlink()
    with pytest.raises(CdxError, match='unavailable'):
        command([target['name']], ctx)
    assert len(launches) == 1


@pytest.mark.parametrize('args', [[], ['one', 'two', 'three'], ['one', '--source-conversation', ID],
                                 ['one', 'two', '--source-conversation'], ['one', 'two', '--bad'],
                                 ['one', 'two', '--source-conversation', ID, '--source-transcript', 'path']])
def test_handoff_invalid_arguments(args, command_context):
    command, ctx, *_ = command_context
    with pytest.raises(CdxError, match='Usage'):
        command(args, ctx)


def test_entry_write_failure_preserves_previous_pointer(command_context, tmp_path, monkeypatch):
    from src import handoff

    _command, _ctx, _out, _launches, source, target, _path = command_context
    info = resolve_source(source, str(tmp_path))
    prepared = prepare_entry(str(tmp_path), target, str(tmp_path), source, info)
    original = handoff.atomic_write

    def fail_pointer(path, *args, **kwargs):
        if os.path.basename(path).startswith('handoff-'):
            raise OSError('simulated write failure')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(handoff, 'atomic_write', fail_pointer)
    with pytest.raises(OSError, match='simulated'):
        prepare_entry(str(tmp_path), target, str(tmp_path), source, info)
    assert load_entry(str(tmp_path), target, str(tmp_path)) == prepared
    assert len(list((tmp_path / 'target/handoffs').glob('*.json'))) == 1
