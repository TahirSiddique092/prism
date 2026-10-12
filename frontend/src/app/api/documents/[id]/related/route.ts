import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * GET /api/documents/:id/related (Next route handler)
 *
 * Proxies the related-documents lookup to Flask with JWT authentication.
 * Upstream response: [{ doc_id, title, shared_topics }] — up to 5, or [] when
 * none exist. A 404 (doc missing or not owned) is passed straight through.
 */
export async function GET(request: NextRequest, context: RouteContext) {
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
    const upstream = await fetch(
      `${getApiBaseUrl()}/api/documents/${docId}/related`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    const data = await upstream.json().catch(() => []);
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach documents service" },
      { status: 502 }
    );
  }
}
