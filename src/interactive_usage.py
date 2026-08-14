"""Best-effort usage readers for interactive provider sessions.

Three providers report usage and one does not:

- Claude and Codex write their own JSONL transcripts, resolved by the
  conversation id cdx already holds.
- Ollama writes nothing. Its counts exist only in `--verbose` terminal output,
  so they are parsed out of the PTY capture cdx takes for every launch.
- Antigravity has no retrievable source. Its conversation history is
  schema-less binary protobuf under `~/.gemini/antigravity-cli/conversations/`
  with no `.proto` available to decode field numbers into token counts, and its
  logs are plain glog with no usage-bearing line at any verbosity `agy --help`
  exposes. This was investigated and is a dead end, not an oversight -- do not
  spend the afternoon rediscovering it.
"""

import json
import os
import re
import time

from .run_usage import claude_usage_dedup_key, normalize_usage
from .status_source import _normalize_terminal_transcript

MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
MAX_TRANSCRIPT_CANDIDATES = 1000
MAX_TRANSCRIPT_SCAN_SECONDS = 1

#: Codex repeats the conversation id at the end of each rollout filename.
_ROLLOUT_NAME = re.compile(r"^rollout-.*-([0-9a-fA-F-]{36})\.jsonl$")

#: Ollama's `--verbose` block, one per response. Captured from a real
#: `ollama run smollm2:135m --verbose` on 0.32.11:
#:
#:     total duration:       1.159523666s
#:     prompt eval count:    32 token(s)
#:     eval count:           58 token(s)
#:
#: `prompt eval count` is the prompt actually evaluated for that response and
#: `eval count` what it generated, so a multi-turn session contributes one
#: block per turn and they sum. Ollama reports no cache and no reasoning: it is
#: a local runner with no prompt cache to read from, so those fields stay
#: absent rather than zero.
_OLLAMA_PROMPT_TOKENS = re.compile(r"^\s*prompt eval count:\s*(\d+)\s*token", re.M)
_OLLAMA_EVAL_TOKENS = re.compile(r"^\s*eval count:\s*(\d+)\s*token", re.M)

#: How the transcript that produced a usage record was found. An id match is
#: the session's own transcript by construction; a recency match is a guess
#: that happened to be the newest file, and must not read as the same thing.
MATCH_CONVERSATION_ID = "conversation_id"
MATCH_RECENCY = "recency"
#: The run's own terminal capture -- no ambiguity to resolve.
MATCH_RUN_TRANSCRIPT = "run_transcript"


def extract_interactive_usage(provider, auth_home, started_at=None, conversation_id=None,
                              terminal_transcript=None):
    """Return this session's provider-native usage, and how it was found.

    Provider transcripts are not stable public APIs.  A missing or changed
    record is therefore ordinary absence, never a launch failure.

    Resolution is by conversation id whenever the session has one: cdx mints
    Claude's itself and passes it as `--session-id`, and observes Codex's back
    after a run, so the session's own transcript is addressable by name. The
    mtime scan that used to decide this returned whichever file in the whole
    provider home was touched most recently, which is why sessions reported
    three runs and eighteen output tokens -- they were being billed for an
    unrelated file.

    A session with an id whose transcript cannot be found reports absence
    rather than falling back to that scan: a wrong attribution is worse than a
    missing one, and it is the failure this replaces.
    """
    path, match = resolve_transcript(
        provider, auth_home, started_at, conversation_id, terminal_transcript)
    if not path:
        return None, None, None, None
    try:
        if os.path.getsize(path) > MAX_TRANSCRIPT_BYTES:
            return None, path, match, None
        with open(path, encoding="utf-8", errors="replace") as handle:
            usage, model = _READERS.get(provider, _claude_usage)(handle)
        return usage, path, match, model
    except OSError:
        return None, path, match, None


def resolve_transcript(provider, auth_home, started_at=None, conversation_id=None,
                       terminal_transcript=None):
    """The transcript belonging to this session, and how confidently."""
    if provider == "ollama":
        # No provider-native transcript exists to resolve. The run's own PTY
        # capture is the only record, and the caller already knows its path --
        # which makes this the most certain attribution of the three, not the
        # least: there is no file to pick wrongly.
        return (terminal_transcript, MATCH_RUN_TRANSCRIPT) if terminal_transcript else (None, None)
    if not auth_home:
        return None, None
    if conversation_id:
        path = _transcript_for_conversation(provider, auth_home, conversation_id)
        if _covers_run(path, started_at) or provider != "codex":
            return path, MATCH_CONVERSATION_ID
        # Codex mints its conversation id itself and cdx can only read it back
        # *after* the run, so at this point the session still names the
        # previous conversation. Its rollout is untouched by this run, and
        # differencing it yields a zero -- which is how a real codex turn came
        # to report no usage at all.
        #
        # Falling back to recency is safe here in a way it was not for Claude:
        # a Codex rollout lives under the session's own auth home, so the
        # newest one touched during this run is this session's current
        # conversation, not somebody else's file.
    path = _latest_transcript(provider, auth_home, started_at)
    return path, (MATCH_RECENCY if path else None)


