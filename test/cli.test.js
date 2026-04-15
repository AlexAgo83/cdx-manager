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

test("add and launch sessions", async () => {
  const dir = makeTempDir();
  const io = makeIo();
  await main(["add", "main"], { ...io, env: { CDX_HOME: dir } });
  assert.match(io.getStdout(), /Created session main/);

  const io2 = makeIo();
  await main(["main"], { ...io2, env: { CDX_HOME: dir } });
  assert.match(io2.getStdout(), /Launching codex session main/);
});

