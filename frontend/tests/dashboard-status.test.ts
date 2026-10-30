import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { POST as retryDocument } from "../src/app/api/documents/[id]/retry/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";
import { STATUS_POLL_MS, hasProcessing, markRetrying } from "../src/lib/documents.ts";

const DOCS = [
  { doc_id: 1, title: "a.pdf", status: "ready", chunk_count: 43 },
  { doc_id: 2, title: "b.pdf", status: "error", chunk_count: 0 },
];

describe("Slice 28 — dashboard status", () => {
  it("polls every 3 seconds, only while something is processing", () => {
    assert.strictEqual(STATUS_POLL_MS, 3000);
    assert.strictEqual(hasProcessing(DOCS), false);
    assert.strictEqual(hasProcessing([...DOCS, { doc_id: 3, title: "c.pdf", status: "processing", chunk_count: 0 }]), true);
    assert.strictEqual(hasProcessing([]), false);
  });

  it("shows a retried document as processing with no chunks, leaving the others alone", () => {
    const after = markRetrying(DOCS, 2);
    assert.deepStrictEqual(after[1], { doc_id: 2, title: "b.pdf", status: "processing", chunk_count: 0 });
    assert.strictEqual(after[0], DOCS[0]);
    assert.strictEqual(hasProcessing(after), true);
  });
});

describe("Slice 28 — POST /api/documents/:id/retry", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token";
  const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
  const request = (id: string, withCookie = true) =>
    new NextRequest(`http://localhost:3000/api/documents/${id}/retry`, {
      method: "POST",
      headers: withCookie ? { cookie: `${AUTH_COOKIE}=${mockToken}` } : {},
    });

  after(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns 401 without a session and 400 for a non-numeric id", async () => {
    assert.strictEqual((await retryDocument(request("2", false), ctx("2"))).status, 401);
    assert.strictEqual((await retryDocument(request("x"), ctx("x"))).status, 400);
  });

  it("forwards the retry to Flask with the Bearer token and relays 202", async () => {
    let forwarded = "";
    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      forwarded = `${init?.method} ${url} ${(init?.headers as Record<string, string>)["Authorization"]}`;
      return new Response(JSON.stringify({ doc_id: 2, status: "processing" }), { status: 202 });
    }) as typeof fetch;

    const res = await retryDocument(request("2"), ctx("2"));

    assert.strictEqual(res.status, 202);
    assert.deepStrictEqual(await res.json(), { doc_id: 2, status: "processing" });
    assert.match(forwarded, /^POST .*\/api\/documents\/2\/retry Bearer /);
  });

  it("passes 409 and 404 through, and returns 502 when Flask is unreachable", async () => {
    for (const status of [409, 404]) {
      globalThis.fetch = (async () => new Response(JSON.stringify({ error: "nope" }), { status })) as typeof fetch;
      assert.strictEqual((await retryDocument(request("2"), ctx("2"))).status, status);
    }
    globalThis.fetch = (async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof fetch;
    assert.strictEqual((await retryDocument(request("2"), ctx("2"))).status, 502);
  });
});
