import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

/**
 * GET /api/analytics/unsearched (Next route handler)
 *
 * Proxies unsearched documents request to Flask, attaching the JWT from the httpOnly cookie.
 * Upstream response: [{ doc_id, title, uploaded_at }]
 */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 }
    );
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/analytics/unsearched`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    const data = await upstream.json().catch(() => []);
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach analytics service" },
      { status: 502 }
    );
  }
}
