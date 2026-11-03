import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { NextRequest } from "next/server.js";
import { GET as getMe } from "../src/app/api/auth/me/route.ts";
import { GET as getAdminUsers } from "../src/app/api/admin/users/route.ts";
import { GET as getAdminStats } from "../src/app/api/admin/stats/route.ts";
import { GET as getAdminDeletions } from "../src/app/api/admin/deletions/route.ts";
import { proxy } from "../src/proxy.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";
import {
  ADMINS_ONLY_MESSAGE,
  STAT_TILES,
  isAdmin,
  loadAdminData,
  type SystemStats,
} from "../src/lib/admin.ts";

const TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.admin-token";

function withCookie(path: string) {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: { cookie: `${AUTH_COOKIE}=${TOKEN}` },
  });
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const STATS: SystemStats = {
  users: 3,
  admins: 1,
  documents: 5,
  documents_processing: 1,
  documents_ready: 3,
  documents_error: 1,
  chunks: 120,
  searches: 42,
  searches_today: 4,
  deletions: 2,
};

describe("slice-35 — admin role (frontend)", () => {
  const originalFetch = globalThis.fetch;
  after(() => {
    globalThis.fetch = originalFetch;
  });

  const proxies = [
    { name: "/api/auth/me", handler: getMe, upstream: "/api/auth/me" },
    { name: "/api/admin/users", handler: getAdminUsers, upstream: "/api/admin/users" },
    { name: "/api/admin/stats", handler: getAdminStats, upstream: "/api/admin/stats" },
    { name: "/api/admin/deletions", handler: getAdminDeletions, upstream: "/api/admin/deletions" },
  ];

  for (const { name, handler, upstream } of proxies) {
    describe(`GET ${name} proxy`, () => {
      it("returns 401 without a session cookie, without calling Flask", async () => {
        let called = false;
        globalThis.fetch = (async () => {
          called = true;
          return jsonResponse({});
        }) as typeof fetch;
        const res = await handler(new NextRequest(`http://localhost:3000${name}`));
        assert.strictEqual(res.status, 401);
        assert.strictEqual(called, false);
      });

      it("forwards the cookie's JWT as a Bearer token to the Flask route", async () => {
        let seenUrl = "";
        let seenAuth: string | null = null;
        globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
          seenUrl = String(url);
          seenAuth = new Headers(init?.headers).get("Authorization");
          return jsonResponse({ ok: true });
        }) as typeof fetch;
        const res = await handler(withCookie(name));
        assert.strictEqual(res.status, 200);
        assert.ok(seenUrl.endsWith(upstream), seenUrl);
        assert.strictEqual(seenAuth, `Bearer ${TOKEN}`);
      });

      it("passes a 403 from Flask through unchanged", async () => {
        globalThis.fetch = (async () => jsonResponse({ error: "Admins only" }, 403)) as typeof fetch;
        const res = await handler(withCookie(name));
        assert.strictEqual(res.status, 403);
        assert.deepStrictEqual(await res.json(), { error: "Admins only" });
      });

      it("returns 502 when Flask can't be reached", async () => {
        globalThis.fetch = (async () => {
          throw new Error("ECONNREFUSED");
        }) as typeof fetch;
        const res = await handler(withCookie(name));
        assert.strictEqual(res.status, 502);
      });
    });
  }

  describe("isAdmin", () => {
    it("is true only for role = admin", () => {
      assert.strictEqual(isAdmin({ user_id: 1, name: "A", email: "a@x", role: "admin" }), true);
      assert.strictEqual(isAdmin({ user_id: 2, name: "B", email: "b@x", role: "user" }), false);
      assert.strictEqual(isAdmin({ error: "Unauthorized" }), false);
      assert.strictEqual(isAdmin(null), false);
      assert.strictEqual(isAdmin(undefined), false);
    });
  });

  describe("Admin link in the header", () => {
    it("is rendered only behind the isAdmin(/api/auth/me) check", () => {
      const source = readFileSync(new URL("../src/components/AppHeader.tsx", import.meta.url), "utf8");
      assert.match(source, /fetch\("\/api\/auth\/me"\)/);
      assert.match(source, /setShowAdmin\(isAdmin\(me\)\)/);
      assert.match(source, /\{showAdmin && \(\s*<Link\s+href="\/admin"/);
    });
  });

  describe("loadAdminData", () => {
    const ok = {
      "/api/admin/users": [
        { user_id: 1, name: "A", email: "a@x", role: "admin", created_at: null,
          documents: 2, chunks: 40, searches: 7, last_search_at: null },
      ],
      "/api/admin/stats": STATS,
      "/api/admin/deletions": [
        { audit_id: 9, doc_id: 12, title: "old.pdf", user_id: 1, deleted_at: "2026-11-03T10:00:00Z" },
      ],
    };

    function fakeFetch(statusFor: Record<string, number> = {}) {
      return (async (url: string | URL | Request) => {
        const path = String(url) as keyof typeof ok;
        const status = statusFor[path] ?? 200;
        return jsonResponse(status === 200 ? ok[path] : { error: "nope" }, status);
      }) as typeof fetch;
    }

    it("returns the three sections for an admin", async () => {
      const result = await loadAdminData(fakeFetch());
      assert.strictEqual(result.status, "ok");
      if (result.status !== "ok") return;
      assert.deepStrictEqual(result.data.users, ok["/api/admin/users"]);
      assert.deepStrictEqual(result.data.stats, STATS);
      assert.deepStrictEqual(result.data.deletions, ok["/api/admin/deletions"]);
    });

    it("says forbidden when the backend answers 403 (a user, not an admin)", async () => {
      const result = await loadAdminData(fakeFetch({
        "/api/admin/users": 403, "/api/admin/stats": 403, "/api/admin/deletions": 403,
      }));
      assert.deepStrictEqual(result, { status: "forbidden" });
      assert.strictEqual(ADMINS_ONLY_MESSAGE, "Admins only");
    });

    it("says unauthorized on a 401, so the page sends the viewer to /login", async () => {
      const result = await loadAdminData(fakeFetch({ "/api/admin/stats": 401 }));
      assert.deepStrictEqual(result, { status: "unauthorized" });
    });

    it("reports the backend's error message on any other failure", async () => {
      const result = await loadAdminData(fakeFetch({ "/api/admin/deletions": 500 }));
      assert.deepStrictEqual(result, { status: "error", message: "nope" });
    });

    it("reports a network failure as an error", async () => {
      const result = await loadAdminData((async () => {
        throw new Error("offline");
      }) as typeof fetch);
      assert.deepStrictEqual(result, { status: "error", message: "offline" });
    });
  });

  describe("System stats tiles", () => {
    it("show every total the backend returns, once each", () => {
      const keys = STAT_TILES.map((tile) => tile.key).sort();
      assert.deepStrictEqual(keys, Object.keys(STATS).sort());
    });
  });

  describe("/admin page guard", () => {
    it("redirects a signed-out visitor to /login", () => {
      const res = proxy(new NextRequest("http://localhost:3000/admin"));
      assert.strictEqual(res.status, 307);
      assert.strictEqual(res.headers.get("location"), "http://localhost:3000/login");
    });
  });
});
