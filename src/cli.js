"use strict";

const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { createSessionService } = require("./session-service");
const { CdxError } = require("./errors");
const { refreshClaudeSessionStatus } = require("./claude-usage");

const VERSION = "0.1.0";
const LOG_ROTATE_BYTES = 10 * 1024 * 1024; // 10 MB

function printHelp() {
  return [
    "cdx - terminal session manager",
    "",
    "Usage:",
    "  cdx",
    "  cdx status [name] [--json]",
    "  cdx add [provider] <name>",
    "  cdx cp <source> <dest>",
    "  cdx login <name>",
    "  cdx logout <name>",
    "  cdx rmv <name> [--force]",
    "  cdx clean [name]",
    "  cdx <name>",
    "  cdx --help",
    "  cdx --version",
  ].join("\n");
}

function printVersion() {
  return VERSION;
}

function isHelpFlagOnly(argv) {
  return argv.length === 1 && (argv[0] === "--help" || argv[0] === "-h");
}

function isVersionFlagOnly(argv) {
  return argv.length === 1 && (argv[0] === "--version" || argv[0] === "-v");
}

function formatSessions(service) {
  const rows = service.formatListRows();
  const hasProvider = rows.some((row) => row.provider);
  const headers = ["SESSION"];
  if (hasProvider) {
    headers.push("PROVIDER");
  }
  headers.push("UPDATED");
  const lines = [
    "Known sessions:",
    headers.join("  "),
  ];
  for (const row of rows) {
    const parts = [row.name];
    if (hasProvider) {
      parts.push(row.provider || "n/a");
    }
    parts.push(row.updatedAt || "-");
    lines.push(parts.join("  "));
  }
  lines.push("");
  lines.push("Next actions:");
  lines.push("  cdx add <name>");
  lines.push("  cdx <name>");
  lines.push("  cdx login <name>");
  lines.push("  cdx logout <name>");
  lines.push("  cdx rmv <name>");
  lines.push("  cdx status");
  return lines.join("\n");
}

