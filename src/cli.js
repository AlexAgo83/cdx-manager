"use strict";

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
      stdout.write("SESSION  USAGE  5H LEFT  WEEK LEFT  UPDATED\n");
      for (const session of service.listSessions()) {
        const status = session.lastStatus || {};
        stdout.write(
          [
            session.name,
            status.usagePct !== undefined ? `${status.usagePct}%` : "n/a",
            status.remaining5hPct !== undefined ? `${status.remaining5hPct}%` : "n/a",
            status.remainingWeekPct !== undefined ? `${status.remainingWeekPct}%` : "n/a",
            session.updatedAt || "-",
          ].join("  ") + "\n",
        );
      }
      return 0;
    }
    if (rest.length !== 1) {
      throw new CdxError("Usage: cdx status [name]");
    }
    const session = service.getSession(rest[0]);
    if (!session) {
      throw new CdxError(`Unknown session: ${rest[0]}`);
    }
    stdout.write(`Session: ${session.name}\nProvider: ${session.provider}\n`);
    const status = session.lastStatus || {};
    stdout.write(`Usage: ${status.usagePct !== undefined ? `${status.usagePct}%` : "n/a"}\n`);
    stdout.write(`5h left: ${status.remaining5hPct !== undefined ? `${status.remaining5hPct}%` : "n/a"}\n`);
    stdout.write(`Week left: ${status.remainingWeekPct !== undefined ? `${status.remainingWeekPct}%` : "n/a"}\n`);
    stdout.write(`Updated: ${session.updatedAt || "-"}\n`);
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
    return 0;
  }

  throw new CdxError(`Unknown command: ${command}. Use cdx --help.`);
}

module.exports = {
  main,
  printHelp,
  printVersion,
};
