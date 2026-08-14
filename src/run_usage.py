"""What a cdx usage record means, and the only place that decides it.

Three code paths read provider usage -- this module for headless stdout,
`interactive_usage` for a terminal launch, `provider_background` for a native
background close-out -- and each used to compute the fields its own way. They
disagreed in every direction at once: one dropped cache from the total, one
counted it twice, one omitted the cached field entirely. All three wrote into
the same launch history and the same `cdx stats` column, so the table mixed
definitions without saying so.

The definitions below are therefore normative, not a suggestion:

  input_tokens          Uncached input only. Claude reports it this way
                        natively; Codex does not, so its cache-inclusive count
                        is reduced here rather than left for a reader to guess.
  cache_creation_tokens Tokens written to the provider's prompt cache.
  cache_read_tokens     Tokens served from it.
  cached_input_tokens   cache_creation + cache_read. Kept because it is a
                        published field of `cdx run --json`, and because the
                        stats table shows one CACHE column. It is a derived
                        sum, never a source.
  output_tokens         Generated tokens.
  reasoning_tokens      Reasoning counted separately by the provider. Codex
                        reports one; Claude does not and never will -- it bills
                        thinking as output, so those tokens are already inside
                        output_tokens. An empty REASON column for Claude is
                        correct, not a gap to fill.
  total_tokens          input + cache_creation + cache_read + output. Cache is
                        the bulk of real consumption, so a total that excludes
                        it is not a slightly-wrong total, it is a different
                        quantity.

Cache creation and cache read are separate fields because they cost very
differently -- 1.25x and 0.1x of uncached input -- and a weighted figure cannot
recover the split once they are summed.

Absence stays absent: `None` means "not reported", which is not zero. Only
`normalize_usage` may derive `cached_input_tokens` and `total_tokens`, so no
caller can invent a fourth arithmetic.
"""

import json

#: Order matters only for readability; every consumer addresses these by name.
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)
#: The two fields `normalize_usage` derives. Never read them from a provider.
DERIVED_USAGE_KEYS = ("cached_input_tokens", "total_tokens")
SUPPORTED_PROVIDERS = {"claude", "codex"}


def empty_usage():
    return {key: None for key in USAGE_KEYS}


def normalize_usage(input_tokens=None, cache_creation_tokens=None, cache_read_tokens=None,
                    output_tokens=None, reasoning_tokens=None):
    """Build a usage record from the four measured quantities.

    The derived fields are computed here and only here. A record whose parts are
    all absent stays fully absent rather than becoming a row of zeros: a session
    cdx could not measure must not read as a session that spent nothing.
    """
    parts = {
        "input_tokens": _non_negative(input_tokens),
        "cache_creation_tokens": _non_negative(cache_creation_tokens),
        "cache_read_tokens": _non_negative(cache_read_tokens),
        "output_tokens": _non_negative(output_tokens),
        "reasoning_tokens": _non_negative(reasoning_tokens),
    }
    if all(value is None for value in parts.values()):
        return empty_usage()
    cached = _sum_present(parts["cache_creation_tokens"], parts["cache_read_tokens"])
    total = _sum_present(
        parts["input_tokens"],
        parts["cache_creation_tokens"],
        parts["cache_read_tokens"],
        parts["output_tokens"],
    )
    return {**parts, "cached_input_tokens": cached, "total_tokens": total}


#: What each token class costs relative to one uncached input token.
#:
#: Ratios, not prices. Across the current model lineup output is 5x input on
#: every model and the cache multipliers do not vary by model either; only the
#: absolute price per million tokens changes between tiers. So a weighted
#: figure needs no per-model table and cannot go stale the way a price list
#: would -- which is exactly why cdx weights rather than prices.
#:
#: The cache-write multiplier is the five-minute TTL. A one-hour TTL is 2x, and
#: nothing in a transcript says which was used, so this under-weights long-TTL
#: writes. Cache writes are a small share of a cache-heavy session's tokens, so
#: the error is bounded and stated rather than hidden behind a guess.
USAGE_WEIGHTS = {
    "input_tokens": 1.0,
    "cache_creation_tokens": 1.25,
    "cache_read_tokens": 0.1,
    "output_tokens": 5.0,
}


def weighted_usage(usage):
    """Consumption in uncached-input-equivalent tokens, or None if unknown.

    A raw token total ranks a cache read equal to an output token worth fifty
    times more, and cache reads are typically the overwhelming majority of
    tokens -- so a raw total is very nearly a measure of cache reads alone.
    That is not the ranking anyone reading `cdx stats` is looking for.

    `reasoning_tokens` is deliberately absent from the weights: Codex reports
    it as a subset of its output, and adding it would count those tokens twice.
    """
    if not isinstance(usage, dict):
        return None
    present = [
        weight * usage[key]
        for key, weight in USAGE_WEIGHTS.items()
        if usage.get(key) is not None
    ]
    if not present:
        return None
    return int(round(sum(present)))


