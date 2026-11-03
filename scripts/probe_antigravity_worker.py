"""Measure native worker inference without exporting credentials or raw output.

Run on the signed-in worker as its ordinary service user. The prompt forbids
all tools; agy may still update its own login/session metadata. This is a host
measurement, with optional isolated acceptance, never a login/refresh command.
"""

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
from pathlib import Path

from src.run_usage import _parse_json_records, extract_run_usage
from src.workspace_sandbox import ANTIGRAVITY_DESTINATIONS, antigravity_attempt, antigravity_token, sandbox_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated', action='store_true', help='Measure the read-only bubblewrap attempt too')
    args = parser.parse_args()
    if not shutil.which('strace'):
        raise SystemExit('Host measurement requires strace; no provider was started.')
    with antigravity_attempt() as directory:
        token = antigravity_token()
        before = token.stat()
        trace = Path(directory) / 'connect.trace'
        output = Path(directory) / 'result.json'
        workspace = Path(directory) / 'workspace'
        workspace.mkdir(mode=0o700)
        attempt_home = Path(directory) / 'home'
        attempt_home.mkdir(mode=0o700)
        command = ['agy', '-p', 'Reply with OK only. Do not use tools, access files, or run commands.',
                   '--output-format', 'json']
        env = {**os.environ, 'AGY_CLI_DISABLE_AUTO_UPDATE': 'true'}
        if args.isolated:
            command, env = sandbox_command(command, workspace, network=False, writable=False,
                                           source=env, provider='antigravity', observation_home=str(attempt_home))
        with subprocess.Popen(['strace', '-f', '-e', 'trace=connect', '-o', str(trace), *command],
                              cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as child:
            try:
                stdout, _stderr = child.communicate(timeout=120)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate()
                raise SystemExit('Antigravity host measurement stopped; raw output withheld.') from None
        result_code = child.returncode
        after = token.stat()
        output.write_bytes(stdout)
        records = _parse_json_records(stdout.decode('utf-8', errors='replace'))
        statuses = [row['status'] for row in records if isinstance(row, dict) and row.get('status') in
                    ('SUCCESS', 'ERROR', 'FAILED', 'CANCELLED')]
        addresses = sorted(set(re.findall(r'inet_addr\("([0-9.]+)"\)|inet_pton\(AF_INET6, "([0-9a-fA-F:]+)"',
                                         trace.read_text())))
        resolved = {}
        for host in ANTIGRAVITY_DESTINATIONS:
            resolved[host] = sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        print(json.dumps({'exit_code': result_code, 'isolated': args.isolated, 'statuses': statuses,
                          'usage': extract_run_usage('antigravity', output),
                          'connected_addresses': sorted({a or b for a, b in addresses}),
                          'candidate_dns': resolved, 'token_same_inode': before.st_ino == after.st_ino,
                          'token_metadata_changed': (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size),
                          'token_mode': oct(after.st_mode & 0o777)}))
        return result_code


if __name__ == '__main__':
    raise SystemExit(main())
