# Changelog (`0.4.2 -> 0.4.3`)

## Major Highlights

- Generated from 1 commit(s) between `v0.4.2` and `HEAD` on 2026-04-19.
- Touched areas: Workflow and Skills.
- Fix Windows Codex status parsing

## Generated Commit Summary

## Workflow and Skills

- Fix Windows Codex status parsing

## Validation and Regression Evidence

- `python -m unittest discover -s test -p "test_session_service_py.py"`
- `python -m unittest discover -s test -p "test_cli_py.py"`
- `python -m unittest discover -s test -p "test_runtime_py.py"`
- `node bin/cdx.js status`
