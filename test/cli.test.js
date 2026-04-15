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
    stdin: { isTTY: true },
    stdout: { write: (value) => { stdout += value; } },
    stderr: { write: (value) => { stderr += value; } },
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function makeAuthHarness(initialAuth = {}) {
  const calls = [];
  const authByHome = new Map(Object.entries(initialAuth));

  const getHome = (options = {}) => options?.env?.CODEX_HOME || options?.env?.HOME || null;

  const spawnSync = (command, args, options = {}) => {
    calls.push({ kind: "spawnSync", command, args, options });
    const home = getHome(options);
    const authed = authByHome.get(home) ?? false;
    if (command === "codex" && args[0] === "login" && args[1] === "status") {
      return {
        status: 0,
        stdout: authed ? "Logged in using ChatGPT\n" : "Not logged in\n",
        stderr: "",
      };
    }
    if (command === "claude" && args[0] === "auth" && args[1] === "status") {
      return {
        status: 0,
        stdout: `${JSON.stringify({ loggedIn: authed, authMethod: authed ? "oauth" : "none" })}\n`,
        stderr: "",
      };
    }
    return { status: 0, stdout: "", stderr: "" };
  };

  const spawn = (command, args, options) => {
    calls.push({ kind: "spawn", command, args, options });
    const child = new EventEmitter();
    child.stdin = null;
    child.stdout = null;
    child.stderr = null;
    const home = getHome(options);
    if (command === "codex" && args[0] === "login" && args.length === 1) {
      authByHome.set(home, true);
    }
    if (command === "codex" && args[0] === "logout" && args.length === 1) {
      authByHome.set(home, false);
    }
    if (command === "claude" && args[0] === "auth" && args[1] === "login") {
      authByHome.set(home, true);
    }
    if (command === "claude" && args[0] === "auth" && args[1] === "logout") {
      authByHome.set(home, false);
    }
    process.nextTick(() => child.emit("close", 0));
    return child;
  };

  return { calls, spawn, spawnSync, authByHome };
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
  const launcher = makeAuthHarness();
  const io = makeIo();
  await main(["add", "main"], { ...io, env: { CDX_HOME: dir }, spawn: launcher.spawn, spawnSync: launcher.spawnSync, stdin: io.stdin });
  assert.match(io.getStdout(), /Created session main/);
  const io2 = makeIo();
  await main(["main"], { ...io2, env: { CDX_HOME: dir }, spawn: launcher.spawn, spawnSync: launcher.spawnSync, stdin: io2.stdin });
  assert.match(io2.getStdout(), /Launching codex session main/);
  const authProbe = launcher.calls.find((call) => call.kind === "spawnSync" && call.command === "codex" && call.args[0] === "login" && call.args[1] === "status");
  const bootstrapLogin = launcher.calls.find((call) => call.kind === "spawn" && call.command === "codex" && call.args[0] === "login" && call.args.length === 1);
  const launchSpawn = launcher.calls.find((call) => call.kind === "spawn" && call.command === "script");
  assert.ok(authProbe);
  assert.ok(bootstrapLogin);
  assert.ok(launchSpawn);
  assert.deepEqual(launchSpawn.args.slice(0, 3), ["-q", path.join(dir, "profiles", encodeURIComponent("main"), "log", "cdx-session.log"), "codex"]);
  assert.deepEqual(launchSpawn.args.slice(3, 6), ["--no-alt-screen", "--cd", process.cwd()]);
  assert.equal(launchSpawn.options.env.CODEX_HOME, path.join(dir, "profiles", encodeURIComponent("main")));
});

test("provider-specific sessions are supported", async () => {
  const dir = makeTempDir();
  const launcher = makeAuthHarness();
  const createIo = makeIo();
  await main(["add", "claude", "work1"], { ...createIo, env: { CDX_HOME: dir }, spawn: launcher.spawn, spawnSync: launcher.spawnSync, stdin: createIo.stdin });
  assert.match(createIo.getStdout(), /Created session work1 \(claude\)/);

  const launchIo = makeIo();
  await main(["work1"], { ...launchIo, env: { CDX_HOME: dir }, spawn: launcher.spawn, spawnSync: launcher.spawnSync, stdin: launchIo.stdin });
  assert.match(launchIo.getStdout(), /Launching claude session work1/);
  const bootstrapLogin = launcher.calls.find((call) => call.kind === "spawn" && call.command === "claude" && call.args[0] === "auth" && call.args[1] === "login");
  const launchSpawn = launcher.calls.find((call) => call.kind === "spawn" && call.command === "script");
  assert.ok(bootstrapLogin);
  assert.ok(launchSpawn);
  assert.deepEqual(launchSpawn.args.slice(0, 3), ["-q", path.join(dir, "profiles", encodeURIComponent("work1"), "claude-home", "log", "cdx-session.log"), "claude"]);
  assert.deepEqual(launchSpawn.args.slice(3), ["--name", "work1"]);
  assert.equal(launchSpawn.options.cwd, process.cwd());
  assert.equal(launchSpawn.options.env.HOME, path.join(dir, "profiles", encodeURIComponent("work1"), "claude-home"));
});

