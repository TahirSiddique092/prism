import { NextResponse, type NextRequest } from "next/server";

import { AUTH_COOKIE, AUTH_ROUTES } from "@/lib/auth";

/**
 * Edge middleware enforcing the slice-16 auth boundary:
 *
 *  - Unauthenticated users hitting any protected page  → redirected to /login
 *  - Authenticated users hitting /login or /register   → redirected to /dashboard
 *
 * Authentication is determined by the presence of the httpOnly JWT cookie.
 * Signature/expiry verification happens on the backend for every API call;
 * middleware only needs the coarse "is there a session" signal to gate pages.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthenticated = Boolean(request.cookies.get(AUTH_COOKIE)?.value);
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
