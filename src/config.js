"use strict";

const os = require("os");
const path = require("path");

function getCdxHome(env = process.env) {
  return env.CDX_HOME || path.join(os.homedir(), ".cdx");
}

module.exports = {
  getCdxHome,
};
