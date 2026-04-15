"use strict";

const fs = require("fs");
const path = require("path");

const ANSI_ESCAPE_REGEX = /\u001b\[[0-9;]*m/g;
const ANSI_TERMINAL_CONTROL_REGEX = /\u001b\[[0-9;?]*[ -/]*[@-~]/g;
const OSC_SEQUENCE_REGEX = /\u001b\][^\u0007\u001b]*(?:\u0007|\u001b\\)/g;
const CONTROL_CHAR_REGEX = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g;
const STATUS_LABELS = {
  usagePct: [/^(?:usage|current)\s*[:=]\s*(\d{1,3})%$/i, /(?:^|\b)(?:usage|current)\s*[:=]\s*(\d{1,3})%/i],
  remaining5hPct: [/^(?:5h(?:\s+remaining)?|remaining\s+5h)\s*[:=]\s*(\d{1,3})%$/i, /(?:5h(?:\s+remaining)?|remaining\s+5h)\s*[:=]\s*(\d{1,3})%/i],
  remainingWeekPct: [/^(?:week(?:\s+remaining)?|remaining\s+week)\s*[:=]\s*(\d{1,3})%$/i, /(?:week(?:\s+remaining)?|remaining\s+week)\s*[:=]\s*(\d{1,3})%/i],
};

function stripAnsi(text) {
  return String(text || "").replace(ANSI_ESCAPE_REGEX, "");
}

function normalizeTerminalTranscript(text) {
  return String(text || "")
    .replace(OSC_SEQUENCE_REGEX, " ")
    .replace(ANSI_TERMINAL_CONTROL_REGEX, " ")
    .replace(ANSI_ESCAPE_REGEX, " ")
    .replace(CONTROL_CHAR_REGEX, " ")
    .replace(/\r/g, "\n");
}

function safeReadText(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch (error) {
    if (error && error.code === "ENOENT") {
      return null;
    }
    return null;
  }
}

function safeStat(filePath) {
  try {
    return fs.statSync(filePath);
  } catch (error) {
    return null;
  }
}

function collectTextValues(value, output = []) {
  if (typeof value === "string") {
    output.push(value);
    return output;
  }
  if (!value || typeof value !== "object") {
    return output;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectTextValues(item, output);
    }
    return output;
  }
  for (const item of Object.values(value)) {
    collectTextValues(item, output);
  }
  return output;
}

function extractJsonlTexts(filePath) {
  const text = safeReadText(filePath);
  if (!text) {
    return [];
  }
  const lines = text.split(/\r?\n/);
  const items = [];
  for (const [lineIndex, line] of lines.entries()) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      const record = JSON.parse(trimmed);
      const payloadTexts = collectTextValues(record.payload || {});
      for (const candidate of payloadTexts) {
        if (typeof candidate === "string" && candidate.trim()) {
          items.push({
            sourceRef: `${filePath}:${lineIndex + 1}`,
            timestamp: record.timestamp || null,
            text: candidate,
          });
        }
      }
    } catch {
      continue;
    }
  }
  return items;
}

function extractLogBlock(filePath) {
  const text = safeReadText(filePath);
  if (!text) {
    return [];
  }
  const normalized = normalizeTerminalTranscript(text);
  const lines = normalized.split("\n");
  const findBlock = (startPattern, endPatterns, maxSpan = 80) => {
    const startIndex = lines.findIndex((line) => startPattern.test(line));
    if (startIndex === -1) {
      return null;
    }
    let endIndex = lines.length;
    for (let index = startIndex + 1; index < Math.min(lines.length, startIndex + maxSpan); index += 1) {
      if (endPatterns.some((pattern) => pattern.test(lines[index]))) {
        endIndex = index;
        break;
      }
    }
    return lines.slice(startIndex, endIndex).join("\n").trim();
  };

  const claudeBlock = findBlock(
    /Current session\b/i,
    [/^Extra usage\b/i, /^Esc to cancel\b/i, /^To continue this session\b/i, /^╰/],
  );
  if (claudeBlock) {
    return [{
      sourceRef: filePath,
      timestamp: null,
      text: claudeBlock,
    }];
  }

  const codexBlock = findBlock(
    /5h\s+limit\b/i,
    [/^Credits\b/i, /^To continue this session\b/i, /^╰/],
  );
  if (codexBlock) {
    return [{
      sourceRef: filePath,
      timestamp: null,
      text: codexBlock,
    }];
  }

  const fallbackLines = text.split(/\r?\n/);
  const matches = [];
  const keywordRegex = /\/status|usage|current|remaining|\d{1,3}%/i;
  for (let index = fallbackLines.length - 1; index >= 0; index -= 1) {
    if (!keywordRegex.test(fallbackLines[index])) {
      continue;
    }
    const start = Math.max(0, index - 4);
    const end = Math.min(fallbackLines.length, index + 5);
    const snippet = fallbackLines.slice(start, end).join("\n").trim();
    if (snippet) {
      matches.push({
        sourceRef: `${filePath}:${index + 1}`,
        timestamp: null,
        text: snippet,
      });
      break;
    }
  }
  return matches;
}

