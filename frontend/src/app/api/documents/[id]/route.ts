import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * GET /api/documents/:id (Next route handler)
 *
 * Proxies the document-detail request to Flask with JWT authentication.
 * Upstream response: { doc_id, title, uploaded_at, status, chunk_count, topics }.
 * A 404 from Flask (doc missing or not owned) is passed straight through so the
 * page can render its not-found state.
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
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/${docId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
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

/**
 * DELETE /api/documents/:id (Next route handler)
 *
 * Proxies document deletion to Flask with JWT authentication.
 * Deletes document from MySQL, pgvector, MinIO, and invalidates Redis cache.
 */
export async function DELETE(request: NextRequest, context: RouteContext) {
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
    return NextResponse.json(
      { error: "Invalid document ID" },
      { status: 400 }
    );
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/${docId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach documents deletion service" },
      { status: 502 }
    );
  }
}
