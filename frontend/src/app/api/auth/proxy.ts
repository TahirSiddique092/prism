import { NextResponse } from "next/server";

import { AUTH_COOKIE, authCookieOptions, getApiBaseUrl } from "@/lib/auth";

/**
 * Proxy a credentials payload to a Flask auth endpoint and, on success, store
 * the returned JWT in an httpOnly cookie.
 *
 * This runs server-side only. The browser posts credentials to our Next route
 * handler; we forward them to Flask, pull the token out of the JSON response,
 * and set it as an httpOnly cookie. The token is therefore never handed to
 * client JavaScript.
 *
 * @param path  Flask auth path, e.g. "/api/auth/login".
 * @param body  Parsed JSON body received from the client form.
 */
export async function proxyAuth(
  path: string,
  body: unknown,
): Promise<NextResponse> {
  let upstream: Response;
  try {
    upstream = await fetch(`${getApiBaseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
  } catch {
    // Backend unreachable — surface a generic message, never internals.
    return NextResponse.json(
      { error: "Unable to reach the authentication service. Try again." },
      { status: 502 },
    );
  }

  const data = await upstream.json().catch(() => ({}));

  if (!upstream.ok) {
    // Forward the backend's (already generic) error message and status.
    const error =
      typeof data?.error === "string" ? data.error : "Authentication failed";
    return NextResponse.json({ error }, { status: upstream.status });
  }

  const token = data?.token;
  if (typeof token !== "string" || !token) {
    return NextResponse.json(
      { error: "Authentication failed" },
      { status: 502 },
    );
  }

  // Success: hand the client only a minimal ack; the JWT stays in the cookie.
  const response = NextResponse.json({ ok: true }, { status: 200 });
  response.cookies.set(AUTH_COOKIE, token, authCookieOptions());
  return response;
}
