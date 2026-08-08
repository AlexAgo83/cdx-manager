#!/usr/bin/env python3
"""Enumerate and classify every declaration site an option touches.

A count is a symptom. What a consolidation design needs to know is which sites
restate one fact - and could therefore be generated from a single declaration -
and which encode an independent decision that has to stay written down.
"""
import collections
import re

OPTIONS = {
    "rtk":            "boolean",
    "budget":         "bounded number",
    "extra_args":     "free string",
    "fallback_model": "provider-specific string",
    "priority":       "bounded number",
}

SITES = [
    ("cli_args: parser table",   "src/cli_args.py",           r'"--[a-z-]*{flag}"\s*:\s*\{{'),
    ("cli_args: usage string",   "src/cli_args.py",           r'USAGE = .*--{flag}'),
    ("cli_args: returned dict",  "src/cli_args.py",           r'"{key}":\s*parsed\['),
    ("cli_args: unset key list", "src/cli_args.py",           r'"{key}",'),
    ("session_service: validate","src/session_service.py",    r'if "{key}" in settings'),
    ("session_service: unset ok","src/session_service.py",    r'"{key}",'),
    ("cli_helpers: display list","src/cli_helpers.py",        r'\("{key}",'),
    ("cli_helpers: formatting",  "src/cli_helpers.py",        r'key == "{key}"|key in \([^)]*"{key}"'),
    ("commands/status: table",   "src/commands/status.py",    r'"{key}"'),
    ("provider_runtime: mapping","src/provider_runtime.py",   r'launch\.get\("{key}"\)|\("{key}"\)'),
]

rows = collections.OrderedDict()
for key in OPTIONS:
    flag = key.replace("_", "-")
    present = []
    for label, path, pattern in SITES:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        if re.search(pattern.format(flag=flag, key=key), text):
            present.append(label)
    rows[key] = present

print(f"{'option':16}{'shape':26}sites")
for key, present in rows.items():
    print(f"{key:16}{OPTIONS[key]:26}{len(present)}")
print()
counts = collections.Counter(s for present in rows.values() for s in present)
print(f"{'site':30}{'options':9}classification")
for label, _p, _x in SITES:
    n = counts.get(label, 0)
    print(f"{label:30}{n}/{len(OPTIONS):<8}")
