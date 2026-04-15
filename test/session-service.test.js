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
