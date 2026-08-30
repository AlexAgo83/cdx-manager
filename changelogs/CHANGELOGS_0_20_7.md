# CDX Manager 0.20.7

## Fixes

- `cdx handoff <source> <target>` now prefers the source transcript from the
  current workspace when Codex rollout metadata records one, avoiding stale or
  unrelated context when the same account recently worked in another repository.

## Notes

- If provider metadata does not identify a workspace, handoff keeps the previous
  newest-transcript fallback.
