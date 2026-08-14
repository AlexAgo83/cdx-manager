## prod_049_token_numbers_a_user_can_act_on - Token numbers a user can act on
> Date: 2026-08-14
> Status: Proposed
> Related request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
> Related backlog: `item_126_define_one_token_accounting_shared_by_both_usage_readers`, `item_127_bill_each_run_for_its_own_tokens_instead_of_the_whole_transcript`, `item_128_read_usage_from_the_session_s_own_transcript_not_the_newest_file`
> Related task: `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Make `cdx stats` an honest account of what each session spent: totals that include cached input, per-run figures that do not re-bill history on resume, measurements taken from the session's own transcript, and one column meaning across providers.

# Goals
- Report a total that reflects real consumption, cache included.
- Bill each run for its own tokens and nothing else.
- Measure the session that ran, identified rather than guessed.
- Give IN, CACHE, OUT, and TOTAL one definition shared by both usage readers and both providers.
- Raise how often usage is captured at all, so the table describes the fleet rather than a sample of it.

# Non-goals
- No cost-in-currency reporting or per-model pricing.
- No new stats columns, filters, or output formats.
- No querying provider billing APIs — this stays local-transcript based.
- No retroactive repair of usage already recorded in launch history.
- No change to how launches are performed or to launch success semantics.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Task back-reference: `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`
