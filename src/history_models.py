"""Recover serving models using only evidence attached to a history row."""

import json
import os
import time

from .interactive_usage import MAX_TRANSCRIPT_BYTES, MAX_TRANSCRIPT_SCAN_SECONDS
from .run_registry import registry_path

EVIDENCE_KINDS = ("isolated_observation", "stdout", "run_report", "codex_rollout", "claude_transcript")


def missing_model(value):
    return not value or (isinstance(value, str) and value.startswith("<"))


def _read_records(path):
    if not path:
        return [], None
    if not isinstance(path, (str, os.PathLike)):
        return [], "invalid_evidence_path"
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_TRANSCRIPT_BYTES + 1)
        if len(raw) > MAX_TRANSCRIPT_BYTES:
            return [], "evidence_too_large"
        text = raw.decode("utf-8")
        try:
            records = [json.loads(text)]
        except ValueError:
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not all(isinstance(record, dict) for record in records):
            return [], "invalid_evidence"
        return records, None
    except FileNotFoundError:
        return [], None
    except (OSError, UnicodeError, ValueError):
        return [], "unreadable_evidence"


def _single_model(models):
    if any(not isinstance(model, str) or missing_model(model) for model in models):
        return None, "incomplete_model_evidence"
    # Context size variants already share a model group in stats.
    groups = {model.removesuffix("[1m]") if model.startswith("claude-") else model for model in models}
    if len(groups) > 1:
        return None, "ambiguous_models"
    return (models[0], None) if models else (None, None)


def _stdout_models(records):
    models = []
    for record in records:
        if record.get("launcher") == "cdx" or record.get("action") == "run":
            if not missing_model(record.get("usage_model")):
                models.append(record["usage_model"])
            continue
        message = record.get("message")
        if isinstance(message, dict) and message.get("model") == "<synthetic>":
            continue
        if isinstance(message, dict) and (message.get("role") == "assistant" or record.get("type") == "assistant"):
            models.append(message.get("model"))
        elif "model" in record and ("usage" in record or record.get("type") == "result"):
            models.append(record["model"])
        model_usage = record.get("modelUsage")
        if isinstance(model_usage, dict):
            models.extend(model_usage)
    return models


def _exact_id(entry, records, provider):
    key = "thread_id" if provider == "codex" else "session_id"
    identifiers = {record[key] for record in records if isinstance(record.get(key), str) and record[key]}
    for identifier in (entry.get(key), entry.get("conversation_id")):
        if identifier:
            if not isinstance(identifier, str):
                return None, "invalid_conversation_id"
            identifiers.add(identifier)
    if len(identifiers) > 1:
        return None, "ambiguous_conversation_ids"
    return next(iter(identifiers), None), None


def _matches_transcript(provider, name, identifier):
    if provider == "codex":
        return name.startswith("rollout-") and name.endswith(f"-{identifier}.jsonl")
    return name == f"{identifier}.jsonl"


def _exact_transcript(provider, auth_home, identifier):
    if not auth_home:
        return None, None
    root = os.path.join(auth_home, "sessions") if provider == "codex" else os.path.join(auth_home, ".claude", "projects")
    paths = []
    deadline = time.monotonic() + MAX_TRANSCRIPT_SCAN_SECONDS
    for directory, subdirs, names in os.walk(root):
        if time.monotonic() > deadline:
            return None, "transcript_scan_limit"
        subdirs[:] = [name for name in subdirs if name != "subagents"]
        for name in names:
            if _matches_transcript(provider, name, identifier):
                paths.append(os.path.join(directory, name))
                if len(paths) > 1:
                    return None, "multiple_exact_transcripts"
    return next(iter(paths), None), None