function extractNamedStatusesFromText(text) {
  const normalized = normalizeTerminalTranscript(text);
  const lines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const result = {};

  const setIfMatch = (field, candidateLine) => {
    if (result[field] !== undefined) {
      return;
    }
    for (const pattern of STATUS_LABELS[field]) {
      const match = candidateLine.match(pattern);
      if (match) {
        result[field] = Number(match[1]);
        return;
      }
    }
  };

  for (const line of lines) {
    setIfMatch("usagePct", line);
    setIfMatch("remaining5hPct", line);
    setIfMatch("remainingWeekPct", line);
  }

  const keyValuePatterns = [
    ["usagePct", /usage_pct\s*[:=]\s*(\d{1,3})%?/i],
    ["remaining5hPct", /remaining_?5h_pct\s*[:=]\s*(\d{1,3})%?/i],
    ["remainingWeekPct", /remaining_?week_pct\s*[:=]\s*(\d{1,3})%?/i],
    ["usagePct", /usage\s*[:=]\s*(\d{1,3})%/i],
    ["usagePct", /current\s*[:=]\s*(\d{1,3})%/i],
    ["remaining5hPct", /5h(?:\s+remaining)?\s*[:=]\s*(\d{1,3})%/i],
    ["remaining5hPct", /remaining\s+5h\s*[:=]\s*(\d{1,3})%/i],
    ["remainingWeekPct", /week(?:\s+remaining)?\s*[:=]\s*(\d{1,3})%/i],
    ["remainingWeekPct", /remaining\s+week\s*[:=]\s*(\d{1,3})%/i],
    ["remaining5hPct", /5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left/i],
    ["remainingWeekPct", /weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left/i],
  ];
  for (const [field, pattern] of keyValuePatterns) {
    if (result[field] !== undefined) {
      continue;
    }
    const match = normalized.match(pattern);
    if (match) {
      result[field] = Number(match[1]);
    }
  }

  const extractFollowingPercent = (anchorPattern) => {
    const anchorIndex = lines.findIndex((line) => anchorPattern.test(line));
    if (anchorIndex === -1) {
      return null;
    }
    for (let index = anchorIndex + 1; index < Math.min(lines.length, anchorIndex + 8); index += 1) {
      const match = lines[index].match(/(\d{1,3})%\s+used/i);
      if (match) {
        return Number(match[1]);
      }
    }
    return null;
  };

  const claudeCurrentSessionUsed = extractFollowingPercent(/Current session\b/i);
  const claudeCurrentWeekUsed = extractFollowingPercent(/Current week\b/i);
  if (claudeCurrentSessionUsed !== null || claudeCurrentWeekUsed !== null) {
    if (result.usagePct === undefined && claudeCurrentSessionUsed !== null) {
      result.usagePct = claudeCurrentSessionUsed;
    }
    if (result.remaining5hPct === undefined && claudeCurrentSessionUsed !== null) {
      result.remaining5hPct = Math.max(0, 100 - claudeCurrentSessionUsed);
    }
    if (result.remainingWeekPct === undefined && claudeCurrentWeekUsed !== null) {
      result.remainingWeekPct = Math.max(0, 100 - claudeCurrentWeekUsed);
    }
  }

  const tableHeaderIndex = lines.findIndex((line) =>
    /\bSESSION\b/i.test(line) && /\bUSAGE\b/i.test(line) && /\b5H\b/i.test(line) && /\bWEEK\b/i.test(line),
  );
  if (tableHeaderIndex !== -1) {
    for (let index = tableHeaderIndex + 1; index < lines.length; index += 1) {
      const row = lines[index];
      const percentages = [...row.matchAll(/(\d{1,3})%/g)].map((match) => Number(match[1]));
      if (percentages.length >= 3) {
        result.usagePct = result.usagePct ?? percentages[0];
        result.remaining5hPct = result.remaining5hPct ?? percentages[1];
        result.remainingWeekPct = result.remainingWeekPct ?? percentages[2];
        break;
      }
    }
  }

  for (const line of lines) {
    const fiveHourLimit = line.match(/5h\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left/i);
    if (fiveHourLimit && result.remaining5hPct === undefined) {
      result.remaining5hPct = Number(fiveHourLimit[1]);
    }
    const weeklyLimit = line.match(/weekly\s+limit\s*:\s*\[[^\]]*\]\s*(\d{1,3})%\s*left/i);
    if (weeklyLimit && result.remainingWeekPct === undefined) {
      result.remainingWeekPct = Number(weeklyLimit[1]);
    }
  }

  if (result.remaining5hPct !== undefined && result.usagePct === undefined) {
    result.usagePct = Math.max(0, 100 - Number(result.remaining5hPct));
  }
  if (result.remainingWeekPct !== undefined && result.usagePct === undefined) {
    result.usagePct = Math.max(0, 100 - Number(result.remainingWeekPct));
  }

  if (Object.keys(result).length === 0) {
    return null;
  }

  return {
    usagePct: result.usagePct ?? null,
    remaining5hPct: result.remaining5hPct ?? null,
    remainingWeekPct: result.remainingWeekPct ?? null,
    rawStatusText: normalized.trim() || null,
  };
}

