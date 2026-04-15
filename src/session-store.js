"use strict";

const fs = require("fs");
const path = require("path");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    if (error && error.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

function writeJson(filePath, value) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function createSessionStore(baseDir) {
  const storeFile = path.join(baseDir, "sessions.json");
  const stateDir = path.join(baseDir, "state");

  function stateFilePath(name) {
    return path.join(stateDir, `${encodeURIComponent(name)}.json`);
  }

  function load() {
    const data = readJson(storeFile, { version: 1, sessions: [] });
    if (!data.sessions) {
      data.sessions = [];
    }
    return data;
  }

  function save(data) {
    writeJson(storeFile, data);
  }

  function readSessionState(name) {
    return readJson(stateFilePath(name), null);
  }

  function writeSessionState(name, state) {
    writeJson(stateFilePath(name), state);
  }

  function removeSessionState(name) {
    try {
      fs.unlinkSync(stateFilePath(name));
    } catch (error) {
      if (!error || error.code !== "ENOENT") {
        throw error;
      }
    }
  }

  function listSessions() {
    return load().sessions.slice().sort((left, right) => {
      return left.name.localeCompare(right.name);
    });
  }

  function getSession(name) {
    return load().sessions.find((session) => session.name === name) || null;
  }

  function addSession(session) {
    const data = load();
    if (data.sessions.some((item) => item.name === session.name)) {
      return { ok: false, reason: "duplicate" };
    }
    data.sessions.push(session);
    save(data);
    writeSessionState(session.name, {
      provider: session.provider,
      status: "ready",
      rehydratedAt: null,
    });
    return { ok: true, session };
  }

  function updateSession(name, updater) {
    const data = load();
    const index = data.sessions.findIndex((session) => session.name === name);
    if (index === -1) {
      return null;
    }
    const nextSession = updater(data.sessions[index]);
    data.sessions[index] = nextSession;
    save(data);
    return nextSession;
  }

  function removeSession(name) {
    const data = load();
    const index = data.sessions.findIndex((session) => session.name === name);
    if (index === -1) {
      return null;
    }
    const [removed] = data.sessions.splice(index, 1);
    save(data);
    removeSessionState(name);
    return removed;
  }

  function hasSessionState(name) {
    return readSessionState(name) !== null;
  }

  return {
    addSession,
    getSession,
    listSessions,
    hasSessionState,
    readSessionState,
    removeSession,
    removeSessionState,
    updateSession,
    writeSessionState,
  };
}

module.exports = {
  createSessionStore,
};
