"""Controller-side temporary Codex credentials and SSH transport."""

import base64
import json
import math
import os
import pathlib
import re
import shlex
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from .codex_usage import _request_codex_app_server, codex_auth_lock
from .errors import CdxError


def token_expiry(token):
    try:
        part = token.split('.')[1]
        expiry = float(json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))['exp'])
        if not math.isfinite(expiry) or expiry <= 0:
            raise ValueError('Invalid expiration')
        return expiry
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise CdxError('Cannot determine remote access token expiration; log in on the controller.') from error


def needs_refresh(auth, now):
    try:
        refreshed = datetime.fromisoformat(auth['last_refresh'].replace('Z', '+00:00')).timestamp()
    except (ValueError, KeyError, TypeError):
        return True
    return now - refreshed > 7 * 86400 or token_expiry(auth['tokens']['access_token']) - now < 86400


def refresh_auth(home):
    result = _request_codex_app_server(home, 'account/read', {'refreshToken': True}, 'refresh_failed', timeout=30)
    if not result.get('ok'):
        raise CdxError('Controller Codex credential refresh failed; log in on the controller.')


def temporary_auth(home, now=None):
    now = time.time() if now is None else now
    try:
        auth = json.loads((pathlib.Path(home) / 'auth.json').read_text())
        if needs_refresh(auth, now):
            refresh_auth(home)
            auth = json.loads((pathlib.Path(home) / 'auth.json').read_text())
            if needs_refresh(auth, now):
                raise CdxError('Controller refresh did not produce a fresh remote credential.')
        tokens = {key: auth['tokens'][key] for key in ('access_token', 'id_token', 'account_id')}
        tokens['refresh_token'] = ''
        result = {'tokens': tokens, 'last_refresh': auth['last_refresh']}
        rotating = auth['tokens'].get('refresh_token')
        if result['tokens']['refresh_token'] != '' or (rotating and rotating in json.dumps(result)):
            raise CdxError('Refusing to send a refresh token to a worker.')
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CdxError('Cannot read controller Codex OAuth credentials; log in on the controller.') from error


def nonsecret_config(home):
    # Copy only known scalar preferences. Provider URLs, hooks, env and arbitrary
    # config entries can contain secrets or refer to controller-only programs.
    path = pathlib.Path(home) / 'config.toml'
    if not path.exists():
        return ''
    allowed = {'model', 'model_reasoning_effort', 'service_tier', 'personality',
               'model_context_window', 'model_auto_compact_token_limit'}
    lines = []
    for line in path.read_text().splitlines():
        if line.lstrip().startswith('['):
            break
        key, sep, value = line.partition('=')
        if sep and key.strip() in allowed and re.fullmatch(r'\s*("[a-zA-Z0-9_. /-]+"|[0-9]+)\s*', value):
            lines.append(line)
    return '\n'.join(lines) + '\n'


def ssh_command(target, mode):
    if not re.fullmatch(r'[a-zA-Z0-9_@.:[\]-]+', target) or target.startswith('-'):
        raise CdxError('Invalid --remote SSH target; use a host alias or user@host.')
    source = pathlib.Path(__file__).with_name('remote_worker.py').read_text()
    return ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=1', target,
            'python3 -c ' + shlex.quote(source) + ' ' + mode]


