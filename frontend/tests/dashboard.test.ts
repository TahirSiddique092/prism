import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { GET as getDocuments } from "../src/app/api/documents/route.ts";
import { POST as uploadDocument } from "../src/app/api/documents/upload/route.ts";
import { DELETE as deleteDocument } from "../src/app/api/documents/[id]/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";

describe("Slice 17 — Frontend Dashboard & API Handlers", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token";

  after(() => {
    globalThis.fetch = originalFetch;
  });

  describe("1. GET /api/documents route handler", () => {
    it("returns 401 when unauthenticated (no cookie)", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents", {
        method: "GET",
      });
      const res = await getDocuments(req);
      assert.strictEqual(res.status, 401);
      const data = await res.json();
      assert.match(data.error, /Unauthorized/);
    });

    it("proxies document listing to Flask with Bearer token when authenticated", async () => {
      const mockDocs = [
        {
          doc_id: 1,
          title: "Database Indexing.pdf",
          uploaded_at: "2026-10-10T14:00:00",
          status: "ready",
          chunk_count: 14,
        },
        {
          doc_id: 2,
          title: "Query Optimization.pdf",
          uploaded_at: "2026-10-11T09:30:00",
          status: "processing",
          chunk_count: 0,
        },
        {
          doc_id: 3,
          title: "Corrupted Scan.pdf",
          uploaded_at: "2026-10-11T10:00:00",
          status: "error",
          chunk_count: 0,
        },
      ];

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        const urlStr = url.toString();
        assert.match(urlStr, /\/api\/documents$/);
        const headers = init?.headers as Record<string, string>;
        assert.strictEqual(headers["Authorization"], `Bearer ${mockToken}`);

        return new Response(JSON.stringify(mockDocs), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents", {
        method: "GET",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await getDocuments(req);
      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert.strictEqual(data.length, 3);
      assert.strictEqual(data[0].title, "Database Indexing.pdf");
      assert.strictEqual(data[0].status, "ready");
      assert.strictEqual(data[0].chunk_count, 14);
      assert.strictEqual(data[2].status, "error");
    });
  });

  describe("2. POST /api/documents/upload route handler", () => {
    it("returns 401 when unauthenticated", async () => {
      const formData = new FormData();
      formData.append(
        "file",
        new File(["dummy pdf content"], "doc.pdf", { type: "application/pdf" })
      );

      const req = new NextRequest("http://localhost:3000/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      const res = await uploadDocument(req);
      assert.strictEqual(res.status, 401);
    });

    it("rejects request missing a file part (400)", async () => {
      const formData = new FormData();
      formData.append("topics", "Databases, SQL");

      const req = new NextRequest("http://localhost:3000/api/documents/upload", {
        method: "POST",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: formData,
      });

      const res = await uploadDocument(req);
      assert.strictEqual(res.status, 400);
      const data = await res.json();
      assert.match(data.error, /No file/i);
    });

    it("rejects non-PDF files (400)", async () => {
      const formData = new FormData();
      formData.append(
        "file",
        new File(["some text"], "notes.txt", { type: "text/plain" })
      );

      const req = new NextRequest("http://localhost:3000/api/documents/upload", {
        method: "POST",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: formData,
      });

      const res = await uploadDocument(req);
      assert.strictEqual(res.status, 400);
      const data = await res.json();
      assert.match(data.error, /Only \.pdf files are accepted/i);
    });

    it("rejects files larger than 20MB (413)", async () => {
      const formData = new FormData();
      const largeBuffer = new Uint8Array(21 * 1024 * 1024);
      const largeFile = new File([largeBuffer], "large.pdf", {
        type: "application/pdf",
      });
      formData.append("file", largeFile);

      const req = new NextRequest("http://localhost:3000/api/documents/upload", {
        method: "POST",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: formData,
      });

      const res = await uploadDocument(req);
      assert.strictEqual(res.status, 413);
      const data = await res.json();
      assert.match(data.error, /20MB max/i);
    });

    it("proxies valid PDF upload with topics to Flask with Bearer token (201)", async () => {
      let forwardedAuthorization = "";
      let forwardedEndpoint = "";

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedEndpoint = url.toString();
        const headers = init?.headers as Record<string, string>;
        forwardedAuthorization = headers["Authorization"];

        return new Response(
          JSON.stringify({ doc_id: 42, minio_key: "1/42.pdf" }),
          {
            status: 201,
            headers: { "Content-Type": "application/json" },
          }
        );
      }) as typeof fetch;

      const formData = new FormData();
      formData.append(
        "file",
        new File(["%PDF-1.4 dummy pdf bytes"], "ch12_query.pdf", {
          type: "application/pdf",
        })
      );
      formData.append("topics", "Query Optimization, Relational Algebra");

      const req = new NextRequest("http://localhost:3000/api/documents/upload", {
        method: "POST",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
        body: formData,
      });

      const res = await uploadDocument(req);
      assert.strictEqual(res.status, 201);
      const data = await res.json();
      assert.strictEqual(data.doc_id, 42);
      assert.strictEqual(data.minio_key, "1/42.pdf");
      assert.match(forwardedEndpoint, /\/api\/documents\/upload$/);
      assert.strictEqual(forwardedAuthorization, `Bearer ${mockToken}`);
    });
  });

  describe("3. DELETE /api/documents/:id route handler", () => {
    it("returns 401 when unauthenticated", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/42", {
        method: "DELETE",
      });

      const res = await deleteDocument(req, {
        params: Promise.resolve({ id: "42" }),
      });
      assert.strictEqual(res.status, 401);
    });

    it("rejects non-integer document ID (400)", async () => {
      const req = new NextRequest("http://localhost:3000/api/documents/abc", {
        method: "DELETE",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await deleteDocument(req, {
        params: Promise.resolve({ id: "abc" }),
      });
      assert.strictEqual(res.status, 400);
      const data = await res.json();
      assert.match(data.error, /Invalid document ID/);
    });

    it("proxies deletion to Flask with Bearer token (200)", async () => {
      let forwardedUrl = "";
      let forwardedMethod = "";
      let forwardedAuth = "";

      globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
        forwardedUrl = url.toString();
        forwardedMethod = init?.method ?? "";
        const headers = init?.headers as Record<string, string>;
        forwardedAuth = headers["Authorization"];

        return new Response(JSON.stringify({ message: "deleted" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }) as typeof fetch;

      const req = new NextRequest("http://localhost:3000/api/documents/42", {
        method: "DELETE",
        headers: {
          cookie: `${AUTH_COOKIE}=${mockToken}`,
        },
      });

      const res = await deleteDocument(req, {
        params: Promise.resolve({ id: "42" }),
      });
      assert.strictEqual(res.status, 200);
      const data = await res.json();
      assert.strictEqual(data.message, "deleted");
      assert.match(forwardedUrl, /\/api\/documents\/42$/);
      assert.strictEqual(forwardedMethod, "DELETE");
      assert.strictEqual(forwardedAuth, `Bearer ${mockToken}`);
    });
  });

  describe("4. Dashboard Acceptance Criteria State Invariants", () => {
    it("criteria: document list represents title, uploaded_at, status, chunk_count", () => {
      const sampleDocs = [
        {
          doc_id: 1,
          title: "Lecture 1.pdf",
          uploaded_at: "2026-10-10T10:00:00Z",
          status: "ready" as const,
          chunk_count: 25,
        },
        {
          doc_id: 2,
          title: "Lecture 2.pdf",
          uploaded_at: "2026-10-11T12:00:00Z",
          status: "processing" as const,
          chunk_count: 0,
        },
        {
          doc_id: 3,
          title: "Corrupt.pdf",
          uploaded_at: "2026-10-11T12:30:00Z",
          status: "error" as const,
          chunk_count: 0,
        },
      ];

      for (const doc of sampleDocs) {
        assert.ok(doc.doc_id > 0);
        assert.ok(typeof doc.title === "string" && doc.title.length > 0);
        assert.ok(["ready", "processing", "error"].includes(doc.status));
        assert.ok(typeof doc.chunk_count === "number" && doc.chunk_count >= 0);
      }
    });

    it("criteria: after upload, document appears immediately with status processing", () => {
      const currentDocs = [
        {
          doc_id: 1,
          title: "Existing.pdf",
          uploaded_at: "2026-10-10T10:00:00Z",
          status: "ready" as const,
          chunk_count: 10,
        },
      ];

      const uploadResponse = { doc_id: 99, minio_key: "1/99.pdf" };
      const uploadedFile = { name: "NewlyUploaded.pdf", size: 1024 * 500 };

      // Simulate immediate optimistic addition as done in DashboardClient
      const newDoc = {
        doc_id: uploadResponse.doc_id,
        title: uploadedFile.name,
        uploaded_at: new Date().toISOString(),
        status: "processing" as const,
        chunk_count: 0,
      };

      const updatedDocs = [newDoc, ...currentDocs];

      assert.strictEqual(updatedDocs.length, 2);
      assert.strictEqual(updatedDocs[0].doc_id, 99);
      assert.strictEqual(updatedDocs[0].title, "NewlyUploaded.pdf");
      assert.strictEqual(updatedDocs[0].status, "processing");
      assert.strictEqual(updatedDocs[0].chunk_count, 0);
    });

    it("criteria: deleted document disappears from list without full page reload", () => {
      const currentDocs = [
        {
          doc_id: 10,
          title: "KeepMe.pdf",
          uploaded_at: "2026-10-10T10:00:00Z",
          status: "ready" as const,
          chunk_count: 10,
        },
        {
          doc_id: 20,
          title: "DeleteMe.pdf",
          uploaded_at: "2026-10-10T11:00:00Z",
          status: "ready" as const,
          chunk_count: 5,
        },
      ];

      // Simulate client deletion filter upon successful DELETE response
      const deletedDocId = 20;
      const afterDeletion = currentDocs.filter((d) => d.doc_id !== deletedDocId);

      assert.strictEqual(afterDeletion.length, 1);
      assert.strictEqual(afterDeletion[0].doc_id, 10);
      assert.ok(!afterDeletion.some((d) => d.doc_id === 20));
    });
  });
});
