#!/usr/bin/env node
/**
 * Simple helper that increments the extension's patch version
 * whenever `npm run package` is executed.
 */

const fs = require("node:fs");
const path = require("node:path");

function bumpVersion(input) {
  const segments = input.split(".");
  while (segments.length < 3) {
    segments.push("0");
  }
  const patchIndex = segments.length - 1;
  const currentPatch = Number.parseInt(segments[patchIndex], 10);
  const nextPatch = Number.isFinite(currentPatch) ? currentPatch + 1 : 0;
  segments[patchIndex] = String(nextPatch);
  return segments.join(".");
}

function main() {
  const packagePath = path.resolve(__dirname, "..", "package.json");
  const raw = fs.readFileSync(packagePath, "utf8");
  const pkg = JSON.parse(raw);
  const previous = typeof pkg.version === "string" ? pkg.version : "0.0.0";
  const next = bumpVersion(previous);
  pkg.version = next;
  fs.writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`, "utf8");
  console.log(`[hsx-debug] bumped extension version: ${previous} -> ${next}`);
}

main();