def preflight(target, env=None):
    try:
        local = subprocess.check_output(['codex', '--version'], env=env, stderr=subprocess.DEVNULL, timeout=10).decode().strip()
        result = subprocess.run(ssh_command(target, 'probe'), env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CdxError('Remote worker unreachable or Codex CLI unavailable.', code='remote_unavailable') from error
    if result.returncode:
        raise CdxError('Remote worker unreachable or missing Python 3, Codex or memory-backed /dev/shm.', code='remote_unavailable')
    if local != result.stdout.decode().strip():
        raise CdxError('Remote Codex CLI version mismatch; install the controller version on the worker.', code='remote_version_mismatch')
    return local


@contextmanager
def remote_auth_lock(home):
    try:
        with codex_auth_lock(home, strict=True) as acquired:
            if not acquired:
                raise CdxError('Codex profile is busy on the controller or a worker.', code='session_busy')
            yield
    except OSError as error:
        raise CdxError('Unable to hold the controller authentication lock.', code='auth_lock_failed') from error


def run_remote(session, target, version, cwd=None, env_override=None, initial_prompt=None,
               timeout_seconds=None, run_id=None, attempt=1, budget_check=None, **_):
    from .provider_runtime import (
        _build_headless_launch_spec,
        _combine_headless_transcript,
        _headless_artifact_paths,
        _headless_run_info,
        _restore_signal_handlers,
        _route_termination_to_interrupt,
    )

    home = session['authHome']
    with remote_auth_lock(home):
        auth = temporary_auth(home)
        if auth['tokens'].get('refresh_token') != '':
            raise CdxError('Refusing to send a refresh token to a worker.')
        spec = _build_headless_launch_spec(session, cwd, env_override, initial_prompt)
        if (session.get('launch') or {}).get('network_access'):
            index = spec['args'].index('--') if '--' in spec['args'] else len(spec['args'])
            spec['args'][index:index] = ['-c', 'sandbox_workspace_write.network_access=true']
        config = nonsecret_config(home)
        launch_text = json.dumps(spec['args']) + config
        if any(value and value in launch_text for value in auth['tokens'].values()):
            raise CdxError('Refusing a credential embedded in the remote prompt or configuration.')
        payload = {'auth': auth, 'config': config, 'args': spec['args'], 'cwd': cwd,
                   'version': version, 'expires_at': token_expiry(auth['tokens']['access_token'])}
        rotating = json.loads((pathlib.Path(home) / 'auth.json').read_text())['tokens'].get('refresh_token')
        if rotating and rotating in json.dumps(payload):
            raise CdxError('Refusing to send a refresh token to a worker.')
        paths = _headless_artifact_paths(session, run_id, attempt)
        paths['remote'] = target
        start = datetime.now(timezone.utc)
        child = None
        cancelled = timed_out = budget_exceeded = credential_expired = False
        handlers = _route_termination_to_interrupt()
        try:
            with open(paths['stdout_path'], 'w') as out, open(paths['stderr_path'], 'w') as err:
                child = subprocess.Popen(ssh_command(target, 'run'), env={**os.environ, **(env_override or {})},
                                         stdin=subprocess.PIPE, stdout=out, stderr=err)
                child.stdin.write(json.dumps(payload).encode() + b'\n')
                child.stdin.flush()
                deadline = time.monotonic() + timeout_seconds if timeout_seconds else None
                while child.poll() is None:
                    if time.time() >= payload['expires_at']:
                        credential_expired = True
                        break
                    if budget_check and budget_check(paths):
                        budget_exceeded = True
                        break
                    if deadline and time.monotonic() >= deadline:
                        timed_out = True
                        break
                    time.sleep(0.1)
        except KeyboardInterrupt:
            cancelled = True
        except (OSError, ValueError) as error:
            raise CdxError('Remote SSH transport failed.', code='remote_unavailable') from error
        finally:
            if child:
                # EOF makes the worker stop its process group and remove the home.
                try:
                    child.stdin.close()
                except (OSError, BrokenPipeError):
                    pass
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
            _restore_signal_handlers(handlers)
            _combine_headless_transcript(paths)
        info = {**_headless_run_info(paths, spec, start, child.returncode), 'remote': target,
                'timed_out': timed_out, 'budget_exceeded': budget_exceeded}
        if cancelled:
            error = CdxError('Remote run was cancelled.', 130)
            error.cancelled = True
            error.run_info = {**info, 'returncode': 130}
            raise error
        if credential_expired or time.time() >= payload['expires_at'] or child.returncode == 123:
            error = CdxError('Remote temporary credential expired; start a new run from the controller.', code='remote_credential_expired')
            error.run_info = info
            raise error
        if child.returncode == 255 and not (timed_out or budget_exceeded):
            error = CdxError('Remote SSH connection failed or was lost.', code='remote_unavailable')
            error.run_info = info
            raise error
        if timed_out or budget_exceeded:
            info['returncode'] = 125 if budget_exceeded else 124
        return info
