"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { main } = require("../src/cli");

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

  const io2 = makeIo();
  await main(["main"], { ...io2, env: { CDX_HOME: dir } });
  assert.match(io2.getStdout(), /Launching codex session main/);
});

test("list sessions shows next actions", async () => {
  const dir = makeTempDir();
  const io = makeIo();
  await main([], { ...io, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /Next actions:/);
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