#: List prices in dollars per million *uncached input* tokens. Every other rate
#: is already folded into USAGE_WEIGHTS, so one number per model prices a run.
#:
#: This is the one genuinely perishable input in cdx's usage accounting: the
#: ratios above hold across the lineup, but these change when a provider
#: reprices. Override with CDX_TOKEN_PRICES (JSON, model -> dollars per MTok)
#: rather than editing code, and treat an unknown model as unpriced instead of
#: assuming a tier.
#:
#: Anthropic models only, deliberately. cdx can state these with confidence; it
#: cannot do the same for another vendor's, and a plan-based subscription makes
#: "list price per MTok" a shakier notion there anyway. A Codex run is measured
#: and weighted like any other -- only the currency column stays empty, and the
#: totals line names the model so CDX_TOKEN_PRICES can fill it in. Shipping a
#: guessed price would be the one failure this whole definition exists to
#: prevent, committed in the column users trust most.
DEFAULT_TOKEN_PRICES = {
    "claude-fable-5": 10.0,
    "claude-mythos-5": 10.0,
    "claude-opus-5": 5.0,
    "claude-opus-4-8": 5.0,
    "claude-opus-4-7": 5.0,
    "claude-opus-4-6": 5.0,
    "claude-sonnet-5": 3.0,
    "claude-sonnet-4-6": 3.0,
    "claude-haiku-4-5": 1.0,
}
TOKEN_PRICES_REVIEWED = "2026-08-14"
TOKEN_PRICES_ENV = "CDX_TOKEN_PRICES"


def token_prices(env=None):
    """The price table in force, and where it came from."""
    import os

    environment = env if env is not None else os.environ
    raw = environment.get(TOKEN_PRICES_ENV)
    if raw:
        try:
            overrides = json.loads(raw)
        except ValueError:
            return dict(DEFAULT_TOKEN_PRICES), f"built-in, reviewed {TOKEN_PRICES_REVIEWED} ({TOKEN_PRICES_ENV} ignored: not JSON)"
        if isinstance(overrides, dict):
            merged = {**DEFAULT_TOKEN_PRICES}
            merged.update({str(k): float(v) for k, v in overrides.items()})
            return merged, TOKEN_PRICES_ENV
    return dict(DEFAULT_TOKEN_PRICES), f"built-in, reviewed {TOKEN_PRICES_REVIEWED}"


def estimate_cost(usage, model, prices=None):
    """Dollars this usage would list at, or None when it cannot be priced.

    ponytail: a run is priced at one model -- the one serving its most recent
    record -- rather than split per model. A session that switches models
    mid-run is priced at the newer one. Upgrade path if that matters: have the
    readers return a per-model breakdown and difference each model separately;
    the delta machinery already generalizes to a dict.

    An unknown or absent model yields None. Pricing it at a default tier would
    turn "cdx does not know" into a number someone might believe.
    """
    if not model:
        return None
    table = prices if prices is not None else token_prices()[0]
    rate = table.get(model)
    if rate is None:
        return None
    equivalent = weighted_usage(usage)
    if equivalent is None:
        return None
    return equivalent / 1_000_000 * rate


def claude_usage_dedup_key(record):
    """What identifies one *billed* Claude API response in a transcript.

    Not the record's `uuid`. A Claude Code transcript writes the same assistant
    response under several uuids -- measured on one real 2741-row transcript:
    2741 distinct uuids for 1765 distinct responses, so 36% of the rows were
    repeats of a call the account paid for once. Summing per uuid inflated that
    file's tokens by about 1.55x against an independent reader of the same
    bytes.

    The billed unit is the API response, so the key is the message id paired
    with the request that produced it. `uuid` remains the fallback for records
    that carry neither, which is the older transcript shape.

    Returns None when the record carries no identity at all. That means "cannot
    prove this is a repeat", and the caller must count it: two identity-less
    records collapsing into one would discard usage that was really spent,
    which is a worse error than counting a duplicate.
    """
    message = record.get("message") or {}
    message_id = message.get("id")
    request_id = record.get("requestId")
    if message_id and request_id:
        return ("api", message_id, request_id)
    if message_id:
        return ("message", message_id)
    uuid = record.get("uuid")
    return ("uuid", uuid) if uuid else None


def coerce_usage(usage):
    """Bring an already-built usage record onto the canonical shape.

    For boundaries that receive a record rather than measure one -- the run
    registry, which publishes what it stores. Missing fields become absent
    rather than zero, and the derived figures are recomputed from the parts, so
    a record built before this definition existed cannot carry a stale total
    into the JSON surfaces.
    """
    if not isinstance(usage, dict):
        return None
    record = normalize_usage(
        input_tokens=usage.get("input_tokens"),
        cache_creation_tokens=usage.get("cache_creation_tokens"),
        cache_read_tokens=usage.get("cache_read_tokens"),
        output_tokens=usage.get("output_tokens"),
        reasoning_tokens=usage.get("reasoning_tokens"),
    )
    if record["cached_input_tokens"] is None:
        # A legacy record carrying only the fused figure: keep it visible rather
        # than dropping a number someone already recorded, but leave the split
        # absent because it genuinely is not recoverable.
        record["cached_input_tokens"] = _first_int(usage.get("cached_input_tokens"))
    return record


