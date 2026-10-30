import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { GET as getChunk } from "../src/app/api/documents/[id]/chunks/[chunkId]/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";
import {
  findPassageItems,
  normalizeForMatch,
  pagePosition,
  parsePassageParams,
  passageHref,
} from "../src/lib/passage.ts";

const params = (query: string) => new URLSearchParams(query);

describe("Slice 27 — links to a passage", () => {
  it("search results link to the document with the chunk and page", () => {
    assert.strictEqual(passageHref(4, 42, 12), "/documents/4?chunk=42&page=12");
    assert.strictEqual(passageHref(4, 42, null), "/documents/4?chunk=42");
    assert.strictEqual(passageHref(4, 42), "/documents/4?chunk=42");
  });

  it("reads the passage from the document URL", () => {
    assert.deepStrictEqual(parsePassageParams(params("chunk=42&page=12")), { chunkId: 42, page: 12 });
    assert.deepStrictEqual(parsePassageParams(params("chunk=42")), { chunkId: 42, page: null });
    assert.deepStrictEqual(parsePassageParams(params("chunk=42&page=abc")), { chunkId: 42, page: null });
    assert.strictEqual(parsePassageParams(params("")), null);
    assert.strictEqual(parsePassageParams(params("chunk=0")), null);
    assert.strictEqual(parsePassageParams(params("chunk=-3")), null);
  });

  it("places a page within the passage", () => {
    assert.strictEqual(pagePosition(5, 5, 5), "only");
    assert.strictEqual(pagePosition(5, 5, 7), "start");
    assert.strictEqual(pagePosition(6, 5, 7), "middle");
    assert.strictEqual(pagePosition(7, 5, 7), "end");
    assert.strictEqual(pagePosition(4, 5, 7), null);
    assert.strictEqual(pagePosition(8, 5, 7), null);
  });
});

describe("Slice 27 — finding the passage in a page's text items", () => {
  const SLIDE = [
    "Database Management Systems",
    "Weak Entity",
    "• A weak entity set is one whose",
    "existence depends on another",
    "entity, called its identifying entity.",
    "Next: Mapping cardinalities",
    "55",
  ];

  it("ignores spacing, line breaks and bullets when comparing text", () => {
    assert.strictEqual(normalizeForMatch("• A weak\n entity—set!"), "aweakentityset");
    assert.strictEqual(normalizeForMatch("ﬁle"), "file"); // ligature
  });

  it("highlights a passage that starts and ends on the page", () => {
    const passage = "A weak entity set is one whose existence depends on another entity, called its identifying entity.";
    assert.deepStrictEqual(findPassageItems(SLIDE, passage, "only"), [2, 3, 4]);
  });

  it("highlights from the passage start to the page end when it continues on the next page", () => {
    const passage = "Weak Entity\n• A weak entity set is one whose existence depends on another entity, called its identifying entity. Next: Mapping cardinalities 55 Database Management Systems One-to-one…";
    assert.deepStrictEqual(findPassageItems(SLIDE, passage, "start"), [1, 2, 3, 4, 5, 6]);
  });

  it("finds a passage that starts with the last few characters of a page", () => {
    // Real case: a chunk starting with "C\nQ & A\n54" at the bottom of slide 54
    const page = ["ANSWERS:", "1.", "A", "2.", "B", "8.", "C", "Q & A", "54"];
    const passage = "C\nQ & A\n54\n Database Management Systems\n• A weak entity is one whose existence is dependent";
    assert.deepStrictEqual(findPassageItems(page, passage, "start"), [6, 7, 8]);
  });

  it("highlights from the page top to the passage end when it began on the previous page", () => {
    const passage = "…a strong entity set. Database Management Systems Weak Entity • A weak entity set is one whose existence depends on another";
    assert.deepStrictEqual(findPassageItems(SLIDE, passage, "end"), [0, 1, 2, 3]);
  });

  it("highlights the whole page when the passage runs through it", () => {
    assert.deepStrictEqual(findPassageItems(SLIDE, "anything at all", "middle"), [0, 1, 2, 3, 4, 5, 6]);
  });

  it("still finds the passage if its first characters differ from the page", () => {
    // Extraction differences at the very start: try a little further in
    const passage = "XQ7Z9W2K3 A weak entity set is one whose existence depends on another entity, called its identifying entity.";
    const items = findPassageItems(SLIDE, passage, "only");
    assert.ok(items && items.includes(2) && items.includes(4));
  });

  it("returns null when the passage isn't on the page", () => {
    assert.strictEqual(findPassageItems(SLIDE, "Functional dependencies and normal forms are covered in unit three of the course.", "only"), null);
    assert.strictEqual(findPassageItems(SLIDE, "Functional dependencies and normal forms are covered in unit three.", "start"), null);
    assert.strictEqual(findPassageItems([], "anything", "middle"), null);
    assert.strictEqual(findPassageItems(SLIDE, "  •  ", "only"), null);
  });
});

describe("Slice 27 — GET /api/documents/:id/chunks/:chunkId", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token";
  const ctx = (id: string, chunkId: string) => ({ params: Promise.resolve({ id, chunkId }) });
  const request = (path: string, withCookie = true) =>
    new NextRequest(`http://localhost:3000${path}`, {
      method: "GET",
      headers: withCookie ? { cookie: `${AUTH_COOKIE}=${mockToken}` } : {},
    });

  after(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns 401 without a session and 400 for non-numeric ids", async () => {
    assert.strictEqual((await getChunk(request("/api/documents/7/chunks/42", false), ctx("7", "42"))).status, 401);
    assert.strictEqual((await getChunk(request("/api/documents/x/chunks/42"), ctx("x", "42"))).status, 400);
    assert.strictEqual((await getChunk(request("/api/documents/7/chunks/y"), ctx("7", "y"))).status, 400);
  });

  it("proxies to Flask with the Bearer token and relays the passage", async () => {
    const passage = { chunk_id: 42, chunk_text: "Weak entities…", page_start: 12, page_end: 13 };
    let forwarded = "";
    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      forwarded = `${url} ${(init?.headers as Record<string, string>)["Authorization"]}`;
      return new Response(JSON.stringify(passage), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    const res = await getChunk(request("/api/documents/7/chunks/42"), ctx("7", "42"));

    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(await res.json(), passage);
    assert.match(forwarded, /\/api\/documents\/7\/chunks\/42 Bearer /);
  });

  it("passes a 404 through and returns 502 when Flask is unreachable", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ error: "Passage not found" }), { status: 404 })) as typeof fetch;
    assert.strictEqual((await getChunk(request("/api/documents/7/chunks/42"), ctx("7", "42"))).status, 404);

    globalThis.fetch = (async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof fetch;
    assert.strictEqual((await getChunk(request("/api/documents/7/chunks/42"), ctx("7", "42"))).status, 502);
  });
});
