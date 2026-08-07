# CDX Manager 0.14.0

## Highlights

- Every command that picks a session now uses one ranking, and `--priority` finally counts in all of them.
- `cdx set --permission workspace-write` works, matching what `cdx run --permission` always accepted.
- New `cdx doctor --check-provider-flags` verifies that the CLI flags cdx maps for each permission actually exist in the provider CLIs.

## Changes

### One session selection rule

`cdx select`, `cdx run --provider`, `cdx next`, the `cdx status` recommendation, and `cdx ready` used two independent rankings that disagreed. Each knew something the other did not: the headless one filtered by provider and honored `--priority`, the recommendation one understood credits and reset scheduling. Which session you got depended on which command you asked.

They are now one function in `src/session_ranking.py`, parameterized by what each caller needs. Candidate filters (disabled, logged out, provider, effort floor, readiness) are kept separate from ordering, because describing a filter as a sort stage is part of what made the old published policy wrong.

The merged ordering is: usability class, then `--priority`, then — for a usable session — credits, availability and reset; for a session that is not usable now, reset first, since when it comes back is what matters. Reasoning effort and session name break the remaining ties.

### The priority setting counts everywhere

`cdx set <name> --priority 90` previously affected only `cdx select` and `cdx run --provider`. Status rows now carry the configured priority and effort, so `cdx next`, `cdx status`, and `cdx ready` honor it too.

Priority ranks sessions *within* a usability class, never across one: a high-priority session with no quota left does not outrank a usable one. Priority says which usable session to prefer, not where to send work that will fail there.

The `cdx status` recommendation line is now labelled `Recommended:` rather than `Priority:`. The old label named the whole recommendation after one of its inputs, so tuning `--priority` and seeing no change read as the setting being broken when availability or resets had decided instead.

### Truthful selection reporting

`cdx select --json` built its `selection_policy` from a hardcoded string that omitted the reasoning-effort tie-break and described the readiness filter as a sort stage, and a `reason` that claimed availability decided even when priority or the alphabetical fallback did.

Both are now derived. `selection_policy` is built from the ranking itself and reports factors and filters separately; `deciding_factor` and `reason` name the factor that actually separated the winner from the runner-up for that call, or report that it was the only candidate. Do not treat `selection_policy` as a stable identifier — it changes when the ranking does, which is the point.

### Selecting on fresh or missing status

`cdx run --provider` now accepts `--refresh` to fetch status before auto-selecting. Cached status remains the default, so ordinary runs do not each pay for a provider probe.

When auto-selection picks a session with no recorded availability, the run payload carries a `session_selected_without_status` warning. That is distinct from a session known to be low: on a freshly imported or long-idle set of sessions, choosing with no data at all is the ordinary case, and it was previously invisible.

### One definition of the values cdx accepts

The reasoning-effort enum was defined in four places (two of them identical, one line apart in the same module) and the permission enum in two, with `cdx set` validating against one pair and `cdx run` against another. `config.py` now owns both, and every validator, normalizer, and `cdx schema --json` derives from them. One test asserts identity rather than equality; another fails if any module restates one of these sets.

### Permission aliases work in cdx set

`cdx run --permission workspace-write` was accepted and normalized to `default`, while `cdx set <name> --permission workspace-write` failed with `Unsupported permission`. The same applied to `read-only` and `danger-full-access`, which are the provider-native spellings a user is most likely to have in hand, and `cdx schema --json` published the aliases without saying they applied to one command only.

`cdx set` and the `perm` alias command now accept them, storing the canonical value so nothing downstream has to learn aliases exist. They were added to `set` rather than removed from `run`, since removing them would break callers passing provider-native spellings today.

### Verifying provider flag mappings

cdx maps each permission to concrete provider CLI flags, and nothing verified those mappings. GitHub issue #8 was exactly that: an `--experimental-yolo` flag mapped for ollama that the ollama CLI never had, undetected until a user hit it.

`cdx doctor --check-provider-flags` checks each configured provider's installed CLI for the flags cdx maps. A rejected flag is a `FAIL` naming the provider, the permission, and the flag. An uninstalled CLI or unreadable help is a `WARN`, never an `OK` — "could not verify" is the state that bug lived in. A provider that maps nothing, such as ollama, reports `OK` with an empty mapping, so having nothing to check is distinguishable from having failed to check.

It is opt-in because it costs a provider CLI invocation per provider, and the default report carries a `provider_permission_flags_unchecked` warning rather than omitting it, so a green doctor never implies the mappings were verified.

Antigravity and ollama permission mappings also moved out of inline branches into `LAUNCH_PERMISSION_ARGS`, so every provider's mapping is declared in one table the check can read. Ollama's entry is deliberately empty.

## Behavior changes

- **`--priority` now outranks availability.** It previously sat below availability in the headless sort, so it only broke exact ties and was effectively inert. A session with lower availability but higher priority now wins within the same usability class. This is the change that makes the setting mean anything.
- **Ties on session name now sort ascending everywhere.** The recommendation ranking sorted names descending as a side effect of reversing its whole sort tuple, disagreeing with the headless ranking. The ascending order is kept.
- **Logged-out sessions are never selection candidates.** `cdx select` without `--require-ready` could previously return one.
- `cdx status`'s recommendation line is labelled `Recommended:` instead of `Priority:`.
- `cdx select --json`'s `selection_policy` is now a structured object rather than an underscore-joined string.

## Validation

- `npm run lint`
- `npm test` — 557 tests.
- End-to-end: with one session at 80% availability and priority 0 and another at 40% and priority 90, `cdx select`, `cdx next`, and `cdx status` all name the second, and `cdx select` reports `decided on priority`.
- The issue #8 condition reproduced against the new provider flag check: mapping `--experimental-yolo` for codex fails the check by name.
- `logics-manager lint --require-status`
- `logics-manager audit --group-by-doc`