def recover_model(entry, session=None, reports=()):
    """Return (model, evidence kind, reason); never consult live model settings."""
    provider = entry.get("provider")
    evidence = entry.get("usage_evidence")
    if isinstance(evidence, dict):
        if (evidence.get("stdout_path") != entry.get("stdout_path")
                or evidence.get("attempt_id") != entry.get("attempt_id")
                or evidence.get("run_id") != entry.get("run_id")
                or (evidence.get("measurement_usage") or evidence.get("usage")) != entry.get("usage")):
            return None, "isolated_observation", "observation_attempt_mismatch"
        model, reason = _single_model(evidence.get("models") or [])
        return model, "isolated_observation", reason or (None if model else "no_turn_models")
    records, error = _read_records(entry.get("stdout_path"))
    if error:
        return None, None, error
    for record in records:
        if record.get("launcher") == "cdx" or record.get("action") == "run":
            if (not entry.get("run_id") or record.get("run_id") != entry["run_id"]
                    or record.get("session") != entry.get("session_name") or record.get("provider") != provider):
                return None, None, "report_identity_mismatch"
    model, error = _single_model(_stdout_models(records))
    if model or error:
        return model, "stdout", error

    # A logical run may fail over across profiles. Its final report does not
    # prove the model used by an earlier attempt with the same run id.
    report_models = []
    for report in reports:
        if not entry.get("run_id") or report.get("run_id") != entry["run_id"]:
            continue
        if report.get("session") != entry.get("session_name") or report.get("provider") != provider:
            continue
        artifacts = report.get("artifacts") or {}
        if not isinstance(artifacts, dict):
            continue
        if not entry.get("stdout_path") or artifacts.get("stdout_path") != entry["stdout_path"]:
            continue
        model = report.get("usage_model")
        if isinstance(model, str) and not missing_model(model):
            report_models.append(model)
    model, error = _single_model(report_models)
    if model or error:
        return model, "run_report", error

    if provider not in ("codex", "claude"):
        return None, None, "no_run_model_evidence"
    identifier, error = _exact_id(entry, records, provider)
    if error:
        return None, None, error
    path = entry.get("provider_transcript_path")
    # A preserved path resolved by recency is not proof of conversation identity.
    if path and not isinstance(path, (str, os.PathLike)):
        return None, None, "invalid_evidence_path"
    if not identifier and path and entry.get("provider_transcript_match") == "conversation_id":
        identifier = os.path.basename(path).removesuffix(".jsonl")
        if provider == "codex":
            identifier = identifier[-36:]
    if not identifier:
        return None, None, "no_run_conversation_id"
    if not path:
        path, error = _exact_transcript(provider, (session or {}).get("authHome"), identifier)
        if error:
            return None, None, error
    elif not _matches_transcript(provider, os.path.basename(path), identifier):
        return None, None, "transcript_identity_mismatch"
    transcript, error = _read_records(path)
    if error:
        return None, None, error
    if not transcript:
        return None, None, "exact_transcript_missing"
    models = []
    for record in transcript:
        recorded_id = record.get("sessionId") if provider == "claude" else None
        if provider == "codex" and record.get("type") == "session_meta":
            payload = record.get("payload")
            if not isinstance(payload, dict):
                return None, None, "invalid_evidence"
            recorded_id = payload.get("id")
        if recorded_id and recorded_id != identifier:
            return None, None, "transcript_identity_mismatch"
        if provider == "codex" and record.get("type") == "turn_context":
            payload = record.get("payload")
            if not isinstance(payload, dict):
                return None, None, "invalid_evidence"
            models.append(payload.get("model"))
        elif provider == "claude" and record.get("type") == "assistant":
            message = record.get("message")
            if not isinstance(message, dict):
                return None, None, "invalid_evidence"
            model = message.get("model")
            if model != "<synthetic>":
                models.append(model)
    # Requiring the whole exact conversation to agree is conservative for
    # resumed runs: mixed conversations stay unknown without turn boundaries.
    model, error = _single_model(models)
    return model, "codex_rollout" if provider == "codex" else "claude_transcript", error or (None if model else "no_turn_models")


def read_run_reports(base_dir):
    """Read the preserved registry without refreshing or changing run state."""
    records, _error = _read_records(registry_path(base_dir))
    runs = records[0].get("runs", []) if records else []
    return [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
