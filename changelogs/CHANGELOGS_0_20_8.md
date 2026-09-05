# CDX Manager 0.20.8

## Fixes

- Price `gpt-6-astra` usage in `cdx stats` at OpenAI's standard API list
  rates, so Astra runs no longer appear as unpriced when provider transcripts
  report the new model id.

## Notes

- Long-context Astra requests keep the existing conservative limitation:
  `cdx` prices the run at standard rates because usage records do not split
  tokens per request context tier.
