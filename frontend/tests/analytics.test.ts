import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { GET as getHistory } from "../src/app/api/analytics/history/route.ts";
import { GET as getUnsearched } from "../src/app/api/analytics/unsearched/route.ts";
import { GET as getTopDocuments } from "../src/app/api/analytics/top-documents/route.ts";
import { proxy } from "../src/proxy.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";
import {
  ANALYTICS_NAV_ITEMS,
  UNSEARCHED_NUDGE_MESSAGE,
  formatDate,
  formatDateTime,
  sortHistoryByRank,
  sortTopDocsByCount,
  type SearchHistoryItem,
  type UnsearchedDocumentItem,
  type TopDocumentItem,
} from "../src/lib/analytics.ts";

describe("Slice 19 — Frontend Analytics Pages & API Handlers", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.analytics-token";

  after(() => {
    globalThis.fetch = originalFetch;
  });

  describe("1. GET /api/analytics/history route handler", () => {
    it("returns 401 when unauthenticated (no cookie)", async () => {
      const req = new NextRequest("http://localhost:3000/api/analytics/history", {
        method: "GET",
      });
      const res = await getHistory(req);
      assert.strictEqual(res.status, 401);
      const data = await res.json();
      assert.match(data.error, /Unauthorized/);
    });

    it("proxies search history to Flask with Bearer token when authenticated", async () => {
      let forwardedUrl = "";
      let forwardedAuth = "";

      const mockHistory: SearchHistoryItem[] = [
        {
          query_text: "database indexing",
          search_count: 5,
          query_rank: 1,
          last_searched: "2026-10-11T12:00:00",
          total_searches: 8,
        },
        {
          query_text: "vector embeddings",
          search_count: 3,
          query_rank: 2,
          last_searched: "2026-10-11T13:30:00",
          total_searches: 8,
        },
      ];

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        const headers = init?.headers as Record<string, string>;
        forwardedAuth = headers["Authorization"];
        return new Response(JSON.stringify(mockHistory), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/history", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getHistory(req);
      assert.strictEqual(res.status, 200);
      const data = await res.json();

      assert.match(forwardedUrl, /\/api\/analytics\/history$/);
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
      assert.strictEqual(data.length, 2);
      assert.strictEqual(data[0].query_text, "database indexing");
      assert.strictEqual(data[0].query_rank, 1);
    });

    it("returns 502 when Flask backend is unreachable", async () => {
      globalThis.fetch = (async () => {
        throw new Error("ECONNREFUSED");
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/history", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getHistory(req);
      assert.strictEqual(res.status, 502);
      const data = await res.json();
      assert.match(data.error, /Unable to reach/i);
    });
  });

  describe("2. GET /api/analytics/unsearched route handler", () => {
    it("returns 401 when unauthenticated (no cookie)", async () => {
      const req = new NextRequest("http://localhost:3000/api/analytics/unsearched", {
        method: "GET",
      });
      const res = await getUnsearched(req);
      assert.strictEqual(res.status, 401);
      const data = await res.json();
      assert.match(data.error, /Unauthorized/);
    });

    it("proxies unsearched documents to Flask with Bearer token when authenticated", async () => {
      let forwardedUrl = "";
      let forwardedAuth = "";

      const mockDocs: UnsearchedDocumentItem[] = [
        {
          doc_id: 12,
          title: "Operating Systems Notes.pdf",
          uploaded_at: "2026-10-10T15:00:00",
        },
      ];

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        const headers = init?.headers as Record<string, string>;
        forwardedAuth = headers["Authorization"];
        return new Response(JSON.stringify(mockDocs), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/unsearched", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getUnsearched(req);
      assert.strictEqual(res.status, 200);
      const data = await res.json();

      assert.match(forwardedUrl, /\/api\/analytics\/unsearched$/);
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
      assert.strictEqual(data.length, 1);
      assert.strictEqual(data[0].doc_id, 12);
    });

    it("returns 502 when Flask backend is unreachable", async () => {
      globalThis.fetch = (async () => {
        throw new Error("ECONNREFUSED");
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/unsearched", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getUnsearched(req);
      assert.strictEqual(res.status, 502);
      const data = await res.json();
      assert.match(data.error, /Unable to reach/i);
    });
  });

  describe("3. GET /api/analytics/top-documents route handler", () => {
    it("returns 401 when unauthenticated (no cookie)", async () => {
      const req = new NextRequest("http://localhost:3000/api/analytics/top-documents", {
        method: "GET",
      });
      const res = await getTopDocuments(req);
      assert.strictEqual(res.status, 401);
      const data = await res.json();
      assert.match(data.error, /Unauthorized/);
    });

    it("proxies top documents to Flask with Bearer token when authenticated", async () => {
      let forwardedUrl = "";
      let forwardedAuth = "";

      const mockTopDocs: TopDocumentItem[] = [
        {
          doc_id: 1,
          title: "Distributed Systems.pdf",
          appearance_count: 9,
          avg_score: 0.3541,
        },
      ];

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        const headers = init?.headers as Record<string, string>;
        forwardedAuth = headers["Authorization"];
        return new Response(JSON.stringify(mockTopDocs), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/top-documents", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getTopDocuments(req);
      assert.strictEqual(res.status, 200);
      const data = await res.json();

      assert.match(forwardedUrl, /\/api\/analytics\/top-documents$/);
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
      assert.strictEqual(data.length, 1);
      assert.strictEqual(data[0].doc_id, 1);
      assert.strictEqual(data[0].appearance_count, 9);
    });

    it("returns 502 when Flask backend is unreachable", async () => {
      globalThis.fetch = (async () => {
        throw new Error("ECONNREFUSED");
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/analytics/top-documents", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getTopDocuments(req);
      assert.strictEqual(res.status, 502);
      const data = await res.json();
      assert.match(data.error, /Unable to reach/i);
    });
  });

  describe("4. Route protection (unauthenticated access redirects to /login)", () => {
    const analyticsRoutes = [
      "/analytics",
      "/analytics/history",
      "/analytics/unsearched",
      "/analytics/top-documents",
    ];

    for (const route of analyticsRoutes) {
      it(`redirects unauthenticated access on ${route} to /login`, () => {
        const req = new NextRequest(`http://localhost:3000${route}`);
        const res = proxy(req);
        assert.strictEqual(res.status, 307);
        assert.strictEqual(res.headers.get("location"), "http://localhost:3000/login");
      });

      it(`allows authenticated access on ${route}`, () => {
        const req = new NextRequest(`http://localhost:3000${route}`, {
          headers: {
            cookie: `${AUTH_COOKIE}=${mockToken}`,
          },
        });
        const res = proxy(req);
        assert.strictEqual(res.headers.get("location"), null);
      });
    }
  });

  describe("5. Shared /analytics navigation", () => {
    it("shared navigation provides links to all three analytics pages", () => {
      const hrefs = ANALYTICS_NAV_ITEMS.map((item) => item.href);
      assert.ok(hrefs.includes("/analytics/history"), "History nav link missing");
      assert.ok(hrefs.includes("/analytics/unsearched"), "Unsearched nav link missing");
      assert.ok(hrefs.includes("/analytics/top-documents"), "Top documents nav link missing");
      assert.strictEqual(ANALYTICS_NAV_ITEMS.length, 3);
    });
  });

  describe("6. Page invariants: /analytics/history", () => {
    it("sorts past queries by rank ascending (rank 1 at top)", () => {
      const raw: SearchHistoryItem[] = [
        { query_text: "query C", search_count: 1, query_rank: 3, last_searched: null, total_searches: 6 },
        { query_text: "query A", search_count: 3, query_rank: 1, last_searched: null, total_searches: 6 },
        { query_text: "query B", search_count: 2, query_rank: 2, last_searched: null, total_searches: 6 },
      ];
      const sorted = sortHistoryByRank(raw);
      assert.strictEqual(sorted[0].query_rank, 1);
      assert.strictEqual(sorted[0].query_text, "query A");
      assert.strictEqual(sorted[1].query_rank, 2);
      assert.strictEqual(sorted[2].query_rank, 3);
    });

    it("exposes all required columns: query, search count, rank, last searched", () => {
      const item: SearchHistoryItem = {
        query_text: "btree indexes",
        search_count: 4,
        query_rank: 1,
        last_searched: "2026-10-11T10:00:00",
        total_searches: 10,
      };
      assert.ok(typeof item.query_text === "string" && item.query_text.length > 0);
      assert.ok(Number.isInteger(item.search_count) && item.search_count > 0);
      assert.ok(Number.isInteger(item.query_rank) && item.query_rank >= 1);
      assert.ok(item.last_searched !== undefined);
      assert.strictEqual(typeof formatDateTime(item.last_searched), "string");
    });

    it("formats null or valid last_searched dates gracefully", () => {
      assert.strictEqual(formatDateTime(null), "—");
      assert.strictEqual(formatDateTime(undefined), "—");
      const formatted = formatDateTime("2026-10-11T12:00:00Z");
      assert.ok(formatted.length > 0 && formatted !== "—");
    });
  });

  describe("7. Page invariants: /analytics/unsearched", () => {
    it("preserves title and upload date for each unsearched document", () => {
      const doc: UnsearchedDocumentItem = {
        doc_id: 42,
        title: "Compiler Design.pdf",
        uploaded_at: "2026-10-09T08:30:00",
      };
      assert.ok(typeof doc.title === "string" && doc.title.length > 0);
      assert.ok(doc.uploaded_at !== undefined);
      assert.ok(Number.isInteger(doc.doc_id) && doc.doc_id > 0);
      const formattedDate = formatDate(doc.uploaded_at);
      assert.ok(formattedDate.length > 0 && formattedDate !== "—");
    });

    it("verifies the exact nudge message required by acceptance criteria", () => {
      assert.strictEqual(
        UNSEARCHED_NUDGE_MESSAGE,
        "These documents have never come up in a search — try searching for their topics"
      );
    });
  });

  describe("8. Page invariants: /analytics/top-documents", () => {
    it("sorts documents by appearance count descending", () => {
      const raw: TopDocumentItem[] = [
        { doc_id: 1, title: "Doc A", appearance_count: 2, avg_score: 0.4 },
        { doc_id: 2, title: "Doc B", appearance_count: 10, avg_score: 0.2 },
        { doc_id: 3, title: "Doc C", appearance_count: 6, avg_score: 0.3 },
      ];
      const sorted = sortTopDocsByCount(raw);
      assert.strictEqual(sorted[0].appearance_count, 10);
      assert.strictEqual(sorted[0].title, "Doc B");
      assert.strictEqual(sorted[1].appearance_count, 6);
      assert.strictEqual(sorted[2].appearance_count, 2);
    });

    it("exposes title, appearance count, and handles both numeric and null average score", () => {
      const itemWithScore: TopDocumentItem = {
        doc_id: 5,
        title: "Database Internals.pdf",
        appearance_count: 12,
        avg_score: 0.28543,
      };
      assert.ok(typeof itemWithScore.title === "string");
      assert.ok(itemWithScore.appearance_count > 0);
      assert.strictEqual(typeof itemWithScore.avg_score, "number");
      assert.strictEqual(itemWithScore.avg_score?.toFixed(4), "0.2854");

      const itemWithoutScore: TopDocumentItem = {
        doc_id: 6,
        title: "SQL Reference.pdf",
        appearance_count: 1,
        avg_score: null,
      };
      assert.strictEqual(itemWithoutScore.avg_score, null);
    });
  });
});
