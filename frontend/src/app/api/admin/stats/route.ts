import type { NextRequest } from "next/server";
import { proxyBackendGet } from "@/lib/backendGet";

/**
 * GET /api/admin/stats (Next route handler, slice-35). Admins only.
 *
 * Upstream response: { users, admins, documents, documents_processing, documents_ready,
 * documents_error, chunks, searches, searches_today, deletions }
 */
export async function GET(request: NextRequest) {
  return proxyBackendGet(request, "/api/admin/stats", "Unable to reach the admin service");
}
