"use strict";

const fs = require("fs");
const path = require("path");
const { createSessionService } = require("./session-service");
const { CdxError } = require("./errors");
const { getCdxHome } = require("./config");

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

function formatSessions(service) {
  const rows = service.formatListRows();
  const hasProvider = rows.some((row) => row.provider);
  const headers = ["SESSION"];
  if (hasProvider) {
    headers.push("PROVIDER");
  }
  headers.push("UPDATED");
  const lines = [headers.join("  ")];
  for (const row of rows) {
    const parts = [row.name];
    if (hasProvider) {
      parts.push(row.provider || "n/a");
    }
    parts.push(row.updatedAt || "-");
    lines.push(parts.join("  "));
  }
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

async function main(argv, options = {}) {
  const env = options.env || process.env;
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  const service = options.service || createSessionService({ env });

  if (argv.includes("--help") || argv.includes("-h")) {
    stdout.write(`${printHelp()}\n`);
    return 0;
  }

  if (argv.includes("--version") || argv.includes("-v")) {
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
    const forceIndex = rest.indexOf("--force");
    const name = rest.find((item) => item !== "--force");
    if (!name) {
      throw new CdxError("Usage: cdx rmv <name> [--force]");
    }
    if (forceIndex === -1) {
      throw new CdxError("Removal confirmation is not implemented yet. Use --force.");
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
            status.usagePct ? `${status.usagePct}%` : "n/a",
            status.remaining5hPct ? `${status.remaining5hPct}%` : "n/a",
            status.remainingWeekPct ? `${status.remainingWeekPct}%` : "n/a",
            session.updatedAt || "-",
          ].join("  ") + "\n",
        );
      }
      return 0;
    }
    const session = service.getSession(rest[0]);
    if (!session) {
      throw new CdxError(`Unknown session: ${rest[0]}`);
    }
    stdout.write(`Session: ${session.name}\nProvider: ${session.provider}\n`);
    const status = session.lastStatus || {};
    stdout.write(`Usage: ${status.usagePct ? `${status.usagePct}%` : "n/a"}\n`);
    stdout.write(`5h left: ${status.remaining5hPct ? `${status.remaining5hPct}%` : "n/a"}\n`);
    stdout.write(`Week left: ${status.remainingWeekPct ? `${status.remainingWeekPct}%` : "n/a"}\n`);
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

  throw new CdxError(printHelp());
}

module.exports = {
  main,
  printHelp,
  printVersion,
};