def _covers_run(path, started_at):
    """Whether this transcript was written during the run, so it can hold it."""
    cutoff = _timestamp(started_at)
    if not path:
        return False
    if cutoff is None:
        return True
    try:
        return os.path.getmtime(path) >= cutoff
    except OSError:
        return False


def conversation_transcript(provider, auth_home, conversation_id):
    """The transcript file for this exact conversation, or None if it has none.

    Answers "does this conversation actually exist" without the fallbacks
    `resolve_transcript` applies: a caller asking whether a resume will work
    must not be told yes because some *other* conversation was found.
    """
    if not auth_home or not conversation_id:
        return None
    return _transcript_for_conversation(provider, auth_home, conversation_id)


def _transcript_for_conversation(provider, auth_home, conversation_id):
    if provider == "codex":
        return _codex_rollout_for(auth_home, conversation_id)
    # Reuse, not reimplement: the background path already resolved a Claude
    # transcript by session id, and having two rules for the same lookup is
    # how they drift apart.
    from .provider_background import find_session_transcript

    return find_session_transcript(auth_home, conversation_id)


def _codex_rollout_for(auth_home, conversation_id):
    """Codex repeats its conversation id in the rollout filename."""
    root = os.path.join(auth_home, "sessions")
    if not os.path.isdir(root):
        return None
    for directory, _subdirs, names in os.walk(root):
        for name in names:
            match = _ROLLOUT_NAME.match(name)
            if match and match.group(1).lower() == str(conversation_id).lower():
                return os.path.join(directory, name)
    return None


#: Which reader parses which provider's transcript. Claude is the default
#: because its shape is what an unknown provider is most likely to resemble.
_READERS = {}


def _latest_transcript(provider, auth_home, started_at):
    if not auth_home:
        return None
    root = os.path.join(auth_home, "sessions") if provider == "codex" else os.path.join(auth_home, ".claude", "projects")
    if not os.path.isdir(root):
        return None
    cutoff = _timestamp(started_at)
    candidates = []
    deadline = time.monotonic() + MAX_TRANSCRIPT_SCAN_SECONDS
    for directory, subdirs, names in os.walk(root):
        if time.monotonic() >= deadline:
            # An inconclusive scan is absence, not "whichever candidate we had
            # reached". Returning a partial answer here is what made a wrong
            # attribution indistinguishable from a real measurement.
            return None
        if provider == "claude":
            subdirs[:] = [name for name in subdirs if name != "subagents"]
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(directory, name)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                continue
            if cutoff is None or modified >= cutoff:
                candidates.append((modified, path))
                if len(candidates) > MAX_TRANSCRIPT_CANDIDATES:
                    return None
    return max(candidates, default=(None, None))[1]


_READERS.update({"codex": lambda handle: _codex_usage(handle),
                 "ollama": lambda handle: _ollama_usage(handle)})


def _timestamp(value):
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _ollama_usage(handle):
    """Token counts parsed out of ollama's `--verbose` blocks.

    Ollama has no provider-native transcript, so the only place these numbers
    exist is the terminal, and the only copy of the terminal is the PTY capture
    cdx already takes through `script`. That capture is not clean text -- a
    real one carries cursor show/hide sequences between individual words and
    carriage returns overwriting lines in place -- so it is normalized with the
    same helper the handoff reader uses before any pattern is applied.

    Returns no model: ollama runs locally and its models are not in any price
    table, so naming one would only invite pricing something that is free.
    """
    text = _normalize_terminal_transcript(handle.read())
    prompts = [int(value) for value in _OLLAMA_PROMPT_TOKENS.findall(text)]
    evals = [int(value) for value in _OLLAMA_EVAL_TOKENS.findall(text)]
    if not prompts and not evals:
        return None, None
    return normalize_usage(
        input_tokens=sum(prompts) if prompts else None,
        output_tokens=sum(evals) if evals else None,
    ), None


