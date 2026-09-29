# slice-04 — Auth — JWT middleware and logout

**Sprint:** 1 — Foundation
**Module:** auth

## What to build

A Flask middleware decorator `@require_auth` that validates the JWT on every protected route, and a `POST /api/auth/logout` endpoint.

## Acceptance criteria

- `@require_auth` decorator extracts and verifies the token from `Authorization: Bearer <token>` header
- Verified `user_id` is injected into the request context so any route can access it via `g.user_id`
- Missing or invalid token returns 401
- Expired token returns 401 with message "token expired"
- `POST /api/auth/logout` returns 200 with `{ message: "logged out" }` — stateless, client discards token
- All routes except `/api/auth/register` and `/api/auth/login` are protected by default

## Out of scope

- No token blocklist or server-side session invalidation — stateless JWT only in v1

## Assigned To

Dev B

## Human review required?

Yes — touches auth module and JWT logic.
