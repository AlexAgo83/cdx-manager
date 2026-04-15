import json
import os
import re
from datetime import datetime, timezone


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_ANSI_TERMINAL_CONTROL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_OSC_SEQUENCE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROL_CHAR = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MAX_STATUS_READ_BYTES = 512 * 1024
MAX_STATUS_CANDIDATE_FILES = 64


def _strip_ansi(text):
    return _ANSI_ESCAPE.sub("", str(text or ""))


def _normalize_terminal_transcript(text):
    text = str(text or "")
    text = _OSC_SEQUENCE.sub(" ", text)
    text = _ANSI_TERMINAL_CONTROL.sub(" ", text)
    text = _ANSI_ESCAPE.sub(" ", text)
    text = _CONTROL_CHAR.sub(" ", text)
    text = text.replace("\r", "\n")
    return text


def _safe_read_text(file_path, max_bytes=MAX_STATUS_READ_BYTES):
    try:
        size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            return f.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None


def _safe_stat(file_path):
    try:
        return os.stat(file_path)
    except OSError:
        return None


def _collect_text_values(value, output=None):
    if output is None:
        output = []
    if isinstance(value, str):
        output.append(value)
    elif isinstance(value, list):
        for item in value:
            _collect_text_values(item, output)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_text_values(item, output)
    return output


def _extract_status_blocks_from_text(text, provider=None, source_ref=None, timestamp=None):
    normalized = _normalize_terminal_transcript(text)
    lines = normalized.split("\n")
    items = []

    def collect_blocks(
        start_pattern,
        end_patterns,
        max_span=80,
        pre_context=0,
        context_pattern=None,
        context_stop_patterns=None,
    ):
        blocks = []
        index = 0
        while index < len(lines):
            if not start_pattern.search(lines[index]):
                index += 1
                continue
            end_index = len(lines)
            for cursor in range(index + 1, min(len(lines), index + max_span)):
                if any(pattern.search(lines[cursor]) for pattern in end_patterns):
                    end_index = cursor
                    break
            start_index = max(0, index - pre_context)
            if context_pattern is not None:
                cursor = index - 1
                while cursor >= 0:
                    line = lines[cursor]
                    if context_stop_patterns and any(pattern.search(line) for pattern in context_stop_patterns):
                        break
                    if not context_pattern.search(line):
                        break
                    start_index = cursor
                    cursor -= 1
            block = "\n".join(lines[start_index:end_index]).strip()
            if block:
                blocks.append(block)
            index = max(index + 1, end_index)
        return blocks

    if provider != "codex":
        for block in collect_blocks(
            re.compile(r"^\s*(?:[│|]\s*)?Current session\b", re.I),
            [re.compile(p, re.I) for p in [
                r"^Extra usage\b", r"^Esc to cancel\b",
                r"^To continue this session\b", r"^╰",
            ]],
        ):
            items.append({"source_ref": source_ref, "timestamp": timestamp, "text": block})

    if provider != "claude":
        for block in collect_blocks(
            re.compile(r"^\s*(?:[│|]\s*)?5h\s+limit\b", re.I),
            [re.compile(p, re.I) for p in [
                r"^To continue this session\b", r"^╰",
            ]],
            context_pattern=re.compile(
                r"^\s*$|^\s*(?:[│|]\s*)?(?:╭|Visit\b|information\b|Model:|Directory:|Permissions:|Agents\.md:|Account:|Collaboration mode:|Session:)",
                re.I,
            ),
            context_stop_patterns=[
                re.compile(r"^\s*(?:[│|]\s*)?5h\s+limit\b", re.I),
                re.compile(r"^\s*(?:[│|]\s*)?Weekly\s+limit\b", re.I),
                re.compile(r"^To continue this session\b", re.I),
            ],
        ):
            items.append({"source_ref": source_ref, "timestamp": timestamp, "text": block})

    if items:
        return items

    if provider:
        return []

    keyword_re = re.compile(r"/status|usage|current|remaining|\d{1,3}%", re.I)
    fallback_lines = str(text or "").splitlines()
    for i in range(len(fallback_lines) - 1, -1, -1):
        if not keyword_re.search(fallback_lines[i]):
            continue
        start = max(0, i - 4)
        end = min(len(fallback_lines), i + 5)
        snippet = "\n".join(fallback_lines[start:end]).strip()
        if snippet:
            return [{"source_ref": source_ref, "timestamp": timestamp, "text": snippet}]
    return []