function collectCandidateFiles(rootDir) {
  const candidates = [];
  const directFiles = [
    path.join(rootDir, "history.jsonl"),
    path.join(rootDir, "session_index.jsonl"),
    path.join(rootDir, "log", "cdx-session.log"),
    path.join(rootDir, "log", "codex-tui.log"),
  ];
  for (const filePath of directFiles) {
    if (safeStat(filePath)) {
      candidates.push(filePath);
    }
  }

  const sessionsDir = path.join(rootDir, "sessions");
  if (!safeStat(sessionsDir)) {
    return candidates;
  }

  const walk = (dirPath) => {
    let entries = [];
    try {
      entries = fs.readdirSync(dirPath, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".")) {
        continue;
      }
      if (["cache", "plugins", "skills", "memories", "sqlite", "shell_snapshots", "tmp"].includes(entry.name)) {
        continue;
      }
      const entryPath = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        walk(entryPath);
        continue;
      }
      if (entry.isFile() && (entry.name.endsWith(".jsonl") || entry.name.endsWith(".log"))) {
        candidates.push(entryPath);
      }
    }
  };

  walk(sessionsDir);
  return candidates;
}

function findLatestStatusArtifact(rootDir) {
  const candidates = collectCandidateFiles(rootDir);
  const records = [];
  for (const filePath of candidates) {
    if (filePath.endsWith(".jsonl")) {
      records.push(...extractJsonlTexts(filePath));
      continue;
    }
    if (filePath.endsWith(".log")) {
      records.push(...extractLogBlock(filePath));
    }
  }

  let best = null;
  for (const candidate of records) {
    const parsed = extractNamedStatusesFromText(candidate.text);
    if (!parsed) {
      continue;
    }
    const timestamp = candidate.timestamp ? Date.parse(candidate.timestamp) : 0;
    const score = Number.isNaN(timestamp) ? 0 : timestamp;
    if (!best || score >= best.score) {
      best = {
        score,
        sourceRef: candidate.sourceRef,
        ...parsed,
      };
      if (candidate.timestamp) {
        best.updatedAt = new Date(candidate.timestamp).toISOString();
      }
    }
  }

  return best;
}

module.exports = {
  extractNamedStatusesFromText,
  findLatestStatusArtifact,
};
