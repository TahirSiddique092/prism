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
 * Whether the auth cookie should carry the `Secure` flag.
 *
 * Defaults to on in production, off otherwise — but is overridable via
 * `COOKIE_SECURE` so the local docker-compose stack (served over plain
 * http://localhost) can set `COOKIE_SECURE=false`, otherwise the browser would
 * drop the Secure cookie and logins would silently fail.
 */
function cookieSecure(): boolean {
  const override = process.env.COOKIE_SECURE?.toLowerCase();
  if (override === "true") return true;
  if (override === "false") return false;
  return process.env.NODE_ENV === "production";
}

/**
 * httpOnly cookie options. `secure` is enabled in production (and over real
 * HTTPS) so the JWT is never sent over plaintext; disabled for local http.
 */
export function authCookieOptions() {
  return {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax" as const,
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE,
  };
}
