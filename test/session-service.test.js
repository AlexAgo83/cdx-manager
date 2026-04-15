"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { createSessionService } = require("../src/session-service");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "cdx-manager-"));
}

test("create, list, and remove sessions", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  service.createSession("work1", "claude");

  const rows = service.formatListRows();
  assert.equal(rows.length, 2);
  assert.equal(rows[0].name, "main");
  assert.equal(rows[1].name, "work1");

  service.removeSession("main");
  assert.equal(service.listSessions().length, 1);
});

test("create session with explicit provider", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  const session = service.createSession("work1", "claude");
  assert.equal(session.provider, "claude");
  assert.equal(service.getSession("work1").provider, "claude");
});

test("launch preserves the provider for named sessions", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("work1", "claude");
  const launched = service.launchSession("work1");

  assert.equal(launched.provider, "claude");
  assert.equal(service.getSession("work1").provider, "claude");
});

test("launch rehydrates a stored session state", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  const launched = service.launchSession("main");

  assert.equal(launched.name, "main");
  assert.equal(launched.lastLaunchedAt, launched.updatedAt);
  assert.equal(service.getSession("main").provider, "codex");
});

test("launch fails when session state is missing", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  fs.rmSync(path.join(dir, "state", `${encodeURIComponent("main")}.json`));
  assert.throws(() => service.launchSession("main"), /Reconnect required/);
});

test("remove deletes persisted session state", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  const sessionRoot = path.join(dir, "profiles", encodeURIComponent("main"));
  service.removeSession("main");

  assert.equal(fs.existsSync(path.join(dir, "state", `${encodeURIComponent("main")}.json`)), false);
  assert.equal(fs.existsSync(sessionRoot), false);
});

test("reject duplicate names and unknown providers", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  assert.throws(() => service.createSession("main"), /already exists/);
  assert.throws(() => service.createSession("work2", "other"), /Unsupported provider/);
});

test("status rows are normalized and sorted by recency", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  service.createSession("work1", "claude");
  service.recordStatus("main", {
    usagePct: 61,
    remaining5hPct: 39,
    remainingWeekPct: 70,
    updatedAt: "2026-04-15T09:00:00.000Z",
    rawStatusText: "main raw",
  });
  service.recordStatus("work1", {
    usagePct: 44,
    remaining5hPct: 56,
    remainingWeekPct: 81,
    updatedAt: "2026-04-15T10:00:00.000Z",
    rawStatusText: "work1 raw",
    sourceRef: "session-2.jsonl",
  });

  const rows = service.getStatusRows();
  assert.equal(rows[0].session_name, "work1");
  assert.equal(rows[0].provider, "claude");
  assert.equal(rows[0].usage_pct, 44);
  assert.equal(rows[0].raw_status_text, "work1 raw");
  assert.equal(rows[1].session_name, "main");
});

test("status rows can be derived from session artifacts", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  const sessionLog = path.join(dir, "profiles", encodeURIComponent("main"), "log", "cdx-session.log");
  fs.mkdirSync(path.dirname(sessionLog), { recursive: true });
  fs.writeFileSync(
    sessionLog,
    [
      "2026-04-15T19:09:31.864Z  INFO /status",
      "Usage: 61%",
      "5h remaining: 39%",
      "Week remaining: 70%",
    ].join("\n"),
  );

  const rows = service.getStatusRows();
  assert.equal(rows[0].session_name, "main");
  assert.equal(rows[0].usage_pct, 61);
  assert.equal(rows[0].remaining_5h_pct, 39);
  assert.equal(rows[0].remaining_week_pct, 70);
  assert.match(rows[0].raw_status_text, /Usage: 61%/);
});

test("status rows can be derived from codex limit output", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  const sessionLog = path.join(dir, "profiles", encodeURIComponent("main"), "log", "cdx-session.log");
  fs.mkdirSync(path.dirname(sessionLog), { recursive: true });
  fs.writeFileSync(
    sessionLog,
    [
      "│  5h limit:             [████████████████████] 100% left",
      "│                        (resets 02:21 on 16 Apr)            │",
      "│  Weekly limit:         [░░░░░░░░░░░░░░░░░░░░] 0% left",
      "│                        (resets 10:10 on 17 Apr)            │",
    ].join("\n"),
  );

  const rows = service.getStatusRows();
  assert.equal(rows[0].session_name, "main");
  assert.equal(rows[0].remaining_5h_pct, 100);
  assert.equal(rows[0].remaining_week_pct, 0);
  assert.equal(rows[0].usage_pct, 0);
});

test("status rows can be derived from claude usage output", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("work1", "claude");
  const sessionLog = path.join(dir, "profiles", encodeURIComponent("work1"), "claude-home", "log", "cdx-session.log");
  fs.mkdirSync(path.dirname(sessionLog), { recursive: true });
  fs.writeFileSync(
    sessionLog,
    [
      "Current session · Resets 2am (Europe/Paris)",
      "",
      "0% used",
      "",
      "Current week (all models) · Resets Apr 21 at 2pm (Europe/Paris)",
      "14% used",
      "",
      "Extra usage",
      "Extra usage not enabled · /extra-usage to enable",
    ].join("\n"),
  );

  const rows = service.getStatusRows();
  assert.equal(rows[0].session_name, "work1");
  assert.equal(rows[0].provider, "claude");
  assert.equal(rows[0].usage_pct, 0);
  assert.equal(rows[0].remaining_5h_pct, 100);
  assert.equal(rows[0].remaining_week_pct, 86);
  assert.match(rows[0].raw_status_text, /Current session/);
});
