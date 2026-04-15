"use strict";

class CdxError extends Error {
  constructor(message, code = 1) {
    super(message);
    this.name = "CdxError";
    this.code = code;
  }
}

module.exports = {
  CdxError,
};
