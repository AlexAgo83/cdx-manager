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

test("launch rehydrates a stored session state", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  const launched = service.launchSession("main");

  assert.equal(launched.name, "main");
  assert.equal(launched.state.status, "ready");
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
  service.removeSession("main");

  assert.equal(fs.existsSync(path.join(dir, "state", `${encodeURIComponent("main")}.json`)), false);
});

test("reject duplicate names and unknown providers", () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });

  service.createSession("main");
  assert.throws(() => service.createSession("main"), /already exists/);
  assert.throws(() => service.createSession("work2", "other"), /Unsupported provider/);
});
