import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

interface RouteContext {
  params: Promise<{ id: string; chunkId: string }>;
}

/**
 * GET /api/documents/:id/chunks/:chunkId (Next route handler, slice-27)
 *
 * Proxies to Flask with JWT auth. Upstream response:
 * { chunk_id, chunk_text, page_start, page_end }. Used by the document page
 * to open a search result at its passage. A 404 (not this user's document,
 * or not a chunk of it) is passed straight through.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 }
    );
  }

  const { id, chunkId } = await context.params;
  const docId = parseInt(id, 10);
  const chunk = parseInt(chunkId, 10);
  if (isNaN(docId) || isNaN(chunk)) {
    return NextResponse.json({ error: "Invalid document or passage ID" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/${docId}/chunks/${chunk}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach documents service" },
      { status: 502 }
    );
  }
}
