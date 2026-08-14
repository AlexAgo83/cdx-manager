## item_130_report_token_spend_in_currency - Report token spend in currency
> From version: 0.19.3
> Schema version: 1.0
> Status: In progress
> Understanding: 70
> Confidence: 65
> Progress: 40%
> Complexity: Medium
> Theme: Usage accounting
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-14 10:26:32

# AI Context
- Summary: Turning the weighted figure into a currency amount needs only one number per model, but cdx does not currently record which model actually served each run — that gap, not the arithmetic, is the work.
- Keywords: cost reporting, price per MTok, model attribution, launch history, weighted tokens
- Use when: Adding a currency cost figure to cdx's usage reporting.
- Skip when: Working on the token counts or the weighted ranking — those are `item_126` through `item_129`.

# Problem
- Once tokens are weighted into an input-equivalent figure (`item_129`), a currency amount is one multiplication away: the weighted figure times the model's input price per million tokens. The weighting has already absorbed every other ratio.
- What blocks it is not the arithmetic but attribution: cdx does not reliably know which model served a run. The launch history stores the session's configured `launch` settings, where `model` is optional and frequently unset because the session takes the provider's default. A weighted figure attributed to the wrong price tier is worse than no figure at all.
- The provider transcript does record the model per message, and a single session can span more than one model, so a run's cost is not necessarily a single tier multiplied by a single total.
- Prices are the one input here that genuinely goes stale, unlike the ratios in `item_129`. Anything hardcoded will be wrong after the next price change, and cdx must keep reporting usage offline, so it cannot resolve prices over the network at read time.
- Cross-provider comparison is a further open question: Codex pricing is not Anthropic's, so a single currency column spanning both providers needs each provider's own prices, not one table.

# Scope
- In:
  - Establish which model served a run, reading it from the provider transcript rather than inferring it from the session's configured launch settings, and handle a run that spans several models rather than assuming one.
  - Record the served model on the run entry so the attribution is durable and auditable after the fact.
  - Put prices in configuration with a documented default, not in code, so a price change is an edit rather than a release.
  - Compute and display a currency figure from the weighted total and the model's input price.
  - Make the figure's provenance legible: state which prices were used and when they were last reviewed, so a stale number is visibly stale rather than silently wrong.
  - Report absence rather than a guess when the model cannot be determined or its price is unknown.
  - Decide explicitly whether the currency column spans providers or is Claude-only in the first pass, and state the decision.
- Out:
  - No network price lookup — cdx reports usage offline.
  - No billing integration or invoice reconciliation; this is an estimate at list prices, not an account statement.
  - No change to the weighting itself, which `item_129` settles.
  - No retroactive costing of runs already in launch history that carry no model attribution.

# Acceptance criteria
- Given a run whose transcript names the serving model, that model is recorded on the run entry and used to price it.
- Given a run whose model cannot be determined, the cost is reported as absent rather than priced at a default tier.
- Given a run spanning more than one model, the documented rule is applied and asserted by a test naming the expected figure.
- Given a price change, updating the configured price changes the reported figures with no code edit.
- The displayed cost states which price set produced it and when that set was last reviewed.
- The README states that the figure is an estimate at list prices, and whether it covers one provider or both.

# AC Traceability
- request-AC12 -> This backlog slice. Proof: Given a run whose transcript names the serving model, that model is recorded on the run entry and used to price it.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_049_token_numbers_a_user_can_act_on`
- Architecture decision(s): (none yet)
- Request: `req_063_make_cdx_stats_report_the_tokens_a_session_actually_spent`
- Primary task(s): `task_073_orchestrate_truthful_token_accounting_for_cdx_stats`

# Priority
- Priority: Low
- Rationale: The weighted figure already fixes the ranking, which was the actionable problem. Currency is a convenience on top, and it carries the only genuinely perishable input in the request.
