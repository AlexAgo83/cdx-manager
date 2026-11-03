"""Dedicated controller-side Claude setup token, never a worker profile."""

import os
import re
import stat
import tempfile
from pathlib import Path

from .errors import CdxError

TOKEN_FILE = '.cdx-remote-claude-token'


def store_token(session, token):
    token = token.strip()
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,16384}', token):
        raise CdxError('Provide one Claude setup token on standard input.')
    home = Path(session['authHome'])
    home.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.claude-token-', dir=home)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(token)
        os.replace(temporary, home / TOKEN_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_token(session):
    try:
        path = Path(session['authHome']) / TOKEN_FILE
        with open(path, opener=lambda name, flags: os.open(name, flags | getattr(os, "O_NOFOLLOW", 0))) as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
                raise ValueError('Unsafe token file')
            token = handle.read(16385).strip()
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,16384}', token):
            raise ValueError('Invalid token')
        return token
    except (OSError, ValueError) as error:
        raise CdxError(
            f"Remote Claude requires a dedicated setup token; run cdx auth claude-token {session['name']} "
            "with the token from claude setup-token on standard input.", code='remote_claude_token_missing',
        ) from error
