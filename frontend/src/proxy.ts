import { NextResponse, type NextRequest } from "next/server";

import { AUTH_COOKIE, AUTH_ROUTES } from "@/lib/auth";

/**
 * Edge middleware enforcing the slice-16 auth boundary:
 *
 *  - Unauthenticated users hitting any protected page  → redirected to /login
 *  - Authenticated users hitting /login or /register   → redirected to /dashboard
 *
 * Authentication is determined by the presence of a JWT cookie whose `exp`
 * claim is still in the future. The signature is still verified on the backend
 * for every API call — middleware only parses `exp` (no secret needed) so that
 * an expired-but-present cookie is treated as signed-out. Without this, an
 * expired session leaves the user stranded on a protected page that silently
 * fails every backend call instead of being sent to /login.
 */
function hasActiveSession(token: string | undefined): boolean {
  if (!token) return false;
  // Reject ONLY when we can positively prove the token is an expired JWT. For
  // anything we cannot parse (or that carries no exp claim) we fall back to the
  // slice-16 presence-based signal — the backend still verifies the signature
  // on every API call.
  const parts = token.split(".");
  if (parts.length === 3) {
    try {
      let b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      b64 += "=".repeat((4 - (b64.length % 4)) % 4);
      const payload = JSON.parse(atob(b64)) as { exp?: number };
      if (typeof payload.exp === "number" && payload.exp * 1000 <= Date.now()) {
        return false;
      }
    } catch {
      // Not a parseable JWT payload — fall through to presence-based auth.
    }
  }
  return true;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthenticated = hasActiveSession(request.cookies.get(AUTH_COOKIE)?.value);
  const isAuthRoute = AUTH_ROUTES.includes(pathname);

  // Signed-in users should never see the login/register screens.
  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Everything the matcher lets through (and isn't an auth route) is protected.
  if (!isAuthRoute && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  /*
   * Run on all paths except Next internals, the auth API routes (which set the
   * cookie), and static/asset files. The `/` root is included so visiting it
   * while signed out lands on /login.
   */
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
