import json

USAGE_KEYS = ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")
SUPPORTED_PROVIDERS = {"claude", "codex"}


def empty_usage():
    return {key: None for key in USAGE_KEYS}


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
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else value
    if not isinstance(usage, dict):
        return empty_usage()

    input_tokens = _int_value(
        usage.get("input_tokens"),
        usage.get("prompt_tokens"),
        usage.get("cache_creation_input_tokens"),
        usage.get("cache_read_input_tokens"),
    )
    output_tokens = _int_value(usage.get("output_tokens"), usage.get("completion_tokens"))
    reasoning_tokens = _int_value(
        usage.get("reasoning_tokens"),
        usage.get("reasoning_output_tokens"),
        _nested_int(usage, "output_tokens_details", "reasoning_tokens"),
        _nested_int(usage, "completion_tokens_details", "reasoning_tokens"),
    )
    total_tokens = _first_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


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
