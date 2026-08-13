## item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates - Declare the launchable terminals in CDX and publish the candidates
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 10%
> Complexity: Medium
> Theme: tray-companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Define the single terminal catalogue and snapshot candidates that native tray backends can honestly offer.
- Keywords: declare, launchable, terminals, cdx, publish, candidates
- Use when: Changing terminal discovery, candidate publication, or the tray terminal preference contract.
- Skip when: Changing an existing platform launcher without changing candidate availability.

# Problem
- Nothing in CDX knows which terminal names are launchable, so nothing can offer a list.
- The preference is discoverable only by reading `cdx tray --help` or the source.
- A list computed in one place and honoured in another will drift the first time a name is added without its launch branch.

# Scope
- In:
  - Declare, in src/tray_terminal.py, the per-platform catalogue of names this build knows how to launch, as the single source of truth.
  - Detect which of them are present on the host: `open -Ra <name>` on macOS, PATH lookup on Linux and Windows.
  - Carry the resulting candidates in the snapshot beside the existing `terminal` key and bump SCHEMA_MINOR, so an older companion ignores the addition.
  - Add `cdx tray terminal list` with human and JSON output, marking the current choice and naming the platform default.
  - Re-validate every candidate name through valid_terminal() before it enters the snapshot or the listing.
  - Compute candidates for the same native or WSL transport that will execute the companion action; do not infer a Windows-host result from a WSL process PATH.
- Out:
  - Changing how a terminal is launched; this item only declares and reports.
  - Any change to the tray companion.
  - Storing detection results; the catalogue is computed per snapshot.

# Acceptance criteria
- AC1: A single declaration in src/tray_terminal.py names the launchable terminals per platform, and both the snapshot and the CLI read it rather than repeating it.
- AC2: Detection reports only terminals present on the host, and a detection failure yields an empty candidate list rather than an error.
- AC3: The snapshot carries the candidates alongside `terminal`, with SCHEMA_MINOR bumped, and read_snapshot on a companion that predates the key is unaffected.
- AC4: `cdx tray terminal list` prints the candidates with the current choice marked and the platform default named, and `--json` returns the same data structurally.
- AC5: A name that fails valid_terminal() never reaches the snapshot or the listing, whatever detection returned.
- AC6: Tray contract and tray command test suites cover the catalogue, the detection boundary and both output modes.
- AC7: Native and WSL detection tests prove the advertised candidates belong to the transport that will launch them.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: A single declaration in src/tray_terminal.py names the launchable terminals per platform, and both the snapshot and the CLI read it rather than repeating it.
- request-AC4 -> This backlog slice. Proof: AC2: Detection reports only terminals present on the host, and a detection failure yields an empty candidate list rather than an error.
- request-AC6 -> This backlog slice. Proof: AC3: The snapshot carries the candidates alongside `terminal`, with SCHEMA_MINOR bumped, and read_snapshot on a companion that predates the key is unaffected.
- request-AC7 -> This backlog slice. Proof: AC4: `cdx tray terminal list` prints the candidates with the current choice marked and the platform default named, and `--json` returns the same data structurally.
- request-AC8 -> This backlog slice. Proof: AC5: A name that fails valid_terminal() never reaches the snapshot or the listing, whatever detection returned.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest`
- Architecture decision(s): (none yet)
- Request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Primary task(s): `task_063_deliver_a_discoverable_and_honest_tray_terminal_choice`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
