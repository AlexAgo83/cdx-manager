#!/usr/bin/env node

const path = require("node:path");
const { runPython } = require("./python-runner");

const scriptPath = path.join(__dirname, "cdx");
const exitCode = runPython([scriptPath, ...process.argv.slice(2)], { expandGlobs: false });

process.exit(exitCode);
