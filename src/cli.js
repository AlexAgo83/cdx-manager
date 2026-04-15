"use strict";

const { spawn } = require("child_process");
const readline = require("readline");
const { createSessionService } = require("./session-service");
const { CdxError } = require("./errors");

const VERSION = "0.1.0";

function printHelp() {
  return [
    "cdx - terminal session manager",
    "",
    "Usage:",
    "  cdx",
    "  cdx status [name]",
    "  cdx add [provider] <name>",
    "  cdx rmv <name> [--force]",
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
    ? ["SESSION", "PROVIDER", "USAGE", "5H LEFT", "WEEK LEFT", "UPDATED"]
    : ["SESSION", "USAGE", "5H LEFT", "WEEK LEFT", "UPDATED"];
  if (rows.length === 0) {
    return ["SESSION  USAGE  5H LEFT  WEEK LEFT  UPDATED", "No saved sessions yet."].join("\n");
  }
  const tableRows = rows.map((row) => {
    const base = [row.session_name];
    if (hasProvider) {
      base.push(row.provider || "n/a");
    }
    base.push(
      formatPct(row.usage_pct),
      formatPct(row.remaining_5h_pct),
      formatPct(row.remaining_week_pct),
      formatRelativeAge(row.updated_at),
    );
    return base;
  });
  return [padTable([headers, ...tableRows])].join("\n");
}

function formatStatusDetail(row) {
  const lines = [
    `Session: ${row.session_name}`,
    `Provider: ${row.provider || "n/a"}`,
    `Usage: ${formatPct(row.usage_pct)}`,
    `5h left: ${formatPct(row.remaining_5h_pct)}`,
    `Week left: ${formatPct(row.remaining_week_pct)}`,
    `Updated: ${formatRelativeAge(row.updated_at)}`,
    "",
  ];
  if (row.raw_status_text) {
    lines.push("Raw last /status:");
    lines.push(row.raw_status_text);
  } else {
    lines.push("Raw last /status: none");
  }
  return lines.join("\n");
}

function launchCodexInteractive(session, options = {}) {
  const spawnFn = options.spawn || spawn;
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  const cwd = options.cwd || process.cwd();
  const child = spawnFn(
    "codex",
    ["--no-alt-screen", "--cd", cwd],
    {
      stdio: "inherit",
      env: {
        ...process.env,
        ...(options.env || {}),
        CODEX_HOME: session.codexHome,
      },
    },
  );

  return new Promise((resolve, reject) => {
    child.on("error", (error) => {
      reject(new CdxError(`Failed to launch Codex for ${session.name}: ${error.message}`));
    });
    child.on("close", (code) => {
      if (code === 0) {
        resolve(code);
        return;
      }
      reject(new CdxError(`Codex exited with code ${code} for session ${session.name}`));
    });
  });
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
    service.createSession(name, provider);
    stdout.write(`Created session ${name} (${provider})\n`);
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
    if (rest.length === 0) {
      stdout.write(`${formatStatusRows(service.getStatusRows())}\n`);
      return 0;
    }
    if (rest.length !== 1) {
      throw new CdxError("Usage: cdx status [name]");
    }
    const rows = service.getStatusRows();
    const row = rows.find((item) => item.session_name === rest[0]);
    if (!row) {
      throw new CdxError(`Unknown session: ${rest[0]}`);
    }
    stdout.write(`${formatStatusDetail(row)}\n`);
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
    stdout.write(`Launching ${session.provider} session ${session.name}\n`);
    await launchCodexInteractive(session, options);
    return 0;
  }

  throw new CdxError(`Unknown command: ${command}. Use cdx --help.`);
}

module.exports = {
  main,
  printHelp,
  printVersion,
};
