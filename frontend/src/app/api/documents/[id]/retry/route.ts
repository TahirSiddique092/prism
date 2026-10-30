import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * POST /api/documents/:id/retry (Next route handler, slice-28)
 *
 * Proxies a retry of a failed document to Flask with JWT auth. Upstream
 * responses are passed through: 202 { doc_id, status: "processing" }, 404 if
 * the document isn't the user's, 409 if it isn't in the error state.
 */
export async function POST(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "Unauthorized — missing session token" },
      { status: 401 }
    );
  }

  const { id } = await context.params;
  const docId = parseInt(id, 10);
  if (isNaN(docId)) {
    return NextResponse.json({ error: "Invalid document ID" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/${docId}/retry`, {
      method: "POST",
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
