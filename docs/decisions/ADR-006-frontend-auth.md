# ADR-006 — Frontend auth & httpOnly JWT storage (slice-16)

## Context

slice-16 adds the `/login` and `/register` pages. The acceptance criteria
require the backend-issued JWT to be stored in an **httpOnly** cookie (not
localStorage) and the whole app to be gated: unauthenticated users are sent to
`/login`, already-authenticated users never see `/login` or `/register`.

The Flask backend returns the JWT in the JSON response body
(`{ user_id, token }`). An httpOnly cookie, by definition, cannot be set from
client JavaScript — so the token cannot simply be read from the fetch response
and written to `document.cookie`.

## Decisions

- **Server-side proxy route handlers set the cookie.** The client forms POST
  credentials to Next route handlers (`/api/auth/login`, `/api/auth/register`),
  which run server-side, forward the payload to Flask, pull `token` out of the
  response, and set it as an httpOnly cookie via `NextResponse.cookies.set`.
  The token is never exposed to client JS. The client only ever receives
  `{ ok: true }` on success. A shared `proxyAuth` helper (`api/auth/proxy.ts`)
  backs both endpoints.
- **Cookie attributes.** `httpOnly`, `sameSite=lax`, `path=/`, `maxAge` = 24h
  (matches the backend's `TOKEN_EXPIRY_HOURS`). `secure` is gated on
  `NODE_ENV === "production"` so the cookie still works over `http://localhost`
  in dev but is secure on Vercel.
- **`proxy.ts` (Next 16 middleware) enforces the gate by cookie presence.**
  Route protection runs at the edge: any matched path redirects to `/login`
  when the `prism_token` cookie is absent, and `/login`/`/register` redirect to
  `/dashboard` when it is present. Middleware checks *presence only* — full JWT
  signature/expiry validation stays on the backend, which already verifies the
  token on every API call. Duplicating signature verification (secret + `jose`)
  at the edge would add a dependency and a second source of truth for no gain
  at this slice's scope. Uses the Next 16 `proxy.ts` convention (the renamed
  `middleware.ts`).
- **Generic login error.** The login page always renders a single generic
  message on any failure and never surfaces which field was wrong, mirroring the
  backend's `GENERIC_AUTH_ERROR`. Registration *does* forward the backend
  message (e.g. "Email already exists") since that is the expected onboarding
  feedback and not a credential-probing surface.
- **Placeholder `/dashboard`.** The redirect target must exist to make the flow
  verifiable. A minimal protected `/dashboard` stub (with logout) ships here;
  the real document-management dashboard is slice-17.

## Out of scope

No "remember me", no social login, no password-strength indicator (per the
slice). No shared app shell / global nav yet — that arrives with the
authenticated pages in later Sprint 5 slices.
