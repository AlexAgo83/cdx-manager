"use strict";

const path = require("path");
const { createSessionStore } = require("./session-store");
const { getCdxHome } = require("./config");
const { CdxError } = require("./errors");

const DEFAULT_PROVIDER = "codex";
const ALLOWED_PROVIDERS = new Set(["codex", "claude"]);

function createSessionService(options = {}) {
  const env = options.env || process.env;
  const baseDir = options.baseDir || getCdxHome(env);
  const store = options.store || createSessionStore(baseDir);

  function normalizeProvider(provider) {
    const value = provider || DEFAULT_PROVIDER;
    if (!ALLOWED_PROVIDERS.has(value)) {
      throw new CdxError(`Unsupported provider: ${value}`);
    }
    return value;
  }

  function createSession(name, provider = DEFAULT_PROVIDER) {
    if (!name) {
      throw new CdxError("Session name is required");
    }
    const normalizedProvider = normalizeProvider(provider);
    const session = {
      name,
      provider: normalizedProvider,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      lastStatus: null,
    };
    const result = store.addSession(session);
    if (!result.ok) {
      throw new CdxError(`Session already exists: ${name}`);
    }
    return result.session;
  }

  function removeSession(name) {
    const removed = store.removeSession(name);
    if (!removed) {
      throw new CdxError(`Unknown session: ${name}`);
    }
    return removed;
  }

  function launchSession(name) {
    const session = store.getSession(name);
    if (!session) {
      throw new CdxError(`Unknown session: ${name}`);
    }
    const state = store.readSessionState(name);
    if (!state) {
      throw new CdxError(`Session state missing for ${name}. Reconnect required.`);
    }
    store.writeSessionState(name, {
      ...state,
      rehydratedAt: new Date().toISOString(),
    });
    return {
      ...session,
      state: store.readSessionState(name),
    };
  }

  function listSessions() {
    return store.listSessions();
  }

  function getSession(name) {
    return store.getSession(name);
  }

  function recordStatus(name, payload) {
    const updated = store.updateSession(name, (session) => ({
      ...session,
      lastStatus: {
        ...payload,
      },
      updatedAt: new Date().toISOString(),
    }));
    if (!updated) {
      throw new CdxError(`Unknown session: ${name}`);
    }
    return updated;
  }

  function formatListRows() {
    const sessions = listSessions();
    const hasMultipleProviders = new Set(sessions.map((session) => session.provider)).size > 1;
    return sessions.map((session) => ({
      name: session.name,
      provider: hasMultipleProviders ? session.provider : undefined,
      status: session.lastStatus,
      updatedAt: session.updatedAt,
    }));
  }

  return {
    createSession,
    formatListRows,
    getSession,
    launchSession,
    listSessions,
    normalizeProvider,
    recordStatus,
    removeSession,
  };
}

module.exports = {
  ALLOWED_PROVIDERS,
  DEFAULT_PROVIDER,
  createSessionService,
};
