import { NextResponse } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth";

/**
 * POST /api/auth/logout (Next route handler)
 *
 * Clears the httpOnly auth cookie. The backend JWT is stateless, so logout is
 * purely a matter of discarding the client's token.
 */
export async function POST() {
  const response = NextResponse.json({ ok: true }, { status: 200 });
  response.cookies.delete(AUTH_COOKIE);
  return response;
}
