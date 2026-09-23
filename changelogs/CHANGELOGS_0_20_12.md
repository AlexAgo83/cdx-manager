# CDX Manager 0.20.12

## Codex launches work again with Codex CLI 0.156

- Stop forcing `service_tier="flex"` on Codex launches when fast mode is off. Codex
  CLI 0.156.1 requests with that tier are rejected with
  `400 Unsupported service_tier: flex`, which blocked every `cdx <session>` and
  `cdx run` launch. The tier is now omitted so the API default applies.
- Fast mode is unchanged: it still sends `service_tier="fast"` with
  `features.fast_mode=true`.

## Validation

- 1048 Python tests and project lint pass, with launch-spec tests asserting no service tier is sent
  when fast mode is off.
- Verified on a Linux host with Codex CLI 0.156.1: a headless
  `cdx run` succeeds, while the same request with `service_tier="flex"` reproduces
  the 400 error.
