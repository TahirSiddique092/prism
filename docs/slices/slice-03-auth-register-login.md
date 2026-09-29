# slice-03 — Auth — register and login

**Sprint:** 1 — Foundation
**Module:** auth

## What to build

`POST /api/auth/register` and `POST /api/auth/login` endpoints. Passwords hashed with bcrypt. On success, both return a signed JWT.

## Endpoints

**POST /api/auth/register**
- Request: `{ name, email, password }`
- Response: `{ user_id, token }`
- Errors: 409 if email already exists, 400 if fields missing

**POST /api/auth/login**
- Request: `{ email, password }`
- Response: `{ user_id, token }`
- Errors: 401 if email not found or password wrong

## Acceptance criteria

- Passwords are hashed with bcrypt before insert — plain text is never stored or logged
- JWT payload contains `{ user_id, email, exp }` — expiry 24 hours
- Registering with a duplicate email returns 409, not a 500
- Wrong password returns 401 with a generic message (do not reveal which field is wrong)
- Token is valid and decodable using `JWT_SECRET` from env

## Out of scope

- No logout endpoint — that's slice-04
- No email verification
- No password reset

## Assigned To

Dev B

## Human review required?

Yes — touches auth module and JWT logic.
