import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { GET as getDocument } from "../src/app/api/documents/[id]/route.ts";
import { GET as getRelated } from "../src/app/api/documents/[id]/related/route.ts";
import { GET as getViewUrl } from "../src/app/api/documents/[id]/url/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";

describe("Slice 20 — Document Detail API Handlers", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token";

  after(() => {
    globalThis.fetch = originalFetch;
  });

  const ctx = (id: string) => ({ params: Promise.resolve({ id }) });

  describe("GET /api/documents/:id (metadata + topics)", () => {
    it("returns 401 when unauthenticated", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/1", {
        method: "GET",
      });
      const res = await getDocument(req, ctx("1"));
      assert.strictEqual(res.status, 401);
    });

    it("returns 400 for a non-integer id", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/abc", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getDocument(req, ctx("abc"));
      assert.strictEqual(res.status, 400);
    });

    it("proxies to Flask with Bearer token and returns metadata + topics", async () => {
      const upstreamBody = {
        doc_id: 7,
        title: "B-Trees.pdf",
        uploaded_at: "2026-10-10T14:00:00",
        status: "ready",
        chunk_count: 18,
        topics: ["indexing", "b-trees"],
      };

      let forwardedUrl = "";
      let forwardedAuth = "";
      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        forwardedAuth = (init?.headers as Record<string, string>)["Authorization"];
        return new Response(JSON.stringify(upstreamBody), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/7", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getDocument(req, ctx("7"));

      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert.deepStrictEqual(data.topics, ["indexing", "b-trees"]);
      assert.strictEqual(data.chunk_count, 18);
      assert.match(forwardedUrl, /\/api\/documents\/7$/);
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
    });

    it("passes a 404 (doc not owned) straight through", async () => {
      globalThis.fetch = (async () =>
        new Response(JSON.stringify({ error: "Document not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        })) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/999", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getDocument(req, ctx("999"));
      assert.strictEqual(res.status, 404);
    });
  });

  describe("GET /api/documents/:id/related", () => {
    it("returns 401 when unauthenticated", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/1/related", {
        method: "GET",
      });
      const res = await getRelated(req, ctx("1"));
      assert.strictEqual(res.status, 401);
    });

    it("proxies and returns the related list (up to 5)", async () => {
      const related = [
        { doc_id: 2, title: "SQL.pdf", shared_topics: 3 },
        { doc_id: 3, title: "Indexing.pdf", shared_topics: 1 },
      ];
      let forwardedUrl = "";
      globalThis.fetch = (async (url: string | URL | Request) => {
        forwardedUrl = url.toString();
        return new Response(JSON.stringify(related), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/7/related", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getRelated(req, ctx("7"));

      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert.strictEqual(data.length, 2);
      assert.strictEqual(data[0].shared_topics, 3);
      assert.match(forwardedUrl, /\/api\/documents\/7\/related$/);
    });

    it("passes an empty list through as 200 (not an error)", async () => {
      globalThis.fetch = (async () =>
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/7/related", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getRelated(req, ctx("7"));
      assert.strictEqual(res.status, 200);
      assert.deepStrictEqual(await res.json(), []);
    });
  });

  describe("GET /api/documents/:id/url (pre-signed view URL)", () => {
    it("returns 401 when unauthenticated", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/1/url", {
        method: "GET",
      });
      const res = await getViewUrl(req, ctx("1"));
      assert.strictEqual(res.status, 401);
    });

    it("proxies and returns the pre-signed view_url", async () => {
      let forwardedUrl = "";
      globalThis.fetch = (async (url: string | URL | Request) => {
        forwardedUrl = url.toString();
        return new Response(
          JSON.stringify({ view_url: "https://minio.local/bucket/1/abc.pdf?sig=xyz" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/7/url", {
        method: "GET",
        headers: { cookie: `${AUTH_COOKIE}=${mockToken}` },
      });
      const res = await getViewUrl(req, ctx("7"));

      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert.match(data.view_url, /^https:\/\/minio\.local/);
      assert.match(forwardedUrl, /\/api\/documents\/7\/url$/);
    });
  });
});
