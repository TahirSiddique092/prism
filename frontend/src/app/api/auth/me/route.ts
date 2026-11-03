import type { NextRequest } from "next/server";
import { proxyBackendGet } from "@/lib/backendGet";

/**
 * GET /api/auth/me (Next route handler, slice-35)
 *
 * The signed-in user's profile. Upstream response: { user_id, name, email, role }
 */
export async function GET(request: NextRequest) {
  return proxyBackendGet(request, "/api/auth/me", "Unable to reach the authentication service");
}
