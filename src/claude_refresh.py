import inspect
import threading

from .claude_usage import refresh_claude_session_status
from .errors import CdxError


def _refresh_claude_sessions(service, refresh_fn=None):
    refresh_fn = refresh_fn or refresh_claude_session_status
    sessions = service["list_sessions"]()
    claude_sessions = [s for s in sessions if s["provider"] == "claude"]
    if not claude_sessions:
        return

    errors = []
    results = {}
    threads = []

    def fetch(s):
        try:
            usage = refresh_fn(s)
            if inspect.isawaitable(usage):
                import asyncio
                usage = asyncio.run(usage)
            if usage:
                results[s["name"]] = usage
        except Exception as e:
            errors.append(e)

    for s in claude_sessions:
        t = threading.Thread(target=fetch, args=(s,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    for name, usage in results.items():
        try:
            service["record_status"](name, usage)
        except CdxError:
            pass