function formatRelativeAge(isoValue) {
  if (!isoValue) {
    return "-";
  }
  const timestamp = Date.parse(isoValue);
  if (Number.isNaN(timestamp)) {
    return "-";
  }
  const deltaMs = Date.now() - timestamp;
  if (deltaMs < 0) {
    return "just now";
  }
  const minutes = Math.floor(deltaMs / 60000);
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatPct(value) {
  return value === null || value === undefined ? "n/a" : `${value}%`;
}

function padTable(columns) {
  const widths = columns[0].map((_, columnIndex) =>
    Math.max(...columns.map((row) => String(row[columnIndex]).length)),
  );
  return columns
    .map((row) => row.map((value, index) => String(value).padEnd(widths[index])).join("  "))
    .join("\n");
}

function formatStatusRows(rows) {
  const hasProvider = new Set(rows.map((row) => row.provider)).size > 1;
  const headers = hasProvider
    ? ["SESSION", "PROVIDER", "5H LEFT", "WEEK LEFT", "RESET", "UPDATED"]
    : ["SESSION", "5H LEFT", "WEEK LEFT", "RESET", "UPDATED"];
  if (rows.length === 0) {
    return ["SESSION  5H LEFT  WEEK LEFT  RESET  UPDATED", "No saved sessions yet."].join("\n");
  }
  const tableRows = rows.map((row) => {
    const base = [row.session_name];
    if (hasProvider) {
      base.push(row.provider || "n/a");
    }
    base.push(
      formatPct(row.remaining_5h_pct),
      formatPct(row.remaining_week_pct),
      row.reset_at || "-",
      formatRelativeAge(row.updated_at),
    );
    return base;
  });
  return [
    padTable([headers, ...tableRows]),
    "",
    "Tip: run /status in codex to refresh. Claude sessions refresh automatically.",
  ].join("\n");
}

function formatStatusDetail(row) {
  const lines = [
    `Session: ${row.session_name}`,
    `Provider: ${row.provider || "n/a"}`,
    `5h left: ${formatPct(row.remaining_5h_pct)}`,
    `Week left: ${formatPct(row.remaining_week_pct)}`,
    `Next reset: ${row.reset_at || "n/a"}`,
    `Updated: ${formatRelativeAge(row.updated_at)}`,
  ];
  return lines.join("\n");
}

function getAuthHome(session) {
  return session.authHome || session.sessionRoot || session.codexHome;
}

function getLaunchTranscriptPath(session) {
  return path.join(getAuthHome(session), "log", "cdx-session.log");
}

function rotateLogIfNeeded(logPath) {
  try {
    const stat = fs.statSync(logPath);
    if (stat.size >= LOG_ROTATE_BYTES) {
      fs.writeFileSync(logPath, "");
    }
  } catch {
    // File doesn't exist yet — nothing to rotate
  }
}

function wrapLaunchWithTranscript(session, spec, options = {}) {
  if (options.captureTranscript === false) {
    return spec;
  }
  const transcriptPath = getLaunchTranscriptPath(session);
  fs.mkdirSync(path.dirname(transcriptPath), { recursive: true });
  rotateLogIfNeeded(transcriptPath);
  return {
    command: "script",
    args: ["-q", transcriptPath, spec.command, ...spec.args],
    options: spec.options,
    label: spec.label,
  };
}

function buildLaunchSpec(session, options = {}) {
  const cwd = options.cwd || process.cwd();
  if (session.provider === "claude") {
    return {
      command: "claude",
      args: ["--name", session.name],
      options: {
        cwd,
        stdio: "inherit",
        env: {
          ...process.env,
          ...(options.env || {}),
          HOME: getAuthHome(session),
        },
      },
      label: "claude",
    };
  }
  return wrapLaunchWithTranscript(session, {
    command: "codex",
    args: ["--no-alt-screen", "--cd", cwd],
    options: {
      stdio: "inherit",
      env: {
        ...process.env,
        ...(options.env || {}),
        CODEX_HOME: getAuthHome(session),
      },
    },
    label: "codex",
  }, options);
}

function buildLoginStatusSpec(session, options = {}) {
  const env = {
    ...process.env,
    ...(options.env || {}),
  };
  if (session.provider === "claude") {
    env.HOME = getAuthHome(session);
    return {
      command: "claude",
      args: ["auth", "status"],
      env,
      parser: (output) => {
        try {
          return Boolean(JSON.parse(output || "{}").loggedIn);
        } catch {
          return false;
        }
      },
      label: "claude auth status",
    };
  }
  env.CODEX_HOME = getAuthHome(session);
  return {
    command: "codex",
    args: ["login", "status"],
    env,
    parser: (output) => {
      const text = output || "";
      if (/Not logged in/i.test(text)) {
        return false;
      }
      return /Logged in/i.test(text);
    },
    label: "codex login status",
  };
}

function buildAuthActionSpec(session, action, options = {}) {
  const cwd = options.cwd || process.cwd();
  const env = {
    ...process.env,
    ...(options.env || {}),
  };
  if (session.provider === "claude") {
    env.HOME = getAuthHome(session);
    return {
      command: "claude",
      args: ["auth", action],
      options: { cwd, stdio: "inherit", env },
      label: `claude auth ${action}`,
    };
  }
  env.CODEX_HOME = getAuthHome(session);
  return {
    command: "codex",
    args: [action],
    options: { cwd, stdio: "inherit", env },
    label: `codex ${action}`,
  };
}

function probeProviderAuth(session, options = {}) {
  const spawnSyncFn = options.spawnSync || spawnSync;
  const spec = buildLoginStatusSpec(session, options);
  const result = spawnSyncFn(spec.command, spec.args, {
    env: spec.env,
    encoding: "utf8",
  });
  if (result.error) {
    throw new CdxError(`Failed to check login status for ${session.name}: ${result.error.message}`);
  }
  return spec.parser(`${result.stdout || ""}${result.stderr || ""}`);
}

function signalExitCode(signal) {
  const map = {
    SIGHUP: 129,
    SIGINT: 130,
    SIGTERM: 143,
  };
  return map[signal] || 1;
}

function runInteractiveProviderCommand(session, action, options = {}) {
  const spawnFn = options.spawn || spawn;
  const signalEmitter = options.signalEmitter || process;
  const spec = action === "launch" ? buildLaunchSpec(session, options) : buildAuthActionSpec(session, action, options);
  const child = spawnFn(spec.command, spec.args, spec.options);
  const signals = ["SIGINT", "SIGTERM", "SIGHUP"];
  const signalHandlers = new Map();
  let settled = false;
  let forwardedSignal = null;

  const cleanup = () => {
    for (const [signal, handler] of signalHandlers.entries()) {
      signalEmitter.removeListener(signal, handler);
    }
  };

  const finish = (handler) => {
    if (settled) {
      return;
    }
    settled = true;
    cleanup();
    handler();
  };

  function handleSignal(signal) {
    forwardedSignal = signal;
    if (child && typeof child.kill === "function") {
      child.kill(signal);
    }
  }

  for (const signal of signals) {
    const handler = () => handleSignal(signal);
    signalHandlers.set(signal, handler);
    signalEmitter.on(signal, handler);
  }

  return new Promise((resolve, reject) => {
    child.on("error", (error) => {
      finish(() => reject(new CdxError(`Failed to run ${spec.label} for ${session.name}: ${error.message}`)));
    });
    child.on("close", (code, signal) => {
      finish(() => {
        const terminatedBy = signal || forwardedSignal;
        if (terminatedBy) {
          reject(new CdxError(`${spec.label} interrupted by ${terminatedBy} for session ${session.name}`, signalExitCode(terminatedBy)));
          return;
        }
        if (code === 0) {
          resolve(code);
          return;
        }
        reject(new CdxError(`${spec.label} exited with code ${code} for session ${session.name}`));
      });
    });
  });
}

async function ensureSessionAuthentication(session, options = {}, behavior = "launch") {
  const isAuthenticated = probeProviderAuth(session, options);
  if (isAuthenticated) {
    return { authenticated: true, checked: true };
  }
  if (behavior === "probe-only") {
    return { authenticated: false, checked: true };
  }
  if (behavior === "launch") {
    throw new CdxError(`Session ${session.name} is not authenticated. Run: cdx login ${session.name}`);
  }
  if (!options.stdin || !options.stdin.isTTY) {
    throw new CdxError(`Session ${session.name} is not authenticated. Run: cdx login ${session.name}`);
  }
  await runInteractiveProviderCommand(session, "login", options);
  return { authenticated: true, checked: true, bootstrapped: true };
}

function parseAddArgs(args) {
  if (args.length === 1) {
    return { provider: "codex", name: args[0] };
  }
  if (args.length === 2) {
    return { provider: args[0], name: args[1] };
  }
  throw new CdxError("Usage: cdx add [provider] <name>");
}

function confirmRemoval(stdin, stdout, name) {
  if (!stdin || !stdin.isTTY) {
    throw new CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.");
  }
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: stdin, output: stdout });
    rl.question(`Remove session ${name}? [y/N] `, (answer) => {
      rl.close();
      resolve(/^y(es)?$/i.test(answer.trim()));
    });
  });
}

