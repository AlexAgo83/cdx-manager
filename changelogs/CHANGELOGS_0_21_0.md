# CDX Manager 0.21.0

## Recovery and usage reliability

- Preserve imported sessions when an early credential failure triggers forced recovery, and serialize context and run-history appends across independent CLI processes.
- Attribute headless failover attempts and their usage to the actual session. Keep interactive usage totals at real launch boundaries; overlapping sessions with ambiguous attribution are marked uncertain instead of assigned invented totals.
- Use the recorded serving model for headless usage pricing. Handle model-specific cache rates and undefined relative weights consistently in stats.
- Bind handoff recovery to one exact native source file, improve native and terminal transcript discovery, and remove duplicate finalization paths.
- Add regression coverage for persistence, failover totals, usage boundaries, and handoff source selection.

## Validation

- Python tests, project lint, Logics lint/audit, npm package inspection, and Python package build and metadata checks are part of release preparation. Publication and version-specific checksum verification remain separate release gates.
