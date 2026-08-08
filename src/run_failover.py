"""Deciding whether a finished run stopped because its account ran out.

Two independent signals have to agree before cdx moves a task to another
account, because the two ways of being wrong are not symmetric. Missing a rate
limit costs nothing new: the run fails exactly as it does today. Inventing one
migrates a healthy run off a working account, discards its progress, and
consumes a second account's quota to redo it. So every ambiguous case here
resolves to "not rate limited".

Signal one is the provider's own structured output, which both headless paths
already produce - `codex exec --json` emits JSONL events, and the claude spec
passes `--print --output-format json`. Signal two is the account's rate-limit
status, refreshed once and read through the existing status pipeline - where
`rate_limit_reached` is the strongest evidence available, being the provider's
own typed reason rather than a threshold or a sentence.

The matchers below are deliberately the only place that knows what exhaustion
looks like on the wire. That shape is version-specific and is the part most
likely to drift, so it is one function per provider and nothing else in the
codebase reads provider output for this purpose.
"""

import json
import os

from .config import PROVIDER_CLAUDE, PROVIDER_CODEX

MAX_FAILOVER_TRANSITIONS = 4

# Read from the tail: a rate limit ends the run, so its marker is near the end,
# and a long transcript should not be loaded whole to find it.
_MAX_TAIL_BYTES = 64 * 1024

# Observed against codex-cli 0.147.0 on an exhausted account:
#   {"type":"error","message":"Your workspace is out of credits. Add credits to continue."}
#   {"type":"turn.failed","error":{"message":"Your workspace is out of credits..."}}
# "out of credits" was missing from the first version of this list, which is why
# it never matched anything real. Credit exhaustion and a rate limit are the
# same thing for this decision: the account cannot serve the task, try another.
# Claude's own wording, captured from a real transcript on this machine:
#   API error: 429 {"type":"error","error":{"type":"rate_limit_error",
#     "message":"Usage credits are required for this model.", ...}}
# `rate_limit_error` is already covered by "rate_limit" below. Worth knowing:
# that same 429 is also how an org policy disabling a model is reported
# (`disabled_reason: org_level_disabled`), which no amount of failing over
# would fix - every account in the org hits it. The status corroboration in
# `failover_reason` is what keeps that case from migrating a healthy run.
_RATE_LIMIT_MARKERS = (
    "out of credits",
    "rate_limit",
    "rate limit",
    "usage limit",
    "quota exceeded",
    "insufficient_quota",
)

# Records the provider itself labelled as failures. Scoping the search to these
# is what keeps assistant prose out of the decision - the model's own words are
# never inside a record of this shape. The first version instead excluded the
# `message` key everywhere, which also excluded the field codex actually puts
# its error text in, so nothing could ever match.
_CODEX_ERROR_TYPES = ("error", "turn.failed", "thread.failed")


def _read_tail(path):
    if not path or not os.path.isfile(path):
        return ""
    try:
        size = os.path.getsize(path)
        with open(path, encoding="utf-8", errors="replace") as handle:
            if size > _MAX_TAIL_BYTES:
                handle.seek(size - _MAX_TAIL_BYTES)
            return handle.read()
    except OSError:
        return ""


def _error_texts(provider, record):
    """Message strings from a record the provider marked as a failure.

    Returns nothing for any other record, which is what keeps the assistant's
    own words out of the decision: prose lives in successful results, never in
    an error record.
    """
    if not isinstance(record, dict):
        return []
    texts = []
    if provider == PROVIDER_CODEX:
        if str(record.get("type") or "") not in _CODEX_ERROR_TYPES:
            return []
        texts.append(record.get("message"))
        error = record.get("error")
        if isinstance(error, dict):
            texts.append(error.get("message"))
    elif provider == PROVIDER_CLAUDE:
        # `--print --output-format json` returns one result object; its own
        # is_error flag says whether `result` holds an error or an answer.
        if record.get("is_error") is not True:
            return []
        texts.append(record.get("result"))
        texts.append(record.get("subtype"))
        error = record.get("error")
        if isinstance(error, dict):
            texts.append(error.get("message"))
    return [text for text in texts if isinstance(text, str)]


