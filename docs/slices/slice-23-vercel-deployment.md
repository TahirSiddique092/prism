# slice-23 — Vercel deployment and CORS config

**Sprint:** 6 — Polish and deployment
**Module:** infra

## What to build

Deploy the Next.js frontend to Vercel and configure CORS on the Flask backend to only accept requests from the Vercel domain.

## Acceptance criteria

- Next.js app is deployed and publicly accessible via a Vercel URL
- `NEXT_PUBLIC_API_URL` is set in Vercel environment variables pointing to the OCI VM's public IP
- Flask CORS is configured to allow requests only from the Vercel domain — all other origins return 403
- `POST /api/auth/login` works end-to-end from the deployed Vercel frontend to the OCI Flask API
- `POST /api/search` works end-to-end with a real uploaded document
- No secrets (JWT_SECRET, DB passwords) are present in the Vercel environment or the frontend bundle

## Human review required

This slice touches CORS config and environment variables — do not merge without human sign-off.

## Out of scope

- No custom domain
- No HTTPS on the OCI backend in v1

## Assigned To

Dev B
