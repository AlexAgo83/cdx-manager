"""Suite-wide guards."""
import subprocess
from unittest import mock

import pytest

_real_run = subprocess.run


@pytest.fixture(autouse=True)
def _no_real_keychain():
    """Never reach the developer's real macOS keychain (finds and deletes).

    Only `/usr/bin/security` is intercepted, answering "item not found" (44);
    every other subprocess runs for real. A test that checks the keychain argv
    patches `subprocess.run` itself, which takes precedence over this one.
    """
    def guarded(argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "/usr/bin/security":
            return subprocess.CompletedProcess(argv, 44, "", "")
        return _real_run(argv, *args, **kwargs)

    with mock.patch("subprocess.run", side_effect=guarded):
        yield


@pytest.fixture(autouse=True)
def _no_real_launch_agents(tmp_path):
    """Never write a notification LaunchAgent into the developer's real home.

    `notify._operator_home` deliberately bypasses HOME, so a test that schedules
    a `cdx ready` notification on macOS used to leave a plist in
    ~/Library/LaunchAgents pointing at a deleted temp script, and macOS shows a
    "Background Activity" alert for each one.
    """
    with mock.patch("src.notify._operator_home", return_value=str(tmp_path / "operator-home")):
        yield
