import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { NextRequest } from "next/server.js";
import { proxy } from "../src/proxy.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";

/** Build an unsigned JWT-shaped string with the given exp (seconds since epoch). */
function jwtWithExp(expSeconds: number): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({ user_id: 1, exp: expSeconds })).toString("base64url");
  return `${header}.${payload}.sig`;
}

describe("proxy session handling (M6 — expired tokens)", () => {
  it("redirects to /login when the JWT is expired, even though the cookie is present", () => {
    const expired = jwtWithExp(Math.floor(Date.now() / 1000) - 60);
    const req = new NextRequest("http://localhost:3000/dashboard", {
      headers: { cookie: `${AUTH_COOKIE}=${expired}` },
    });
    const res = proxy(req);
    assert.strictEqual(res.status, 307);
    assert.strictEqual(res.headers.get("location"), "http://localhost:3000/login");
  });

  it("does NOT bounce an expired session away from /login (no redirect loop)", () => {
    const expired = jwtWithExp(Math.floor(Date.now() / 1000) - 60);
    const req = new NextRequest("http://localhost:3000/login", {
      headers: { cookie: `${AUTH_COOKIE}=${expired}` },
    });
    const res = proxy(req);
    // Expired => treated as signed-out => allowed to stay on /login.
    assert.strictEqual(res.headers.get("location"), null);
  });

  it("allows a JWT whose exp is still in the future", () => {
    const valid = jwtWithExp(Math.floor(Date.now() / 1000) + 3600);
    const req = new NextRequest("http://localhost:3000/dashboard", {
      headers: { cookie: `${AUTH_COOKIE}=${valid}` },
    });
    const res = proxy(req);
    assert.strictEqual(res.headers.get("location"), null);
  });
});