def _codex_usage(handle):
    """The conversation's cumulative usage, and the model serving it latest."""
    latest = None
    model = None
    for line in handle:
        try:
            record = json.loads(line)
            payload = record.get("payload") or {}
            if payload.get("model"):
                model = payload["model"]
            usage = ((payload.get("info") or {}).get("total_token_usage") or {}) if payload.get("type") == "token_count" else {}
            if not isinstance(usage, dict) or not usage:
                continue
            # Codex counts cached tokens inside `input_tokens`; reduce to the
            # uncached remainder so the field means what run_usage says it
            # means. Same subset check as the headless reader: a cached count
            # larger than the input count is not a subset, so that record is
            # left alone rather than forced to zero.
            reported_input = _number(usage.get("input_tokens"))
            cache_read = _number(usage.get("cached_input_tokens"))
            latest = normalize_usage(
                input_tokens=reported_input - cache_read if cache_read <= reported_input else reported_input,
                cache_read_tokens=cache_read,
                output_tokens=_number(usage.get("output_tokens")),
                reasoning_tokens=_number(usage.get("reasoning_output_tokens")) or None,
            )
        except (TypeError, ValueError):
            continue
    return latest, model


def _claude_usage(handle):
    """Sum Claude's per-message usage across the transcript.

    Cache creation and cache read are kept apart rather than summed on the way
    in: they cost 1.25x and 0.1x of uncached input, so fusing them here would
    destroy the only information a cost-aware figure needs. Claude reports no
    separate reasoning count -- thinking is billed as output and is already
    inside `output_tokens` -- so that field stays absent by design.
    """
    totals = {"input_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0, "output_tokens": 0}
    seen = set()
    model = None
    for line in handle:
        try:
            record = json.loads(line)
            message = record.get("message") or {}
            usage = message.get("usage") or {}
            if record.get("type") != "assistant" or not usage:
                continue
            identifier = claude_usage_dedup_key(record)
            if identifier is not None:
                if identifier in seen:
                    continue
                seen.add(identifier)
            totals["input_tokens"] += _number(usage.get("input_tokens"))
            totals["cache_creation_tokens"] += _number(usage.get("cache_creation_input_tokens"))
            totals["cache_read_tokens"] += _number(usage.get("cache_read_input_tokens"))
            totals["output_tokens"] += _number(usage.get("output_tokens"))
            if message.get("model"):
                model = message["model"]
        except (TypeError, ValueError):
            continue
    if not seen and not any(totals.values()):
        return None, model
    return normalize_usage(**totals), model


def _number(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


#: The quantities a provider actually reports. The other two fields of a usage
#: record are derived by `normalize_usage` and must never be differenced.
MEASURED_KEYS = (
    "input_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "output_tokens",
    "reasoning_tokens",
)


def usage_delta(cumulative, previous):
    """What this run added to a transcript that already held `previous`.

    Both readers return a *cumulative* figure: Claude's is the sum over the
    whole transcript file, Codex's is its own running total for the
    conversation. Storing that on every run and summing across runs billed a
    resumed session for its entire history once per resume -- one observed
    session's cache read went from 2.6M to 7.6M on a single additional launch.

    Returns None when the difference cannot be trusted: a transcript that
    shrank, rotated, or was replaced produces a negative component, and there
    is no arithmetic that recovers the truth from that. Absence is recoverable
    on the next run; a fabricated number is not.
    """
    if not isinstance(cumulative, dict):
        return None
    if not isinstance(previous, dict):
        return None
    parts = {}
    for key in MEASURED_KEYS:
        now = cumulative.get(key)
        before = previous.get(key)
        if now is None:
            parts[key] = None
            continue
        difference = now - (before or 0)
        if difference < 0:
            return None
        parts[key] = difference
    return normalize_usage(**parts)


def transcript_predates_run(path, started_at):
    """Whether this transcript already existed before the run began.

    Decides what the *first* run against a given transcript may record. A
    transcript created during the run is wholly this run's work, so its total
    is the run's usage. One that predates the run holds history cdx never
    measured, and attributing all of it to this run would commit the very
    over-count the delta exists to prevent -- so that run reports absence and
    only leaves the baseline behind for its successor.
    """
    cutoff = _timestamp(started_at)
    if cutoff is None or not path:
        return False
    try:
        stat = os.stat(path)
    except OSError:
        return False
    # st_birthtime where the platform records it (macOS, some BSDs); st_ctime
    # elsewhere, where it means metadata change and is an upper bound on
    # creation -- which errs toward "predates", the conservative answer.
    created = getattr(stat, "st_birthtime", None)
    if created is None:
        created = stat.st_ctime
    return created < cutoff
