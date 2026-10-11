import { NextRequest } from "next/server";

import { proxyAuth } from "../proxy";

/**
 * POST /api/auth/register (Next route handler)
 *
 * Forwards { name, email, password } to the Flask backend and, on success,
 * stores the returned JWT in an httpOnly cookie, logging the new user straight
 * in.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  return proxyAuth("/api/auth/register", body);
}
