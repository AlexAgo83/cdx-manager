## item_045_accept_prompt_on_standard_input_and_add_a_completion_cursor_to_runs - Accept prompt on standard input and add a completion cursor to runs
> From version: 0.12.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Problem
- `read_run_prompt()` in `src/run_command.py:7` accepts inline text or a file path only. A caller relaying arbitrary untrusted prompt text cannot put it on a command line, so it stages a temporary file, transfers it, invokes cdx, and deletes it in a `finally` block, leaking the file if the process dies in between.
- `handle_runs()` accepts only `--limit`, although `cdx history` already supports `--since`. A watchdog polling for newly-completed runs must request a fixed window and maintain its own bounded set of already-reported run ids to avoid repeating itself.
- That fixed window loses completions outright. The downstream watchdog polls the 20 most recent runs every 15 minutes; if more than 20 runs complete inside one interval, the older ones scroll out of the window before they are ever observed and are never reported. The caller's de-duplication set suppresses repeats but cannot recover a completion it never saw, so this is a silent miss rather than noise — and the fleet launches runs concurrently, so exceeding 20 completions in 15 minutes is reachable in normal use.

# Scope
- In:
  - Accept `--prompt-file -` as reading the prompt from standard input in `read_run_prompt()`, decoded as UTF-8 consistently with the file path branch.
  - Fail with a specific error code when stdin is requested but is an interactive terminal, so an operator is not left waiting at a silent prompt.
  - Ensure the stdin form composes with the existing prompt-source exclusivity rules and with `--detach`.
  - Add `--since` to `cdx runs`, filtering on run completion time and accepting the same cursor forms `cdx history --since` already accepts, reusing that parsing rather than adding a second implementation.
  - Define and document the behavior for runs that have not completed, so a polling caller gets a stable definition of what the cursor selects.
  - Add tests for the stdin prompt path including empty input and non-ASCII content, the interactive-terminal refusal, cursor filtering boundaries, and rejection of a malformed cursor.
- Out:
  - No new prompt source beyond stdin.
  - No opaque or token-based pagination cursor.
  - No `--from`/`--to` window on `runs` in this item.
  - No change to `cdx history` behavior.

# Acceptance criteria
- Given prompt text piped to `cdx run <session> --cwd <path> --prompt-file - --json`, the run receives exactly that text, including non-ASCII characters, with no temporary file created by cdx.
- Given `--prompt-file -` with an interactive terminal on stdin, the command fails immediately with a specific error code instead of blocking on input.
- Given `--prompt-file -` combined with another prompt source, the existing exclusivity rule still applies and reports the argument error code.
- Given `cdx runs --since <cursor> --json`, only runs completed after the cursor are returned, and repeating the call with the newest returned completion time yields no duplicates.
- Given more runs completed after the cursor than the default row count, all of them are returned rather than only the most recent ones, so a polling caller cannot miss a completion by falling behind.
- Given a malformed cursor, the command fails with a specific argument error code and does not fall back to an unfiltered listing.
- Given the same cursor forms accepted by `cdx history --since`, `cdx runs --since` accepts them identically.

# AC Traceability
- request-AC6 -> This backlog slice. Proof: Given prompt text piped to `cdx run <session> --cwd <path> --prompt-file - --json`, the run receives exactly that text, including non-ASCII characters, with no temporary file created by cdx.
- request-AC7 -> This backlog slice. Proof: Given `--prompt-file -` with an interactive terminal on stdin, the command fails immediately with a specific error code instead of blocking on input.
- request-AC8 -> This backlog slice. Proof: Given `--prompt-file -` combined with another prompt source, the existing exclusivity rule still applies and reports the argument error code.
- request-AC9 -> This backlog slice. Proof: Given `cdx runs --since <cursor> --json`, only runs completed after the cursor are returned, and repeating the call with the newest returned completion time yields no duplicates.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Accept prompt on standard input and add a completion cursor to runs
- Keywords: scaffolded-backlog, accept prompt on standard input and add a completion cursor to runs, implementation-ready
- Use when: Implementing the scaffolded slice for Accept prompt on standard input and add a completion cursor to runs.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
