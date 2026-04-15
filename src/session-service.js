"use strict";

const { createSessionStore } = require("./session-store");
const { getCdxHome } = require("./config");
const { CdxError } = require("./errors");

const DEFAULT_PROVIDER = "codex";
const ALLOWED_PROVIDERS = new Set(["codex", "claude"]);

function normalizeStatusPayload(payload = {}) {
  const now = new Date().toISOString();
  return {
    usagePct: payload.usagePct ?? null,
    remaining5hPct: payload.remaining5hPct ?? null,
    remainingWeekPct: payload.remainingWeekPct ?? null,
    updatedAt: payload.updatedAt || payload.capturedAt || now,
    rawStatusText: payload.rawStatusText ?? null,
    sourceRef: payload.sourceRef ?? null,
  };
}

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
      lastLaunchedAt: null,
      lastStatusAt: null,
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
    const rehydratedAt = new Date().toISOString();
    store.writeSessionState(name, {
      ...state,
      rehydratedAt,
    });
    return store.updateSession(name, (current) => ({
      ...current,
      updatedAt: rehydratedAt,
      lastLaunchedAt: rehydratedAt,
    }));
  }

  function listSessions() {
    return store.listSessions();
  }

  function getSession(name) {
    return store.getSession(name);
  }

  function recordStatus(name, payload) {
    const normalizedStatus = normalizeStatusPayload(payload);
    const updated = store.updateSession(name, (session) => ({
      ...session,
      lastStatus: normalizedStatus,
      lastStatusAt: normalizedStatus.updatedAt,
    }));
    if (!updated) {
      throw new CdxError(`Unknown session: ${name}`);
    }
    return updated;
  }

  function getStatusRows() {
    const sessions = listSessions();
    return sessions
      .slice()
      .sort((left, right) => {
        const leftStatusAt = left.lastStatusAt || "";
        const rightStatusAt = right.lastStatusAt || "";
        if (leftStatusAt && rightStatusAt) {
          return rightStatusAt.localeCompare(leftStatusAt);
        }
        if (leftStatusAt) {
          return -1;
        }
        if (rightStatusAt) {
          return 1;
        }
        return left.name.localeCompare(right.name);
      })
      .map((session) => ({
        session_name: session.name,
        provider: session.provider,
        usage_pct: session.lastStatus ? session.lastStatus.usagePct : null,
        remaining_5h_pct: session.lastStatus ? session.lastStatus.remaining5hPct : null,
        remaining_week_pct: session.lastStatus ? session.lastStatus.remainingWeekPct : null,
        updated_at: session.lastStatusAt || null,
        raw_status_text: session.lastStatus ? session.lastStatus.rawStatusText : null,
        source_ref: session.lastStatus ? session.lastStatus.sourceRef : null,
      }));
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
    getStatusRows,
  };
}

module.exports = {
  ALLOWED_PROVIDERS,
  DEFAULT_PROVIDER,
  createSessionService,
  normalizeStatusPayload,
};
