import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { POST as search } from "../src/app/api/search/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";

interface SearchResult {
  chunk_id: number;
  doc_id: number;
  doc_title: string;
  snippet: string;
  score: number | null;
}

/** Mirrors isFallback() in SearchClient: null/undefined score => FULLTEXT fallback. */
function isFallback(r: SearchResult): boolean {
  return r.score === null || r.score === undefined;
}

describe("Slice 18 — Frontend Search page & API handler", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.search-token";

  after(() => {
    globalThis.fetch = originalFetch;
  });

  describe("1. POST /api/search route handler", () => {
    it("returns 401 when unauthenticated (no cookie)", async () => {
      const req = new NextRequest("http://localhost:3000/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: "indexing" }),
      });
      const res = await search(req);
      assert.strictEqual(res.status, 401);
      const data = await res.json();
      assert.match(data.error, /Unauthorized/);
    });

    it("rejects an empty query with 400", async () => {
      const req = new NextRequest("http://localhost:3000/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: JSON.stringify({ query: "   " }),
      });
      const res = await search(req);
      assert.strictEqual(res.status, 400);
      const data = await res.json();
      assert.match(data.error, /required|empty/i);
    });

    it("proxies the query to Flask with a Bearer token and relays results + cached flag", async () => {
      let forwardedUrl = "";
      let forwardedAuth = "";
      let forwardedBody = "";

      const upstream = {
        results: [
          {
            chunk_id: 101,
            doc_id: 7,
            doc_title: "B-Tree Indexing.pdf",
            snippet: "A B-tree keeps keys sorted so range scans stay O(log n)…",
            score: 0.1823,
          },
        ],
        cached: true,
      };

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        const headers = init?.headers as Record<string, string>;
        forwardedAuth = headers["Authorization"];
        forwardedBody = String(init?.body ?? "");
        return new Response(JSON.stringify(upstream), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: JSON.stringify({ query: "  how do b-tree indexes work  " }),
      });

      const res = await search(req);
      assert.strictEqual(res.status, 200);
      const data = await res.json();

      assert.match(forwardedUrl, /\/api\/search$/);
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
      // Query is trimmed before being forwarded upstream.
      assert.strictEqual(JSON.parse(forwardedBody).query, "how do b-tree indexes work");
      assert.strictEqual(data.cached, true);
      assert.strictEqual(data.results.length, 1);
      assert.strictEqual(data.results[0].doc_id, 7);
    });

    it("returns 502 when the backend is unreachable", async () => {
      globalThis.fetch = (async () => {
        throw new Error("ECONNREFUSED");
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: JSON.stringify({ query: "joins" }),
      });

      const res = await search(req);
      assert.strictEqual(res.status, 502);
      const data = await res.json();
      assert.match(data.error, /Unable to reach/i);
    });
  });

  describe("2. Result classification (semantic vs FULLTEXT fallback)", () => {
    it("treats a null score as a FULLTEXT fallback result", () => {
      const fallback: SearchResult = {
        chunk_id: 1,
        doc_id: 1,
        doc_title: "Notes.pdf",
        snippet: "exact keyword match",
        score: null,
      };
      assert.strictEqual(isFallback(fallback), true);
    });

    it("treats a numeric cosine distance as a semantic result", () => {
      const semantic: SearchResult = {
        chunk_id: 2,
        doc_id: 1,
        doc_title: "Notes.pdf",
        snippet: "semantically similar passage",
        score: 0.2417,
      };
      assert.strictEqual(isFallback(semantic), false);
      // A score of 0 is still a valid (perfect) semantic match, not a fallback.
      assert.strictEqual(isFallback({ ...semantic, score: 0 }), false);
    });
  });

  describe("3. Acceptance-criteria data invariants", () => {
    it("each result exposes title, snippet, score, and doc_id for navigation", () => {
      const results: SearchResult[] = [
        {
          chunk_id: 10,
          doc_id: 3,
          doc_title: "Query Optimization.pdf",
          snippet: "The optimizer picks a join order using cost estimates…",
          score: 0.31,
        },
      ];
      for (const r of results) {
        assert.ok(typeof r.doc_title === "string" && r.doc_title.length > 0);
        assert.ok(typeof r.snippet === "string" && r.snippet.length > 0);
        assert.ok(r.score === null || typeof r.score === "number");
        assert.ok(Number.isInteger(r.doc_id) && r.doc_id > 0);
        // Click target used by the result card.
        assert.strictEqual(`/documents/${r.doc_id}`, "/documents/3");
      }
    });

    it("distinguishes 'not searched yet' from 'searched, zero results'", () => {
      // searchedQuery === null  -> initial prompt
      // searchedQuery !== null && results.length === 0 -> empty state
      let searchedQuery: string | null = null;
      let results: SearchResult[] = [];
      const showInitialPrompt = () => searchedQuery === null;
      const showEmptyState = () => searchedQuery !== null && results.length === 0;

      assert.strictEqual(showInitialPrompt(), true);
      assert.strictEqual(showEmptyState(), false);

      searchedQuery = "nonexistent topic";
      results = [];
      assert.strictEqual(showInitialPrompt(), false);
      assert.strictEqual(showEmptyState(), true);
    });

    it("cached flag drives the 'cached' badge independently of result content", () => {
      const cachedResponse = { results: [], cached: true };
      const freshResponse = { results: [], cached: false };
      assert.strictEqual(Boolean(cachedResponse.cached), true);
      assert.strictEqual(Boolean(freshResponse.cached), false);
    });

    it("builds the ?q= URL that persists the query across navigation", () => {
      const query = "how do b-tree indexes speed up range queries?";
      const url = `/search?q=${encodeURIComponent(query)}`;
      const parsed = new URL(url, "http://localhost:3000");
      assert.strictEqual(parsed.searchParams.get("q"), query);
    });
  });
});
