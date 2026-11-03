import { NextResponse, type NextRequest } from "next/server";

import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

/**
 * Proxy a GET to a Flask endpoint, attaching the JWT from the httpOnly cookie
 * (slice-35). The upstream status and JSON body are passed through unchanged,
 * so a 403 "Admins only" reaches the page as a 403.
 *
 * @param path         Flask path, e.g. "/api/admin/users".
 * @param unreachable  Error message when Flask can't be reached.
 */
export async function proxyBackendGet(
  request: NextRequest,
  path: string,
  unreachable: string,
): Promise<NextResponse> {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 },
    );
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}${path}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: unreachable }, { status: 502 });
  }
}
