import type { NextRequest } from "next/server";
import { proxyBackendGet } from "@/lib/backendGet";

/**
 * GET /api/admin/users (Next route handler, slice-35). Admins only.
 *
 * Upstream response: [{ user_id, name, email, role, created_at, documents, chunks, searches, last_search_at }]
 */
export async function GET(request: NextRequest) {
  return proxyBackendGet(request, "/api/admin/users", "Unable to reach the admin service");
}
