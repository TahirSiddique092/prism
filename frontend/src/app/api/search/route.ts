import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

/**
 * POST /api/search (Next route handler)
 *
 * Proxies a plain-English search query to Flask, attaching the JWT from the
 * httpOnly cookie. The backend embeds the query, runs pgvector similarity
 * search (with MySQL FULLTEXT fallback) scoped to the authenticated user, and
 * returns:
 *   { results: [{ chunk_id, doc_id, doc_title, snippet, score }], cached }
 * where `score` is the raw cosine distance (lower = closer) or `null` when the
 * FULLTEXT fallback produced the result.
 */
export async function POST(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 }
    );
  }

  const body = await request.json().catch(() => null);
  const query = body && typeof body.query === "string" ? body.query.trim() : "";
  if (!query) {
    return NextResponse.json(
      { error: "Query string is required and cannot be empty" },
      { status: 400 }
    );
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/search`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
      cache: "no-store",
    });

    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach search service" },
      { status: 502 }
    );
  }
}