def _non_negative(value):
    parsed = _first_int(value)
    return parsed


def _sum_present(*values):
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def extract_run_usage(provider, stdout_path):
    if not stdout_path or not provider:
        return empty_usage()
    if provider not in SUPPORTED_PROVIDERS:
        return empty_usage()
    try:
        with open(stdout_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return empty_usage()
    if not text.strip():
        return empty_usage()

    records = _parse_json_records(text)
    if not records:
        return empty_usage()

    usage = _extract_usage_from_records(records)
    if not _has_usage(usage):
        return empty_usage()
    return usage


def _parse_json_records(text):
    stripped = text.strip()
    try:
        return [json.loads(stripped)]
    except json.JSONDecodeError:
        pass

    records = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # A single truncated/noisy line must not discard the usage
            # carried by every other valid JSONL record in the stream.
            continue
    return records


def _extract_usage_from_records(records):
    latest = None
    for record in records:
        candidate = _find_usage(record)
        if _has_usage(candidate):
            latest = candidate
    return latest or empty_usage()


def _find_usage(value):
    if isinstance(value, dict):
        direct = _usage_from_dict(value)
        if _has_usage(direct):
            return direct
        for child in value.values():
            found = _find_usage(child)
            if _has_usage(found):
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_usage(child)
            if _has_usage(found):
                return found
    return empty_usage()


def _usage_from_dict(value):
    """Map one provider usage object onto the canonical fields.

    This used to fold the cache counts into `input_tokens` *and* report them
    again as `cached_input_tokens`, so IN and CACHE both counted the same
    tokens. The fix is not arithmetic in this function: it is that the split
    parts go to `normalize_usage`, which owns every derived figure.
    """
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else value
    if not isinstance(usage, dict):
        return empty_usage()

    cache_creation = _first_int(usage.get("cache_creation_input_tokens"))
    cache_read = _first_int(usage.get("cache_read_input_tokens"))
    if cache_creation is None and cache_read is None:
        # Codex reports one cached figure with no creation/read split; it is a
        # read by construction, since nothing else could have written it.
        cache_read = _first_int(usage.get("cached_input_tokens"))

    input_tokens = _int_value(usage.get("input_tokens"), usage.get("prompt_tokens"))
    input_tokens = _uncached_input(input_tokens, cache_read, usage)

    return normalize_usage(
        input_tokens=input_tokens,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read,
        output_tokens=_int_value(usage.get("output_tokens"), usage.get("completion_tokens")),
        reasoning_tokens=_int_value(
            usage.get("reasoning_tokens"),
            usage.get("reasoning_output_tokens"),
            _nested_int(usage, "output_tokens_details", "reasoning_tokens"),
            _nested_int(usage, "completion_tokens_details", "reasoning_tokens"),
        ),
    )


def _uncached_input(input_tokens, cache_read, usage):
    """Reduce a cache-inclusive input count to its uncached remainder.

    Two dialects reach this function. Anthropic reports `input_tokens` as the
    uncached remainder already and carries the `cache_*_input_tokens` pair.
    OpenAI-shaped records -- Codex among them -- report a bare
    `cached_input_tokens` that is a *subset* of `input_tokens`, so leaving it
    alone would count those tokens in both IN and CACHE.

    The subset relationship is the assumption, and it is checked rather than
    trusted: a record where the cached count exceeds the input count cannot be
    a subset, so that record is left alone instead of being forced to zero.
    Guessing wrong in that direction would silently erase real input tokens,
    which is the failure this whole definition exists to stop.
    """
    if input_tokens is None or not cache_read:
        return input_tokens
    if usage.get("cache_creation_input_tokens") is not None:
        return input_tokens
    if usage.get("cache_read_input_tokens") is not None:
        return input_tokens
    if usage.get("cached_input_tokens") is None:
        return input_tokens
    if cache_read > input_tokens:
        return input_tokens
    return input_tokens - cache_read


def _nested_int(value, parent, child):
    nested = value.get(parent)
    if not isinstance(nested, dict):
        return None
    return nested.get(child)


def _first_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _int_value(*values):
    parsed = [_first_int(value) for value in values]
    parsed = [value for value in parsed if value is not None]
    if not parsed:
        return None
    return sum(parsed)


def _has_usage(usage):
    return isinstance(usage, dict) and any(usage.get(key) is not None for key in USAGE_KEYS)
