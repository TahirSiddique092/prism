import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatSimilarity, SIMILARITY_TOOLTIP } from "../src/lib/scores.ts";

describe("Slice 25 — one score scale", () => {
  it("shows a cosine distance as similarity (1 − distance)", () => {
    // The same stored distance shows the same number on Search and Top Documents
    assert.strictEqual(formatSimilarity(0.4634), "0.5366");
    assert.strictEqual(formatSimilarity(0.3844), "0.6156");
  });

  it("returns null when there is no score (FULLTEXT results)", () => {
    assert.strictEqual(formatSimilarity(null), null);
    assert.strictEqual(formatSimilarity(undefined), null);
    assert.strictEqual(formatSimilarity(Number.NaN), null);
  });

  it("labels the scale so higher means closer", () => {
    assert.match(SIMILARITY_TOOLTIP, /similarity/i);
    assert.match(SIMILARITY_TOOLTIP, /higher is closer/);
  });
});
