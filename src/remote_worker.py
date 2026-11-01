"""Self-contained Linux worker, framed over SSH stdin before the run payload."""

import fcntl
import json
import os
import pathlib
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

# Supplied by the controller before this module is executed.
SANDBOX_SOURCE = globals().get('SANDBOX_SOURCE', '')


def version():
    return subprocess.check_output(["codex", "--version"], stderr=subprocess.DEVNULL, timeout=10).decode().strip()


def storage():
    mounts = [row.split() for row in pathlib.Path('/proc/mounts').read_text().splitlines()]
    location = pathlib.Path('/dev/shm').resolve()
    enclosing = [row for row in mounts if pathlib.Path(row[1]) == location or pathlib.Path(row[1]) in location.parents]
    if not enclosing or max(enclosing, key=lambda row: len(row[1]))[2] != 'tmpfs':
        raise RuntimeError("Remote execution requires memory-backed /dev/shm")
    root = pathlib.Path('/dev/shm') / f'cdx-remote-{os.getuid()}'
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("Unsafe remote credential directory")
    return root


def allocate(root):
    # Serialize sweep and allocation so another launcher cannot sweep a new home.
    with open(root / '.sweep', 'a') as sweep:
        fcntl.flock(sweep, fcntl.LOCK_EX)
        for path in root.glob('run-*'):
            if path.is_symlink() or not path.is_dir():
                continue
            try:
                with open(path / '.live', 'a') as live:
                    fcntl.flock(live, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    shutil.rmtree(path)
            except (BlockingIOError, FileNotFoundError):
                continue
        home = pathlib.Path(tempfile.mkdtemp(prefix='run-', dir=root))
        live = open(home / '.live', 'a')
        fcntl.flock(live, fcntl.LOCK_EX)
    return home, live


def isolation_probe_command(payload, home, env):
    # Execute exactly the local confinement implementation, shipped over stdin.
    namespace = {'__name__': 'cdx_workspace_sandbox'}
    exec(compile(SANDBOX_SOURCE, 'workspace_sandbox.py', 'exec'), namespace)
    return namespace['sandbox_command'](
        ['codex', '--version'], pathlib.Path(payload['cwd']), network=payload['network'],
        writable=payload['writable'], source=env, auth_home=str(home), provider='codex',
        observation_home=str(home / 'sessions'))


def probe(root, payload):
    if not payload.get('isolate_workspace'):
        print(version())
        return 0
    # Exercise mounts, namespaces and the nft setup with a dummy home before
    # the controller reads or sends a credential. Binary presence is insufficient.
    with tempfile.TemporaryDirectory(prefix='probe-', dir=root) as directory:
        home = pathlib.Path(directory)
        (home / 'auth.json').write_text(json.dumps({'tokens': {'refresh_token': ''}}))
        os.chmod(home / 'auth.json', 0o600)
        (home / 'sessions').mkdir()
        command, env = isolation_probe_command(payload, home, dict(os.environ))
        result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError('Remote workspace isolation unavailable')
        print(result.stdout.decode().strip())
        return 0


def main():
    root = storage()
    payload = json.loads(sys.stdin.buffer.readline())
    if sys.argv[-1] == 'probe':
        return probe(root, payload)
    auth = payload['auth']
    if auth['tokens'].get('refresh_token') != '':
        raise RuntimeError('Refusing a rotating remote credential')
    if version() != payload['version']:
        raise RuntimeError('Remote Codex CLI version mismatch')
    child = None
    stopped = threading.Event()

    def stop(*_):
        stopped.set()
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            except ProcessLookupError:
                pass

    def disconnected():
        while os.read(0, 1):
            pass
        stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    signal.signal(signal.SIGINT, stop)
    home, live = allocate(root)
    try:
        if stopped.is_set():
            return 130
        os.umask(0o077)
        (home / 'auth.json').write_text(json.dumps(auth))
        os.chmod(home / 'auth.json', 0o600)
        (home / 'config.toml').write_text('cli_auth_credentials_store = "file"\n' + payload['config'])
        env = {key: value for key, value in os.environ.items()
               if key not in ('OPENAI_API_KEY', 'OPENAI_ACCESS_TOKEN', 'CODEX_ACCESS_TOKEN', 'CODEX_API_KEY', 'CODEX_HOME')}
        env['CODEX_HOME'] = str(home)
        command = ['codex', *payload['args']]
        if payload.get('isolate_workspace'):
            (home / 'sessions').mkdir(mode=0o700)
            args = payload['args'][:]
            while '-s' in args:
                index = args.index('-s')
                del args[index:index + 2]
            if '--dangerously-bypass-approvals-and-sandbox' not in args:
                index = args.index('--') if '--' in args else len(args)
                args[index:index] = ['--dangerously-bypass-approvals-and-sandbox']
            namespace = {'__name__': 'cdx_workspace_sandbox'}
            exec(compile(SANDBOX_SOURCE, 'workspace_sandbox.py', 'exec'), namespace)
            command, env = namespace['sandbox_command'](
                ['codex', *args], pathlib.Path(payload['cwd']), network=payload['network'],
                writable=payload['writable'], source=env, auth_home=str(home), provider='codex',
                observation_home=str(home / 'sessions'))
        child = subprocess.Popen(command, cwd=payload['cwd'], env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        if stopped.is_set():
            stop()
        threading.Thread(target=disconnected, daemon=True).start()
        secrets = [value for value in auth['tokens'].values() if isinstance(value, str) and value]

        output_lock = threading.Lock()
        observed = {}

        def snapshot():
            # Only the fresh per-run home supplies model evidence. No transcript
            # or authentication content leaves the worker.
            with output_lock:
                identifier = observed.get('thread_id')
                usage = observed.get('usage')
                if not identifier or not usage:
                    return
                for path in (home / 'sessions').rglob('*.jsonl'):
                    if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
                        continue
                    try:
                        records = [json.loads(line) for line in path.read_text().splitlines()]
                    except (OSError, ValueError):
                        continue
                    if not any(row.get('type') == 'session_meta' and row.get('payload', {}).get('id') == identifier for row in records):
                        continue
                    contexts = [row.get('payload', {}) for row in records if row.get('type') == 'turn_context']
                    models = {row.get('model') for row in contexts}
                    counts = [row.get('payload', {}).get('info', {}).get('total_token_usage') for row in records
                              if row.get('type') == 'event_msg' and row.get('payload', {}).get('type') == 'token_count']
                    if (len(models) == 1 and None not in models and counts and counts[-1]
                            and all(counts[-1].get(key) == usage.get(key) for key in ('input_tokens', 'output_tokens', 'cached_input_tokens'))):
                        event = json.dumps({'type': 'cdx.remote.usage', 'usage': usage, 'model': next(iter(models))})
                        for secret in secrets:
                            event = event.replace(secret, '[REDACTED]')
                        print(event, flush=True)
                    return

        def forward(source, target):
            for line in iter(source.readline, b''):
                for secret in secrets:
                    line = line.replace(secret.encode(), b'[REDACTED]')
                with output_lock:
                    if target is sys.stdout:
                        try:
                            event = json.loads(line)
                            if event.get('type') == 'thread.started':
                                observed['thread_id'] = event.get('thread_id')
                            if event.get('type') == 'turn.completed':
                                observed['usage'] = event.get('usage')
                        except (ValueError, AttributeError):
                            pass
                    target.buffer.write(line)
                    target.buffer.flush()

        threads = [threading.Thread(target=forward, args=pair) for pair in
                   ((child.stdout, sys.stdout), (child.stderr, sys.stderr))]
        for thread in threads:
            thread.start()
        while child.poll() is None:
            try:
                child.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                snapshot()
        result = child.returncode
        for thread in threads:
            thread.join()
        snapshot()
        if time.time() >= payload['expires_at']:
            print('Remote temporary credential expired; start a new run from the controller.', file=sys.stderr)
            return 123
        return 130 if stopped.is_set() else result
    finally:
        stop()
        shutil.rmtree(home)
        live.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        # Never render exception values: input and provider errors may contain credentials.
        print('Remote worker setup or execution failed; check Python, Codex, cwd, /dev/shm and isolation dependencies.', file=sys.stderr)
        sys.exit(126)
