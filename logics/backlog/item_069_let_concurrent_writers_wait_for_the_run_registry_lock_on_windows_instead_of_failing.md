## item_069_let_concurrent_writers_wait_for_the_run_registry_lock_on_windows_instead_of_failing - Let concurrent writers wait for the run registry lock on Windows instead of failing
> From version: 0.15.0
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 40%
> Complexity: Low
> Theme: Concurrency
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Owner: claude

# Problem
- `_registry_lock` uses `msvcrt.locking(fileno, LK_LOCK, 1)` on Windows, which retries ten times at one-second intervals and then raises `EDEADLOCK`. Twenty concurrent writers exhaust that budget and the `OSError` reaches the caller.
- Reproduced on a real Windows machine, and identically on the `v0.14.0` tag, so it predates this work. It passes in CI, which is why it went unnoticed: the runner is less contended than a physical desktop.
- It was set aside as a pre-existing flake. That understates it - a fleet of parallel runs each writing the registry is the load cdx is built to carry, and this is that load failing on one of two supported platforms.
- The two platforms also disagree: `fcntl.flock` blocks indefinitely while `LK_LOCK` gives up, so the same contention produces a wait on one and an error on the other.

# Scope
- In:
  - Wrap Windows lock acquisition in a retry loop with backoff so a waiter waits rather than failing at the tenth attempt.
  - Bound the total wait and raise a specific, actionable error when it is exhausted, so an over-contended registry is distinguishable from a defect.
  - Make the two platforms behave equivalently under contention, or document the remaining difference as deliberate.
  - Verify against a real Windows machine, not only CI, since CI is the environment that hides this.
- Out:
  - Replacing the file-lock mechanism with a different concurrency primitive.
  - Changing the registry file format or its write strategy.

# Acceptance criteria
- AC1: Twenty concurrent `start()` calls all succeed on Windows with no `OSError` reaching the caller.
- AC2: `test_concurrent_starts_do_not_lose_records` passes on a physical Windows machine.
- AC3: A waiter that cannot acquire the lock within the bounded wait raises a `CdxError` naming the contention, not a raw `OSError`.
- AC4: The POSIX path is unchanged in behaviour, and a test covers contention on both platforms.
- AC5: No run record is lost or overwritten under contention, which is what the existing test already asserts.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Twenty concurrent `start()` calls all succeed on Windows with no `OSError` reaching the caller.
- request-AC4 -> This backlog slice. Proof: AC2: `test_concurrent_starts_do_not_lose_records` passes on a physical Windows machine.
- request-AC5 -> This backlog slice. Proof: AC3: A waiter that cannot acquire the lock within the bounded wait raises a `CdxError` naming the contention, not a raw `OSError`.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_019_settle_0_15_0_s_remainder`
- Architecture decision(s): (none yet)
- Request: `req_029_settle_what_0_15_0_left_behind_before_cutting_0_15_1`
- Primary task(s): `task_040_settle_0_15_0_s_remainder_and_cut_0_15_1`

# AI Context
- Summary: Let concurrent writers wait for the run registry lock on Windows instead of failing
- Keywords: scaffolded-backlog, let concurrent writers wait for the run registry lock on windows instead of failing, implementation-ready
- Use when: Implementing the scaffolded slice for Let concurrent writers wait for the run registry lock on Windows instead of failing.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
