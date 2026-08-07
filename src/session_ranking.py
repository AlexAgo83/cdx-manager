"""The single rule for ordering sessions by desirability.

cdx used to answer "which session should this work go to" twice, with two
algorithms that disagreed: one behind `cdx select` and `cdx run --provider`,
another behind `cdx next`, the `cdx status` recommendation, and `cdx ready`.
Each knew something the other did not — the first honored the user's
`--priority` and filtered by provider, the second understood credits and reset
scheduling — so the answer depended on which command you asked.

This module is the merge. Every selector calls `rank_sessions`; the callers
differ only in the options they pass and what they do with the result.
"""

from .config import REASONING_EFFORT_VALUES

# Below this, a session has nothing useful left in its window.
USABLE_AVAILABLE_THRESHOLD = 5

# Usability classes, best first.
USABLE_TIER = 3
BLOCKED_WITH_RESET_TIER = 2
RESET_KNOWN_TIER = 1
UNKNOWN_TIER = 0

# Compared in order, best first. `cdx select` publishes this as its
# `selection_policy`, built from these tuples, so the published policy cannot
# describe an order the code does not apply.
#
# The order after the first two factors depends on whether the session can be
# used right now, which the recommendation ranking already did and which is
# worth keeping: for a session you can use, what matters is cost and headroom;
# for one you cannot, what matters is when it comes back.
LEADING_FACTORS = ("usability", "priority")
USABLE_FACTORS = ("credits", "availability", "reset")
BLOCKED_FACTORS = ("reset", "credits", "availability")
TRAILING_FACTORS = ("reasoning_effort", "name")

RANKING_FACTORS = LEADING_FACTORS + USABLE_FACTORS + TRAILING_FACTORS


def factor_order(usable):
    """The factors, in the order they are compared, for one usability class."""
    return LEADING_FACTORS + (USABLE_FACTORS if usable else BLOCKED_FACTORS) + TRAILING_FACTORS

FACTOR_DESCRIPTIONS = {
    "usability": "usable now, then blocked with a known reset, then reset known, then unknown",
    "priority": "higher configured --priority first",
    "credits": "sessions without credits first, to spend included quota before paid credits",
    "availability": "higher remaining availability first",
    "reset": "earlier known reset first",
    "reasoning_effort": "lower configured reasoning effort first, to leave stronger sessions free",
    "name": "session name, so the order is deterministic",
}

# Candidate filters, which exclude rather than order. Kept separate because
# describing them as ranking stages is what made the old published policy wrong.
FILTER_DESCRIPTIONS = {
    "enabled": "disabled sessions are never candidates",
    "authenticated": "logged-out sessions are never candidates; they cannot serve work",
    "provider": "only sessions for the requested provider (when a provider is given)",
    "min_reasoning_effort": "only sessions configured at or above the requested effort (when given)",
    "require_ready": "only sessions confirmed authenticated with availability left (when readiness is required)",
}


def reasoning_rank(value):
    try:
        return REASONING_EFFORT_VALUES.index(str(value or "low").lower())
    except ValueError:
        return -1


def _is_usable_now(row):
    available = row.get("available_pct")
    return available is not None and available > USABLE_AVAILABLE_THRESHOLD


def _usability_tier(row, now_ts, reset_timestamp_fn):
    """Higher is better.

    Preserved from the recommendation ranking, which distinguished "blocked but
    coming back at a known time" from "blocked with no information". The
    headless ranking flattened both into "unavailable", losing the distinction
    that makes `cdx next` useful.
    """
    reset_ts = reset_timestamp_fn(row)
    if _is_usable_now(row):
        return USABLE_TIER
    if reset_ts is not None and reset_ts >= now_ts:
        return BLOCKED_WITH_RESET_TIER
    if reset_ts is not None:
        return RESET_KNOWN_TIER
    return UNKNOWN_TIER


def _factor_values(row, now_ts, reset_timestamp_fn):
    """This row's value for each factor, already oriented so higher is better."""
    reset_ts = reset_timestamp_fn(row)
    available = row.get("available_pct")
    try:
        priority = int(row.get("priority") or 0)
    except (TypeError, ValueError):
        priority = 0
    return {
        "usability": _usability_tier(row, now_ts, reset_timestamp_fn),
        # Ranked inside a usability tier, never across one: a session that
        # cannot serve the request does not become the right choice by being
        # preferred. Priority expresses which usable session to favour.
        "priority": priority,
        # Sessions *without* credits first: spend the included quota before
        # burning paid credits. Inverting this is an easy mistake — the factor
        # is named for what it looks at, not for what it prefers.
        "credits": 0 if row.get("credits") is not None else 1,
        "availability": float(available) if available is not None else -1.0,
        "reset": -reset_ts if reset_ts is not None else float("-inf"),
        # Negated: the weakest configured session that still clears the floor
        # wins, so a stronger one stays free for work that needs it. This was
        # previously implied by an un-negated term in a sort tuple; it is a
        # deliberate cost preference and is stated here rather than inferred.
        "reasoning_effort": -reasoning_rank(row.get("reasoning_effort")),
        "name": row.get("session_name") or "",
    }


