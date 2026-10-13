/**
 * Shared auth constants and helpers for the PRISM frontend (slice-16).
 *
 * The JWT is issued by the Flask backend and stored in an httpOnly cookie that
 * only server code (route handlers + middleware) can read or write — it is
 * never exposed to client JavaScript or localStorage.
 */

/** Name of the httpOnly cookie that holds the backend-issued JWT. */
export const AUTH_COOKIE = "prism_token";

/** Backend token lifetime is 24h (see backend/modules/auth/service.py). */
export const AUTH_COOKIE_MAX_AGE = 60 * 60 * 24;

/** Routes that must NOT be accessible to an already-authenticated user. */
export const AUTH_ROUTES = ["/login", "/register"];

/**
 * Base URL of the Flask API.
 *
 * getApiBaseUrl() is only ever called from server code (route handlers + server
 * components), so we prefer a server-only runtime variable (`API_URL`): it is
 * not inlined into the client bundle and can be changed in the host dashboard
 * without a rebuild. We fall back to the build-time public `NEXT_PUBLIC_API_URL`
 * (for backwards-compatibility and local dev), then to the local dev backend.
 */
export function getApiBaseUrl(): string {
  return (
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:5000"
  );
}

/**
 * httpOnly cookie options. `secure` is only enabled in production so the cookie
 * still works over plain http://localhost during development.
 */
export function authCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE,
  };
}
