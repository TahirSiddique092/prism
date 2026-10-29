import { NextResponse, type NextRequest } from "next/server";
import { AUTH_COOKIE, getApiBaseUrl } from "@/lib/auth";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * GET /api/documents/:id/open (Next route handler, slice-26)
 *
 * Opens the PDF itself: fetches a fresh pre-signed URL from Flask and
 * redirects to it. The viewer's "Open in new tab" button is a plain link to
 * this route, so the tab always gets a URL that hasn't expired, and no popup
 * blocker is involved. This is a page navigation rather than a fetch, so
 * errors come back as short text and a missing or expired session goes to
 * /login.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (!token) {
    return redirectToLogin();
  }

  const { id } = await context.params;
  const docId = parseInt(id, 10);
  if (isNaN(docId)) {
    return new NextResponse("Invalid document ID", { status: 400 });
  }

  try {
    const upstream = await fetch(`${getApiBaseUrl()}/api/documents/${docId}/url`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (upstream.status === 401) {
      return redirectToLogin();
    }
    if (upstream.status === 404) {
      return new NextResponse("Document not found", { status: 404 });
    }

    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok || typeof data?.view_url !== "string") {
      return new NextResponse("Unable to open the document", { status: 502 });
    }
    return NextResponse.redirect(data.view_url);
  } catch {
    return new NextResponse("Unable to reach documents service", { status: 502 });
  }
}

/**
 * Relative redirect to /login. In the standalone server, request.url carries
 * the bind address (http://0.0.0.0:3000), not the host the browser used, so
 * an absolute URL built from it would send the user nowhere.
 */
function redirectToLogin() {
  return new NextResponse(null, { status: 307, headers: { Location: "/login" } });
}
