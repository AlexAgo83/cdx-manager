"use strict";

const fs = require("fs");
const https = require("https");
const path = require("path");

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function readClaudeCredentials(authHome) {
  const credPath = path.join(authHome, ".claude", ".credentials.json");
  try {
    const parsed = JSON.parse(fs.readFileSync(credPath, "utf8"));
    return parsed.claudeAiOauth || null;
  } catch {
    return null;
  }
}

function formatResetDate(unixSeconds) {
  const date = new Date(unixSeconds * 1000);
  return `${MONTH_ABBR[date.getMonth()]} ${date.getDate()}`;
}

function fetchClaudeRateLimitHeaders(accessToken) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1,
      messages: [{ role: "user", content: "hi" }],
    });

    const req = https.request(
      {
        hostname: "api.anthropic.com",
        path: "/v1/messages",
        method: "POST",
        headers: {
          "x-api-key": accessToken,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
          "content-length": Buffer.byteLength(body),
        },
      },
      (res) => {
        res.on("data", () => {});
        res.on("end", () => {
          const util5h = res.headers["anthropic-ratelimit-unified-5h-utilization"];
          const reset5h = res.headers["anthropic-ratelimit-unified-5h-reset"];
          const util7d = res.headers["anthropic-ratelimit-unified-7d-utilization"];
          const reset7d = res.headers["anthropic-ratelimit-unified-7d-reset"];

          if (util5h === undefined && util7d === undefined) {
            resolve(null);
            return;
          }

          const utilization5h = util5h !== undefined ? Number(util5h) : null;
          const utilization7d = util7d !== undefined ? Number(util7d) : null;
          const resetAt = reset7d
            ? formatResetDate(Number(reset7d))
            : reset5h
              ? formatResetDate(Number(reset5h))
              : null;

          resolve({
            remaining5hPct: utilization5h !== null ? Math.round((1 - utilization5h) * 100) : null,
            remainingWeekPct: utilization7d !== null ? Math.round((1 - utilization7d) * 100) : null,
            resetAt,
            updatedAt: new Date().toISOString(),
            rawStatusText: null,
            sourceRef: "api:anthropic-ratelimit-headers",
          });
        });
      },
    );

    req.on("error", reject);
    req.setTimeout(10000, () => req.destroy(new Error("Request timed out")));
    req.write(body);
    req.end();
  });
}

async function refreshClaudeSessionStatus(session) {
  const creds = readClaudeCredentials(session.authHome);
  if (!creds || !creds.accessToken) {
    return null;
  }
  return fetchClaudeRateLimitHeaders(creds.accessToken);
}

module.exports = { refreshClaudeSessionStatus };
