import type { NextRequest } from "next/server";
import { proxyBackendGet } from "@/lib/backendGet";

/**
 * GET /api/admin/deletions (Next route handler, slice-35). Admins only.
 *
 * Upstream response: [{ audit_id, doc_id, title, user_id, deleted_at }], newest first
 */
export async function GET(request: NextRequest) {
  return proxyBackendGet(request, "/api/admin/deletions", "Unable to reach the admin service");
}