def _mentions_exhaustion(texts):
    return any(
        marker in text.lower()
        for text in texts
        for marker in _RATE_LIMIT_MARKERS
    )


def _structured_records(provider, text):
    """The structured payloads a provider wrote, newest last.

    Codex emits one JSON object per line; claude emits a single object. Lines
    that do not decode are skipped rather than pattern-matched as raw text:
    unparsed output is not a signal, it is an absence of one.
    """
    records = []
    if not text:
        return records
    if provider == PROVIDER_CODEX:
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        return records
    if provider == PROVIDER_CLAUDE:
        stripped = text.strip()
        start = stripped.find("{")
        if start >= 0:
            try:
                records.append(json.loads(stripped[start:]))
            except ValueError:
                return records
    return records


def looks_rate_limited(provider, run_info):
    """Whether the provider's structured output says the account is exhausted.

    This is the weaker of the two signals and is never acted on alone; see
    `should_fail_over`.
    """
    if provider not in (PROVIDER_CODEX, PROVIDER_CLAUDE):
        return False
    if run_info.get("timed_out"):
        # A timeout is cdx's own deadline, not the provider's verdict.
        return False
    if run_info.get("returncode") == 0:
        return False
    for record in _structured_records(provider, _read_tail(run_info.get("stdout_path"))):
        if _mentions_exhaustion(_error_texts(provider, record)):
            return True
    return False


def status_confirms_exhaustion(row):
    """Whether a freshly refreshed status row agrees the account is spent.

    An unreadable or empty row is not a confirmation. Treating "no status" as
    exhaustion would make every probe failure look like a rate limit.
    """
    if not row:
        return False
    # The provider's own typed reason, when it gives one. Authoritative and
    # language-free: `workspace_owner_credits_depleted` says the account cannot
    # serve the task even when both percentage windows still read healthy,
    # which is a case the thresholds below would miss entirely.
    if row.get("rate_limit_reached"):
        return True
    if row.get("blocking"):
        return True
    for key in ("remaining_5h_pct", "remaining_week_pct"):
        value = row.get(key)
        if isinstance(value, (int, float)) and value <= 0:
            return True
    return False


def provider_reported_failure(provider, run_info):
    """A failure the provider itself emitted, whatever it says.

    Deliberately wording-free. A timeout is cdx's own deadline, and a zero exit
    is not a failure; everything else that produced a provider error record
    counts.
    """
    if provider not in (PROVIDER_CODEX, PROVIDER_CLAUDE):
        return False
    if run_info.get("timed_out") or run_info.get("returncode") == 0:
        return False
    for record in _structured_records(provider, _read_tail(run_info.get("stdout_path"))):
        if _error_texts(provider, record):
            return True
    return False


def failover_reason(provider, run_info, status_row):
    """Why this run should move, or None to stay put.

    Two independent routes, because relying on either alone has been shown to
    fail:

    `provider_reported_exhaustion` - the provider said so in words cdx
    recognises. Precise, but the wording is not one thing: an enterprise
    workspace out of credits, a personal plan hitting its 5-hour window, and
    Claude's own phrasing are all different sentences, and only the first has
    ever been observed. Matching prose alone would silently miss the rest.

    `account_status_exhausted` - the account's own rate-limit status says it has
    nothing left, and the run failed. This is the authoritative route: it comes
    from the provider's rate-limit API rather than from English, so it holds for
    plans and providers whose wording nobody has seen. An account at zero cannot
    serve the task no matter which sentence it used to say so.

    Status confirmation is required either way, so a healthy account is never
    abandoned on the strength of a matched phrase.
    """
    if not status_confirms_exhaustion(status_row):
        return None
    if looks_rate_limited(provider, run_info):
        return "provider_reported_exhaustion"
    if provider_reported_failure(provider, run_info):
        return "account_status_exhausted"
    return None


def should_fail_over(provider, run_info, status_row):
    return failover_reason(provider, run_info, status_row) is not None
