#!/usr/bin/env python3

from pathlib import Path


REQUIRED_LOGICS_COMMANDS = (
    "status",
    "health",
    "audit",
    "lint",
    "view",
    "sync",
    "flow",
    "mcp",
)


def main():
    root = Path(__file__).resolve().parents[1]
    logics_path = root / "LOGICS.md"
    if not logics_path.is_file():
        raise SystemExit("LOGICS.md is required and must be tracked with project guidance.")
    text = logics_path.read_text(encoding="utf-8")
    missing = [
        command
        for command in REQUIRED_LOGICS_COMMANDS
        if f"logics-manager {command}" not in text and f"`{command}`" not in text
    ]
    if missing:
        raise SystemExit(
            "LOGICS.md is missing core Logics command guidance: "
            + ", ".join(missing)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
