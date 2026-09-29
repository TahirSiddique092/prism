# slice-16 — Frontend — auth pages

**Sprint:** 5 — Frontend
**Module:** frontend

## What to build

`/register` and `/login` pages in Next.js. On success, store the JWT in an httpOnly cookie and redirect to the dashboard.

## Acceptance criteria

- `/register` has fields for name, email, password — calls `POST /api/auth/register`
- `/login` has fields for email, password — calls `POST /api/auth/login`
- JWT is stored in an httpOnly cookie (not localStorage) on successful auth
- Failed login shows a generic error message — not which field is wrong
- Authenticated users visiting `/login` or `/register` are redirected to `/dashboard`
- Unauthenticated users visiting any protected page are redirected to `/login`

## Out of scope

- No "remember me" toggle
- No social login
- No password strength indicator

## Assigned To

Dev A

## Human review required?

Yes — frontend auth handling (JWT storage in httpOnly cookies).