test("launch forwards termination signals to the spawned provider", async () => {
  const dir = makeTempDir();
  const createIo = makeIo();
  const launcher = makeAuthHarness();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir }, spawn: launcher.spawn, spawnSync: launcher.spawnSync, stdin: createIo.stdin });

  const signalEmitter = new EventEmitter();
  const killedSignals = [];
  const spawn = (command, args, options) => {
    const child = new EventEmitter();
    child.kill = (signal) => {
      killedSignals.push(signal);
      process.nextTick(() => child.emit("close", null, signal));
      return true;
    };
    return child;
  };

  const launchIo = makeIo();
  const run = main(["main"], {
    ...launchIo,
    env: { CDX_HOME: dir },
    spawn,
    spawnSync: launcher.spawnSync,
    signalEmitter,
    stdin: launchIo.stdin,
  });
  process.nextTick(() => signalEmitter.emit("SIGINT"));

  await assert.rejects(run, (error) => {
    assert.match(error.message, /interrupted by SIGINT/);
    assert.equal(error.code, 130);
    return true;
  });
  assert.deepEqual(killedSignals, ["SIGINT"]);
});

test("logout clears auth and login reauthenticates only the named session", async () => {
  const dir = makeTempDir();
  const harness = makeAuthHarness();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: createIo.stdin });
  const logoutIo = makeIo();
  await main(["logout", "main"], { ...logoutIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: logoutIo.stdin });
  assert.match(logoutIo.getStdout(), /Logged out session main \(codex\)/);

  const launchIo = makeIo();
  await assert.rejects(
    () => main(["main"], { ...launchIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: launchIo.stdin }),
    /Run: cdx login main/,
  );

  const loginIo = makeIo();
  await main(["login", "main"], { ...loginIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: loginIo.stdin });
  assert.match(loginIo.getStdout(), /Reauthenticated session main \(codex\)/);
});

test("smoke flow includes remove and deletes the session root", async () => {
  const dir = makeTempDir();
  const harness = makeAuthHarness();
  const io = makeIo();
  await main(["add", "main"], { ...io, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: io.stdin });
  await main(["main"], { ...io, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: io.stdin });
  await main(["status"], { ...io, env: { CDX_HOME: dir } });
  await main(["logout", "main"], { ...io, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: io.stdin });
  await main(["login", "main"], { ...io, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: io.stdin });
  await main(["rmv", "main", "--force"], { ...io, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: io.stdin });

  assert.match(io.getStdout(), /Removed session main/);
  assert.equal(fs.existsSync(path.join(dir, "profiles", encodeURIComponent("main"))), false);
  assert.equal(fs.existsSync(path.join(dir, "state", `${encodeURIComponent("main")}.json`)), false);
});

test("list sessions shows next actions", async () => {
  const dir = makeTempDir();
  const harness = makeAuthHarness();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: createIo.stdin });
  const createIo2 = makeIo();
  await main(["add", "claude", "work1"], { ...createIo2, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: createIo2.stdin });

  const io = makeIo();
  await main([], { ...io, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /Next actions:/);
  assert.match(io.getStdout(), /PROVIDER/);
  assert.match(io.getStdout(), /claude/);
  assert.match(io.getStdout(), /cdx rmv <name>/);
  assert.match(io.getStdout(), /cdx status/);
});

test("remove sessions can be forced or confirmed", async () => {
  const dir = makeTempDir();
  const harness = makeAuthHarness();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: createIo.stdin });

  const forceIo = makeIo();
  await main(["rmv", "main", "--force"], { ...forceIo, env: { CDX_HOME: dir } });
  assert.match(forceIo.getStdout(), /Removed session main/);

  const dir2 = makeTempDir();
  const harness2 = makeAuthHarness();
  const createIo2 = makeIo();
  await main(["add", "work1"], { ...createIo2, env: { CDX_HOME: dir2 }, spawn: harness2.spawn, spawnSync: harness2.spawnSync, stdin: createIo2.stdin });

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
  const harness = makeAuthHarness();
  const createIo = makeIo();
  await main(["add", "main"], { ...createIo, env: { CDX_HOME: dir }, spawn: harness.spawn, spawnSync: harness.spawnSync, stdin: createIo.stdin });

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