def _extract_jsonl_texts(file_path, provider=None):
    text = _safe_read_text(file_path)
    if not text:
        return []
    items = []
    for line_index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            payload_texts = _collect_text_values(record.get("payload") or {})
            for candidate in payload_texts:
                if isinstance(candidate, str) and candidate.strip():
                    items.extend(_extract_status_blocks_from_text(
                        candidate,
                        provider=provider,
                        source_ref=f"{file_path}:{line_index + 1}",
                        timestamp=record.get("timestamp"),
                    ))
        except (json.JSONDecodeError, AttributeError):
            continue
    return items


def _extract_log_block(file_path, provider=None):
    text = _safe_read_text(file_path)
    if not text:
        return []
    return _extract_status_blocks_from_text(text, provider=provider, source_ref=file_path, timestamp=None)


def _parse_month_index(name):
    lower = name[:3].lower()
    for i, m in enumerate(MONTH_ABBR):
        if m.lower() == lower:
            return i
    return -1


def _infer_reset_year(month, day):
    now = datetime.now().astimezone()
    year = now.year
    try:
        candidate = datetime(
            year,
            month + 1,
            day,
            tzinfo=now.tzinfo,
        )
    except ValueError:
        return year
    two_days_ago = datetime.fromtimestamp(now.timestamp() - 2 * 24 * 3600, tz=now.tzinfo)
    return year + 1 if candidate < two_days_ago else year


def _normalize_reset_date(raw):
    if not raw:
        return None

    raw = str(raw).strip()

    def pad(n):
        return str(n).zfill(2)

    def format_time(hours, minutes):
        return f"{pad(hours)}:{pad(minutes)}"

    def parse_ampm(hours, minutes, meridiem):
        normalized = meridiem.lower().replace(".", "")
        if normalized == "pm" and hours != 12:
            hours += 12
        if normalized == "am" and hours == 12:
            hours = 0
        return hours, minutes

    # Codex: "10:10 on 17 Apr"
    m = re.match(r"(\d{1,2}):(\d{2})\s+on\s+(\d{1,2})\s+([A-Za-z]+)", raw, re.I)
    if m:
        hours, minutes, day, month_str = int(m[1]), int(m[2]), int(m[3]), m[4]
        month = _parse_month_index(month_str)
        if month != -1:
            year = _infer_reset_year(month, day)
            return f"{MONTH_ABBR[month]} {day} {pad(hours)}:{pad(minutes)}"

    # Claude: "Thursday, April 17 at 5:00 AM" or "April 17, 2026, 5 PM"
    m = re.match(
        r"(?:[A-Za-z]+,\s+)?([A-Za-z]+)\s+(\d{1,2})(?:,\s+(\d{4}))?"
        r"(?:\s*(?:,|at)\s*(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?))?$",
        raw,
        re.I,
    )
    if m:
        month = _parse_month_index(m[1])
        if month != -1:
            day = int(m[2])
            year = int(m[3]) if m[3] else _infer_reset_year(month, day)
            if m[4]:
                hours, minutes = parse_ampm(int(m[4]), int(m[5] or 0), m[6])
                return f"{MONTH_ABBR[month]} {day} {format_time(hours, minutes)}"
            return f"{MONTH_ABBR[month]} {day}"

    # Claude session reset: "at 5:00 AM", "5:00 AM", or "today at 5 PM"
    m = re.match(r"(?:today\s+)?(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)$", raw, re.I)
    if m:
        hours, minutes = parse_ampm(int(m[1]), int(m[2] or 0), m[3])
        now = datetime.now().astimezone()
        from datetime import timedelta
        candidate = datetime(now.year, now.month, now.day, hours, minutes, tzinfo=now.tzinfo)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return f"{MONTH_ABBR[candidate.month - 1]} {candidate.day} {format_time(hours, minutes)}"

    # Codex time-only: "21:51"
    m = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if m:
        hours, minutes = int(m[1]), int(m[2])
        now = datetime.now().astimezone()
        from datetime import timedelta
        candidate = datetime(now.year, now.month, now.day, hours, minutes, tzinfo=now.tzinfo)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return f"{MONTH_ABBR[candidate.month - 1]} {candidate.day} {format_time(hours, minutes)}"

    # Claude: "Thursday, April 17" or "April 17" or "April 17, 2026"
    m = re.match(r"(?:[A-Za-z]+,\s+)?([A-Za-z]+)\s+(\d{1,2})(?:,\s+(\d{4}))?", raw, re.I)
    if m:
        month = _parse_month_index(m[1])
        if month != -1:
            day = int(m[2])
            year = int(m[3]) if m[3] else _infer_reset_year(month, day)
            return f"{MONTH_ABBR[month]} {day}"

    return None