def _sort_key(values):
    # Sessions are bucketed by usability first, so every candidate compared
    # beyond that point shares a usability class and therefore a factor order.
    key = []
    for factor in factor_order(values["usability"] == USABLE_TIER):
        value = values[factor]
        # Names sort ascending; every other factor is "higher is better", so
        # they are negated to sort descending under one ascending sort.
        key.append(value if factor == "name" else _negate(value))
    return tuple(key)


def _negate(value):
    return -value if isinstance(value, (int, float)) else value


def deciding_factor(winner_values, runner_up_values):
    """The first factor that separated the winner from the runner-up.

    Returns None when there was nobody to compare against, so a caller can say
    "only candidate" instead of naming a factor that decided nothing.
    """
    if runner_up_values is None:
        return None
    for factor in factor_order(winner_values["usability"] == USABLE_TIER):
        if winner_values[factor] != runner_up_values[factor]:
            return factor
    return None


def candidate_rows(rows, provider=None, require_ready=False, min_reasoning_effort=None):
    """Rows eligible for selection, applying the filters described above.

    Logged-out sessions are excluded unconditionally. The headless path used to
    admit them unless `--require-ready` was passed, so `cdx select` could return
    a session that could not possibly run anything.
    """
    minimum = reasoning_rank(min_reasoning_effort) if min_reasoning_effort else None
    candidates = []
    for row in rows:
        if row.get("enabled", True) is False:
            continue
        if provider is not None and row.get("provider") != provider:
            continue
        if _row_is_logged_out(row):
            continue
        if minimum is not None and reasoning_rank(row.get("reasoning_effort")) < minimum:
            continue
        if require_ready and not _row_is_ready(row):
            continue
        candidates.append(row)
    return candidates


def _row_is_logged_out(row):
    if row.get("provider") in ("antigravity", "ollama"):
        return False
    return str(row.get("auth_status") or "").strip().lower() == "logged_out"


def _row_is_ready(row):
    """Ready to receive a run right now.

    Stricter than "not logged out": an unknown auth state is not readiness.
    `cdx run --provider` asks for readiness precisely so it does not hand work
    to a session that will fail at launch, and the headless ranking required a
    confirmed `authenticated` here before the two rankings were merged.
    Sessions that are only recommended, rather than selected to run, do not
    pass `require_ready` and so are still surfaced with an unknown state.
    """
    if row.get("provider") not in ("antigravity", "ollama"):
        if str(row.get("auth_status") or "").strip().lower() != "authenticated":
            return False
    return _row_has_availability(row)


def _row_has_availability(row):
    available = row.get("available_pct")
    if available is None:
        # Unknown is not the same as empty. Excluding it here would make a
        # never-probed session permanently unselectable; the caller warns
        # instead, so the decision is visible rather than silent.
        return True
    try:
        return float(available) > 0
    except (TypeError, ValueError):
        return False


def rank_sessions(rows, now_ts, reset_timestamp_fn, provider=None, require_ready=False,
                  min_reasoning_effort=None):
    """Candidate rows ordered best-first, with why the winner won.

    Returns (ordered_rows, decision) where decision names the deciding factor,
    or None when there was only one candidate.
    """
    candidates = candidate_rows(
        rows,
        provider=provider,
        require_ready=require_ready,
        min_reasoning_effort=min_reasoning_effort,
    )
    scored = [
        (row, _factor_values(row, now_ts, reset_timestamp_fn))
        for row in candidates
    ]
    scored.sort(key=lambda item: _sort_key(item[1]))
    ordered = [row for row, _values in scored]
    if not scored:
        return ordered, None
    runner_up = scored[1][1] if len(scored) > 1 else None
    return ordered, deciding_factor(scored[0][1], runner_up)


def selection_policy():
    """The published description of the ranking, built from the ranking itself.

    Derived rather than written, so a change to `RANKING_FACTORS` changes what
    `cdx select` reports without anyone remembering to edit a string. The
    previous hand-written policy omitted the reasoning-effort tie-break and
    described a candidate filter as a sort stage.
    """
    return {
        "factors": [
            {"name": factor, "description": FACTOR_DESCRIPTIONS[factor]}
            for factor in RANKING_FACTORS
        ],
        "filters": [
            {"name": name, "description": description}
            for name, description in FILTER_DESCRIPTIONS.items()
        ],
        "usable_order": list(factor_order(True)),
        "blocked_order": list(factor_order(False)),
        "summary": "_then_".join(factor_order(True)),
    }
