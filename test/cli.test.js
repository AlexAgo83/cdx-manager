"use strict";

const assert = require("node:assert/strict");
const EventEmitter = require("node:events");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { main } = require("../src/cli");
const { createSessionService } = require("../src/session-service");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "cdx-cli-"));
}

function makeIo() {
  let stdout = "";
  let stderr = "";
  return {
    env: {},
    stdout: { write: (value) => { stdout += value; } },
    stderr: { write: (value) => { stderr += value; } },
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function makeSpawnRecorder() {
  const calls = [];
  const spawn = (command, args, options) => {
    calls.push({ command, args, options });
    const child = new EventEmitter();
    child.stdin = null;
    child.stdout = null;
    child.stderr = null;
    process.nextTick(() => child.emit("close", 0));
    return child;
  };
  return { calls, spawn };
}

test("help and version commands", async () => {
  const io = makeIo();
  await main(["--help"], io);
  assert.match(io.getStdout(), /Usage:/);

  const io2 = makeIo();
  await main(["--version"], io2);
  assert.match(io2.getStdout(), /0\.1\.0/);
});

test("help and version aliases work cleanly", async () => {
  const helpIo = makeIo();
  await main(["-h"], helpIo);
  assert.match(helpIo.getStdout(), /Usage:/);

  const versionIo = makeIo();
  await main(["-v"], versionIo);
  assert.match(versionIo.getStdout(), /0\.1\.0/);
});

test("add and launch sessions", async () => {
  const dir = makeTempDir();
  const io = makeIo();
  await main(["add", "main"], { ...io, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /Created session main/);

  const launcher = makeSpawnRecorder();
  const io2 = makeIo();
  await main(["main"], { ...io2, env: { CDX_HOME: dir }, spawn: launcher.spawn });
  assert.match(io2.getStdout(), /Launching codex session main/);
  assert.equal(launcher.calls[0].command, "codex");
  assert.deepEqual(launcher.calls[0].args.slice(0, 3), ["--no-alt-screen", "--cd", process.cwd()]);
  assert.equal(launcher.calls[0].options.env.CODEX_HOME, path.join(dir, "profiles", encodeURIComponent("main")));
});

test("provider-specific sessions are supported", async () => {
  const dir = makeTempDir();
  const createIo = makeIo();
  await main(["add", "claude", "work1"], { ...createIo, env: { CDX_HOME: dir } });
  assert.match(createIo.getStdout(), /Created session work1 \(claude\)/);

  const launcher = makeSpawnRecorder();
  const launchIo = makeIo();
  await main(["work1"], { ...launchIo, env: { CDX_HOME: dir }, spawn: launcher.spawn });
  assert.match(launchIo.getStdout(), /Launching claude session work1/);
  assert.equal(launcher.calls[0].options.env.CODEX_HOME, path.join(dir, "profiles", encodeURIComponent("work1")));
});

test("list sessions shows next actions", async () => {
  const dir = makeTempDir();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir } });
  const createIo2 = makeIo();
  await main(["add", "claude", "work1"], { ...createIo2, env: { CDX_HOME: dir } });

  const io = makeIo();
  await main([], { ...io, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /Next actions:/);
  assert.match(io.getStdout(), /PROVIDER/);
  assert.match(io.getStdout(), /claude/);
  assert.match(io.getStdout(), /cdx status/);
});

test("remove sessions can be forced or confirmed", async () => {
  const dir = makeTempDir();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir } });

  const forceIo = makeIo();
  await main(["rmv", "main", "--force"], { ...forceIo, env: { CDX_HOME: dir } });
  assert.match(forceIo.getStdout(), /Removed session main/);

  const dir2 = makeTempDir();
  const createIo2 = makeIo();
  await main(["add", "work1"], { ...createIo2, env: { CDX_HOME: dir2 } });

  const confirmIo = makeIo();
  await main(["rmv", "work1"], {
    ...confirmIo,
    env: { CDX_HOME: dir2 },
    confirmRemove: async () => true,
  });
  assert.match(confirmIo.getStdout(), /Removed session work1/);
});

test("remove can be cancelled", async () => {
  const dir = makeTempDir();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir } });

  const cancelIo = makeIo();
  await main(["rmv", "main"], {
    ...cancelIo,
    env: { CDX_HOME: dir },
    confirmRemove: async () => false,
  });
  assert.match(cancelIo.getStdout(), /Cancelled\./);
});

test("invalid syntax is rejected with usage guidance", async () => {
  const dir = makeTempDir();
  const io = makeIo();
  await assert.rejects(
    () => main(["status", "main", "extra"], { ...io, env: { CDX_HOME: dir } }),
    /Usage: cdx status \[name\]/,
  );
});

test("status renders normalized usage metrics globally and in detail", async () => {
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
  });

  const globalIo = makeIo();
  await main(["status"], { ...globalIo, service, env: { CDX_HOME: dir } });
  assert.match(globalIo.getStdout(), /SESSION\s+PROVIDER\s+USAGE\s+5H LEFT\s+WEEK LEFT\s+UPDATED/);
  assert.match(globalIo.getStdout(), /work1\s+claude\s+44%\s+56%\s+81%/);
  assert.match(globalIo.getStdout(), /main\s+codex\s+61%\s+39%\s+70%/);

  const detailIo = makeIo();
  await main(["status", "work1"], { ...detailIo, service, env: { CDX_HOME: dir } });
  assert.match(detailIo.getStdout(), /Session: work1/);
  assert.match(detailIo.getStdout(), /Provider: claude/);
  assert.match(detailIo.getStdout(), /Raw last \/status:/);
  assert.match(detailIo.getStdout(), /work1 raw/);
});

test("status renders empty state when no sessions exist", async () => {
  const dir = makeTempDir();
  const service = createSessionService({ baseDir: dir });
  const io = makeIo();
  await main(["status"], { ...io, service, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /No saved sessions yet\./);
});