def _extract_account_identity(text):
    normalized = _normalize_terminal_transcript(text)
    for line in normalized.split("\n"):
        m = re.match(r"^\s*(?:[│|]\s*)?Account:\s*(.+?)\s*$", line, re.I)
        if not m:
            continue
        value = m.group(1).strip().lower()
        if value:
            return value
    return None


def _account_matches_expected(block_text, expected_account_email):
    if not expected_account_email:
        return True
    actual = _extract_account_identity(block_text)
    if not actual:
        return True

    expected = str(expected_account_email).strip().lower()
    actual_email = re.split(r"\s|\(", actual, maxsplit=1)[0]
    expected_email = re.split(r"\s|\(", expected, maxsplit=1)[0]

    if actual_email == expected_email:
        return True
    if actual_email.startswith(expected_email) or expected_email.startswith(actual_email):
        return min(len(actual_email), len(expected_email)) >= 8
    return False


def extract_named_statuses_from_text(text):
    normalized = _normalize_terminal_transcript(text)
    lines = [l.strip() for l in normalized.split("\n") if l.strip()]
    result = {}

    key_value_patterns = [
        ("usage_pct", re.compile(r"usage_pct\s*[:=]\s*(\d{1,3})%?", re.I)),
        ("remaining_5h_pct", re.compile(r"remaining_?5h_pct\s*[:=]\s*(\d{1,3})%?", re.I)),
        ("remaining_week_pct", re.compile(r"remaining_?week_pct\s*[:=]\s*(\d{1,3})%?", re.I)),
        ("credits", re.compile(r"credits?\s*[:=]\s*([\d, ]*\d[\d, ]*)\s*(?:credits?)?", re.I)),
        ("remaining_5h_pct", re.compile(r"5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left", re.I)),
        ("remaining_week_pct", re.compile(r"weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left", re.I)),
        ("remaining_5h_pct", re.compile(r"5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})(?:%|\b)", re.I)),
        ("remaining_week_pct", re.compile(r"weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})(?:%|\b)", re.I)),
        ("usage_pct", re.compile(r"usage\s*[:=]\s*(\d{1,3})%", re.I)),
        ("usage_pct", re.compile(r"current\s*[:=]\s*(\d{1,3})%", re.I)),
        ("remaining_5h_pct", re.compile(r"5h(?:\s+remaining)?\s*[:=]\s*(\d{1,3})%", re.I)),
        ("remaining_5h_pct", re.compile(r"remaining\s+5h\s*[:=]\s*(\d{1,3})%", re.I)),
        ("remaining_week_pct", re.compile(r"week(?:\s+remaining)?\s*[:=]\s*(\d{1,3})%", re.I)),
        ("remaining_week_pct", re.compile(r"remaining\s+week\s*[:=]\s*(\d{1,3})%", re.I)),
    ]
    for field, pattern in key_value_patterns:
        if field not in result:
            m = pattern.search(normalized)
            if m:
                result[field] = int(re.sub(r"\D", "", m[1]))

    # Claude "Current session / Current week" block
    def extract_following_percent(anchor_pattern):
        idx = next((i for i, l in enumerate(lines) if anchor_pattern.search(l)), -1)
        if idx == -1:
            return None
        for i in range(idx + 1, min(len(lines), idx + 8)):
            m = re.search(r"(\d{1,3})%\s+used", lines[i], re.I)
            if m:
                return int(m[1])
        return None

    session_used = extract_following_percent(re.compile(r"\bCurrent session\b", re.I))
    week_used = extract_following_percent(re.compile(r"\bCurrent week\b", re.I))
    if session_used is not None or week_used is not None:
        if "usage_pct" not in result and session_used is not None:
            result["usage_pct"] = session_used
        if "remaining_5h_pct" not in result and session_used is not None:
            result["remaining_5h_pct"] = max(0, 100 - session_used)
        if "remaining_week_pct" not in result and week_used is not None:
            result["remaining_week_pct"] = max(0, 100 - week_used)

    # Table header row
    header_idx = next(
        (i for i, l in enumerate(lines)
         if re.search(r"\bSESSION\b", l, re.I)
         and re.search(r"\bUSAGE\b", l, re.I)
         and re.search(r"\b5H\b", l, re.I)
         and re.search(r"\bWEEK\b", l, re.I)),
        -1,
    )
    if header_idx != -1:
        for line in lines[header_idx + 1:]:
            pcts = [int(m) for m in re.findall(r"(\d{1,3})%", line)]
            if len(pcts) >= 3:
                result.setdefault("usage_pct", pcts[0])
                result.setdefault("remaining_5h_pct", pcts[1])
                result.setdefault("remaining_week_pct", pcts[2])
                break

    for line in lines:
        m = re.search(r"5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left", line, re.I)
        if m and "remaining_5h_pct" not in result:
            result["remaining_5h_pct"] = int(m[1])
        m = re.search(r"5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})(?:%|\b)", line, re.I)
        if m and "remaining_5h_pct" not in result:
            result["remaining_5h_pct"] = int(m[1])
        m = re.search(r"weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left", line, re.I)
        if m and "remaining_week_pct" not in result:
            result["remaining_week_pct"] = int(m[1])
        m = re.search(r"weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})(?:%|\b)", line, re.I)
        if m and "remaining_week_pct" not in result:
            result["remaining_week_pct"] = int(m[1])

    if "remaining_5h_pct" in result and "usage_pct" not in result:
        result["usage_pct"] = max(0, 100 - result["remaining_5h_pct"])
    if "remaining_week_pct" in result and "usage_pct" not in result:
        result["usage_pct"] = max(0, 100 - result["remaining_week_pct"])

    def _extract_reset_near(anchor_pattern, stop_pattern=None, max_span=8):
        idx = next((i for i, l in enumerate(lines) if anchor_pattern.search(l)), -1)
        if idx == -1:
            return None
        for i in range(idx, min(len(lines), idx + max_span)):
            if i > idx and stop_pattern and stop_pattern.search(lines[i]):
                break
            m = re.search(r"\(resets\s+(.+?)\)", lines[i], re.I)
            if m:
                return m[1].strip()
            m = re.match(r"resets?\s*:?\s*(.+)", lines[i], re.I)
            if m:
                return m[1].strip()
        return None

    reset_5h_at = _extract_reset_near(
        re.compile(r"\b5h\s+limit\b", re.I),
        stop_pattern=re.compile(r"\bweekly\s+limit\b", re.I),
        max_span=4,
    )
    if not reset_5h_at:
        reset_5h_at = _extract_reset_near(
            re.compile(r"\bCurrent session\b", re.I),
            stop_pattern=re.compile(r"\bCurrent week\b", re.I),
        )
    reset_week_at = _extract_reset_near(
        re.compile(r"\bweekly\s+limit\b", re.I),
        max_span=4,
    )
    if not reset_week_at:
        reset_week_at = _extract_reset_near(re.compile(r"\bCurrent week\b", re.I))

    if not reset_week_at:
        for line in lines:
            m = re.match(r"(?:(?:weekly\s+)?resets?)\s*:?\s*(.+)", line, re.I)
            if m:
                reset_week_at = m[1].strip()
                break

    if not reset_week_at:
        all_resets = list(re.finditer(r"\(resets\s+(.+?)\)", normalized, re.I))
        if all_resets:
            reset_week_at = all_resets[-1].group(1).strip()

    if reset_5h_at:
        reset_5h_at = _normalize_reset_date(reset_5h_at) or reset_5h_at
    if reset_week_at:
        reset_week_at = _normalize_reset_date(reset_week_at) or reset_week_at

    if not result:
        return None

    return {
        "usage_pct": result.get("usage_pct"),
        "remaining_5h_pct": result.get("remaining_5h_pct"),
        "remaining_week_pct": result.get("remaining_week_pct"),
        "credits": result.get("credits"),
        "reset_5h_at": reset_5h_at,
        "reset_week_at": reset_week_at,
        "reset_at": reset_week_at or reset_5h_at,
        "raw_status_text": normalized.strip() or None,
    }