function parseCopyArgs(args) {
  if (args.length !== 2) {
    throw new CdxError("Usage: cdx cp <source> <dest>");
  }
  return { source: args[0], dest: args[1] };
}

function parseRemoveArgs(args) {
  const force = args.includes("--force");
  const names = args.filter((item) => item !== "--force");
  const unknownFlags = args.filter((item) => item.startsWith("-") && item !== "--force");
  if (unknownFlags.length > 0 || names.length !== 1 || args.length > 2) {
    throw new CdxError("Usage: cdx rmv <name> [--force]");
  }
  return { name: names[0], force };
}

async function main(argv, options = {}) {
  const env = options.env || process.env;
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  const stdin = options.stdin || process.stdin;
  const service = options.service || createSessionService({ env });

  if (argv.some((arg) => arg === "--help" || arg === "-h")) {
    if (!isHelpFlagOnly(argv)) {
      throw new CdxError("Usage: cdx --help");
    }
    stdout.write(`${printHelp()}\n`);
    return 0;
  }

  if (argv.some((arg) => arg === "--version" || arg === "-v")) {
    if (!isVersionFlagOnly(argv)) {
      throw new CdxError("Usage: cdx --version");
    }
    stdout.write(`${printVersion()}\n`);
    return 0;
  }

  const [command, ...rest] = argv;

  if (!command) {
    stdout.write(`${formatSessions(service)}\n`);
    return 0;
  }

  if (command === "add") {
    const { provider, name } = parseAddArgs(rest);
    const session = service.createSession(name, provider);
    stdout.write(`Created session ${name} (${provider})\n`);
    await ensureSessionAuthentication(session, options, "bootstrap");
    service.updateAuthState(name, (auth) => ({
      ...auth,
      status: "authenticated",
      lastCheckedAt: new Date().toISOString(),
      lastAuthenticatedAt: new Date().toISOString(),
      lastLoggedOutAt: auth.lastLoggedOutAt || null,
    }));
    return 0;
  }

  if (command === "clean") {
    const targets = rest.length === 0
      ? service.listSessions()
      : (() => {
          if (rest.length !== 1) throw new CdxError("Usage: cdx clean [name]");
          const s = service.getSession(rest[0]);
          if (!s) throw new CdxError(`Unknown session: ${rest[0]}`);
          return [s];
        })();
    for (const session of targets) {
      const logPath = getLaunchTranscriptPath(session);
      try {
        const stat = fs.statSync(logPath);
        fs.writeFileSync(logPath, "");
        const kb = Math.round(stat.size / 1024);
        stdout.write(`Cleared ${session.name} log (${kb} KB freed)\n`);
      } catch {
        stdout.write(`${session.name}: no log found\n`);
      }
    }
    return 0;
  }

  if (command === "cp") {
    const { source, dest } = parseCopyArgs(rest);
    const { overwritten } = service.copySession(source, dest);
    stdout.write(`Copied session ${source} to ${dest}${overwritten ? " (overwritten)" : ""}\n`);
    return 0;
  }

  if (command === "rmv") {
    const { name, force } = parseRemoveArgs(rest);
    if (!force) {
      const confirmed = options.confirmRemove
        ? await options.confirmRemove(name)
        : await confirmRemoval(stdin, stdout, name);
      if (!confirmed) {
        stdout.write("Cancelled.\n");
        return 0;
      }
    }
    service.removeSession(name);
    stdout.write(`Removed session ${name}\n`);
    return 0;
  }

  if (command === "status") {
    const jsonFlag = rest.includes("--json");
    const args = rest.filter((arg) => arg !== "--json");

    const refreshClaudeSessions = async () => {
      const sessions = service.listSessions();
      await Promise.all(
        sessions
          .filter((s) => s.provider === "claude")
          .map(async (s) => {
            try {
              const usage = await (options.refreshClaudeSessionStatus || refreshClaudeSessionStatus)(s);
              if (usage) {
                service.recordStatus(s.name, usage);
              }
            } catch {
              // Silently ignore refresh failures (expired token, no network, etc.)
            }
          }),
      );
    };

    if (args.length === 0) {
      await refreshClaudeSessions();
      const rows = service.getStatusRows();
      if (jsonFlag) {
        stdout.write(`${JSON.stringify(rows, null, 2)}\n`);
        return 0;
      }
      stdout.write(`${formatStatusRows(rows)}\n`);
      return 0;
    }
    if (args.length !== 1) {
      throw new CdxError("Usage: cdx status [name] [--json]");
    }
    await refreshClaudeSessions();
    const rows = service.getStatusRows();
    const row = rows.find((item) => item.session_name === args[0]);
    if (!row) {
      throw new CdxError(`Unknown session: ${args[0]}`);
    }
    if (jsonFlag) {
      stdout.write(`${JSON.stringify(row, null, 2)}\n`);
      return 0;
    }
    stdout.write(`${formatStatusDetail(row)}\n`);
    return 0;
  }

  if (command === "login") {
    if (rest.length !== 1) {
      throw new CdxError("Usage: cdx login <name>");
    }
    if (!stdin || !stdin.isTTY) {
      throw new CdxError("Login requires an interactive terminal.");
    }
    const session = service.getSession(rest[0]);
    if (!session) {
      throw new CdxError(`Unknown session: ${rest[0]}`);
    }
    await runInteractiveProviderCommand(session, "logout", options);
    await runInteractiveProviderCommand(session, "login", options);
    const now = new Date().toISOString();
    service.updateAuthState(session.name, (auth) => ({
      ...auth,
      status: "authenticated",
      lastCheckedAt: now,
      lastAuthenticatedAt: now,
    }));
    stdout.write(`Reauthenticated session ${session.name} (${session.provider})\n`);
    return 0;
  }

  if (command === "logout") {
    if (rest.length !== 1) {
      throw new CdxError("Usage: cdx logout <name>");
    }
    const session = service.getSession(rest[0]);
    if (!session) {
      throw new CdxError(`Unknown session: ${rest[0]}`);
    }
    await runInteractiveProviderCommand(session, "logout", options);
    const now = new Date().toISOString();
    service.updateAuthState(session.name, (auth) => ({
      ...auth,
      status: "logged_out",
      lastCheckedAt: now,
      lastLoggedOutAt: now,
    }));
    stdout.write(`Logged out session ${session.name} (${session.provider})\n`);
    return 0;
  }

  if (command === "help") {
    stdout.write(`${printHelp()}\n`);
    return 0;
  }

  if (command === "version") {
    stdout.write(`${printVersion()}\n`);
    return 0;
  }

  if (rest.length === 0) {
    const session = service.launchSession(command);
    await ensureSessionAuthentication(session, options, "launch");
    stdout.write(`Launching ${session.provider} session ${session.name}\n`);
    await runInteractiveProviderCommand(session, "launch", options);
    return 0;
  }

  throw new CdxError(`Unknown command: ${command}. Use cdx --help.`);
}

module.exports = {
  main,
  printHelp,
  printVersion,
};
