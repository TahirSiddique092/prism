import { NextRequest } from "next/server";

import { proxyAuth } from "../proxy";

/**
 * POST /api/auth/login (Next route handler)
 *
 * Forwards { email, password } to the Flask backend and, on success, stores
 * the returned JWT in an httpOnly cookie. Failures return a generic error that
 * does not reveal whether the email or the password was wrong.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  return proxyAuth("/api/auth/login", body);
}
