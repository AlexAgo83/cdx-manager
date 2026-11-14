"""The README keeps one short shape; feature detail lives in docs/.

Shared with logics-manager: title and badges, the one-line promise, "Get started in a minute",
"What you can do" (one table row per feature, linking to docs/), "Documentation" with the docs index
and the closing contributions/licence line. Nothing follows that line.
"""

import re
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"
SECTIONS = ["Get started in a minute", "What you can do", "Documentation"]
MAX_LINES = 90


def test_readme_has_exactly_the_shared_sections_in_order():
    text = README.read_text(encoding="utf-8")
    assert re.findall(r"(?m)^## (.+)$", text) == SECTIONS
    assert not re.search(r"(?m)^#{3,} ", text), "subsections belong in docs/, not in the README"


def test_readme_stays_short_and_ends_with_the_licence_line():
    lines = README.read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert len(lines) <= MAX_LINES, f"README has {len(lines)} lines; move detail to docs/"
    assert "MIT licensed" in lines[-1], "nothing may follow the closing contributions/licence line"
