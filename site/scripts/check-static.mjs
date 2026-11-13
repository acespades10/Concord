import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(resolve(root, "index.html"), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
assert.equal(new Set(ids).size, ids.length, "HTML IDs must be unique");
for (const [, url] of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
  if (url.startsWith("https://")) continue;
  if (url.startsWith("#"))
    assert(ids.includes(url.slice(1)), `Missing anchor ${url}`);
  else assert(existsSync(resolve(root, url)), `Missing local file ${url}`);
}
for (const [, id] of html.matchAll(
  /\baria-(?:controls|labelledby)="([^"]+)"/g,
)) {
  assert(ids.includes(id), `Missing accessible reference ${id}`);
}
const evidence = JSON.parse(
  readFileSync(resolve(root, "evidence/results.json"), "utf8"),
);
assert.equal(evidence.status, "passed");
assert.equal(evidence.simulation, true);
assert.equal(evidence.backend_tests_passed, 122);
assert.equal(evidence.export_validation_tests_passed, 53);
assert.equal(evidence.items, 30);
assert.equal(evidence.submissions, 90);
assert.equal(evidence.review.disagreement_items, 10);
assert.equal(evidence.review.unanimous_wrong_items, 5);
assert.equal(evidence.permission_and_workflow_probes.length, 20);
assert(evidence.permission_and_workflow_probes.every((probe) => probe.passed));
for (const name of ["consensus", "annotations"]) {
  const bytes = readFileSync(resolve(root, `evidence/${name}.jsonl`));
  const hash = createHash("sha256").update(bytes).digest("hex");
  assert.equal(hash, evidence.independent_validation.files[name].sha256);
  const rows = bytes.toString("utf8").trimEnd().split("\n").map(JSON.parse);
  assert(rows[0]._manifest);
  assert.equal(rows.length - 1, name === "consensus" ? 30 : 90);
}
const consensus = readFileSync(
  resolve(root, "evidence/consensus.jsonl"),
  "utf8",
)
  .trimEnd()
  .split("\n")
  .map(JSON.parse)
  .find((row) => row.external_id === "sms-00015");
assert(html.includes(consensus.content.prompt));
assert.equal(consensus.payload.label, "ham");
assert.equal(consensus.resolution, "adjudicated");
assert(html.includes("simulated annotations"));
assert(
  !/[A-Z]:\\|token_hash|password_hash|concord_session/.test(
    JSON.stringify(evidence),
  ),
  "Public evidence must omit local paths and credentials",
);
console.log(
  "PASS: local links, accessible references, benchmark claims, original export hashes and public evidence scope.",
);
