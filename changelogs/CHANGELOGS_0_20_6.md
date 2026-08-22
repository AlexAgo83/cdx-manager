# CDX Manager 0.20.6

## Fixes

- `cdx stats` now prices current Codex/OpenAI and Claude models that were
  previously unpriced or stale, including `gpt-5.5`, `gpt-5.6-terra`, and the
  current Claude Sonnet/Haiku snapshot ids seen in real usage history.
- The token price review tooling now checks OpenAI's official pricing
  documentation directly and points maintainers at the active Logics runbook.

## Notes

- Pro-only or credit-based Codex models without an official token price remain
  unpriced rather than receiving a guessed USD estimate.
