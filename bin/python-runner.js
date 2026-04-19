#!/usr/bin/env node

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const PYTHON_VERSION_CHECK = "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)";
const PYTHON_CACHE_PREFIX = path.join(os.tmpdir(), "cdx-manager-pycache");
const SIGNAL_EXIT_CODES = {
  SIGHUP: 129,
  SIGINT: 130,
  SIGTERM: 143,
};

const WINDOWS_CANDIDATES = [
  { command: "py", args: ["-3"], label: "py -3" },
  { command: "python", args: [], label: "python" },
  { command: "python3", args: [], label: "python3" },
];

const UNIX_CANDIDATES = [
  { command: "python3", args: [], label: "python3" },
  { command: "python", args: [], label: "python" },
];

function getCandidates(platform = process.platform) {
  return platform === "win32" ? WINDOWS_CANDIDATES : UNIX_CANDIDATES;
}

function probeCandidate(candidate) {
  const result = spawnSync(
    candidate.command,
    [...candidate.args, "-c", PYTHON_VERSION_CHECK],
    { stdio: "ignore", windowsHide: true }
  );
  return result.status === 0;
}

function findPython(platform = process.platform) {
  for (const candidate of getCandidates(platform)) {
    if (probeCandidate(candidate)) {
      return candidate;
    }
  }
  return null;
}

function hasGlobCharacters(value) {
  return value.includes("*") || value.includes("?") || value.includes("[");
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function segmentToRegExp(segment) {
  const pattern = escapeRegex(segment).replace(/\\\*/g, ".*").replace(/\\\?/g, ".");
  return new RegExp(`^${pattern}$`);
}

function expandGlob(pattern) {
  const pathLike = pattern.includes("/") || pattern.includes("\\") || path.isAbsolute(pattern);
  if (!hasGlobCharacters(pattern) || !pathLike) {
    return [pattern];
  }

  const absolute = path.isAbsolute(pattern);
  const root = absolute ? path.parse(pattern).root : process.cwd();
  const relativePattern = absolute ? path.relative(root, pattern) : pattern;
  const segments = relativePattern.split(/[\\/]+/).filter(Boolean);
  const matches = [];

  const walk = (currentPath, index) => {
    if (index >= segments.length) {
      if (fs.existsSync(currentPath)) {
        matches.push(currentPath);
      }
      return;
    }

    const segment = segments[index];
    const nextIndex = index + 1;

    if (!hasGlobCharacters(segment)) {
      walk(path.join(currentPath, segment), nextIndex);
      return;
    }

    if (!fs.existsSync(currentPath) || !fs.statSync(currentPath).isDirectory()) {
      return;
    }

    const matcher = segmentToRegExp(segment);
    for (const entry of fs.readdirSync(currentPath, { withFileTypes: true })) {
      if (matcher.test(entry.name)) {
        walk(path.join(currentPath, entry.name), nextIndex);
      }
    }
  };

  walk(root, 0);
  return matches.length > 0 ? matches : [pattern];
}

function expandArgs(args) {
  const expanded = [];
  for (const arg of args) {
    expanded.push(...expandGlob(arg));
  }
  return expanded;
}

function prepareEnv(env = process.env) {
  const nextEnv = { ...env };
  if (!nextEnv.PYTHONPYCACHEPREFIX) {
    fs.mkdirSync(PYTHON_CACHE_PREFIX, { recursive: true });
    nextEnv.PYTHONPYCACHEPREFIX = PYTHON_CACHE_PREFIX;
  }
  return nextEnv;
}

function runPython(args, options = {}) {
  const platform = options.platform || process.platform;
  const candidate = findPython(platform);

  if (!candidate) {
    const tried = getCandidates(platform).map((item) => item.label).join(", ");
    console.error(`cdx: no compatible Python 3 interpreter found. Tried: ${tried}.`);
    console.error("Install Python 3 and make one of those commands available on PATH.");
    return 127;
  }

  const finalArgs = options.expandGlobs === false ? args.slice() : expandArgs(args);
  const result = spawnSync(
    candidate.command,
    [...candidate.args, ...finalArgs],
    {
      env: prepareEnv(options.env),
      stdio: "inherit",
      windowsHide: true,
    }
  );

  if (result.error) {
    console.error(`cdx: failed to launch ${candidate.label}: ${result.error.message}`);
    return 127;
  }

  if (result.signal) {
    return SIGNAL_EXIT_CODES[result.signal] || 128;
  }

  return typeof result.status === "number" ? result.status : 1;
}

if (require.main === module) {
  process.exit(runPython(process.argv.slice(2)));
}

module.exports = {
  expandArgs,
  findPython,
  runPython,
};
