"""Check the npm launcher's interpreter compatibility boundary."""

import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("version, expected", [((3, 8), 1), ((3, 9), 1), ((3, 10), 0), ((3, 14), 0)])
def test_python_runner_supported_versions(version, expected):
    source = (Path(__file__).resolve().parents[1] / "bin" / "python-runner.js").read_text(encoding="utf-8")
    probe = re.search(r'const PYTHON_VERSION_CHECK = "([^"]+)";', source).group(1)
    result = subprocess.run([sys.executable, "-c", f"import sys; sys.version_info = {version!r}; {probe}"], check=False)
    assert result.returncode == expected