def _collect_candidate_files(root_dir):
    candidates = []
    direct = [
        os.path.join(root_dir, "history.jsonl"),
        os.path.join(root_dir, "session_index.jsonl"),
        os.path.join(root_dir, "log", "codex-tui.log"),
    ]
    for fp in direct:
        if _safe_stat(fp):
            candidates.append(fp)

    log_dir = os.path.join(root_dir, "log")
    log_dir_stat = _safe_stat(log_dir)
    if log_dir_stat and os.path.isdir(log_dir):
        for fname in os.listdir(log_dir):
            if fname.startswith("cdx-session") and fname.endswith(".log"):
                fp = os.path.join(log_dir, fname)
                if _safe_stat(fp):
                    candidates.append(fp)

    sessions_dir = os.path.join(root_dir, "sessions")
    if not _safe_stat(sessions_dir):
        return candidates

    skip = {"cache", "plugins", "skills", "memories", "sqlite", "shell_snapshots", "tmp"}

    for dirpath, dirnames, filenames in os.walk(sessions_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in skip]
        for fname in filenames:
            if fname.endswith(".jsonl") or fname.endswith(".log"):
                candidates.append(os.path.join(dirpath, fname))

    return candidates


def find_latest_status_artifact(root_dir, provider=None, expected_account_email=None):
    candidates = _collect_candidate_files(root_dir)
    candidate_stats = {
        fp: stat
        for fp, stat in ((candidate, _safe_stat(candidate)) for candidate in set(candidates))
        if stat
    }
    candidates = sorted(
        candidate_stats,
        key=lambda fp: candidate_stats[fp].st_mtime,
        reverse=True,
    )[:MAX_STATUS_CANDIDATE_FILES]
    records = []
    for fp in candidates:
        normalized_fp = fp.replace(os.sep, "/")
        if "/sessions/" in normalized_fp and os.path.basename(fp).startswith("rollout"):
            continue
        if fp.endswith(".jsonl"):
            records.extend(_extract_jsonl_texts(fp, provider))
        elif fp.endswith(".log"):
            records.extend(_extract_log_block(fp, provider))

    best = None
    for candidate in records:
        if provider == "codex" and not _account_matches_expected(
            candidate["text"], expected_account_email
        ):
            continue
        parsed = extract_named_statuses_from_text(candidate["text"])
        if not parsed:
            continue
        ts = candidate.get("timestamp")
        try:
            score = float(ts) if ts else 0
        except (TypeError, ValueError):
            score = 0
        src_file = re.sub(r":\d+$", "", candidate["source_ref"])
        stat = _safe_stat(src_file)
        if not score and stat:
            score = stat.st_mtime
        priority = 2 if src_file.endswith(".log") else 1

        if best is None or (priority, score) >= (best["priority"], best["score"]):
            best = {
                "priority": priority,
                "score": score,
                "source_ref": candidate["source_ref"],
                **parsed,
            }
            if ts:
                try:
                    best["updated_at"] = datetime.fromtimestamp(
                        float(ts) / 1000, tz=timezone.utc
                    ).astimezone().isoformat()
                except (TypeError, ValueError):
                    pass
            if "updated_at" not in best:
                if stat:
                    best["updated_at"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).astimezone().isoformat()

    return best
