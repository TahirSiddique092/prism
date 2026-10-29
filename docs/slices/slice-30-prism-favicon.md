# slice-30 — PRISM favicon

**Sprint:** 7 — Hardening and UX
**Module:** frontend

## What to build

The app's browser tab shows the PRISM mark instead of the default Next.js icon.

## Changes

**Problem:** `frontend/src/app/favicon.ico` is the default icon from create-next-app. `frontend/public/` also still holds the sample SVGs from create-next-app (`next.svg`, `vercel.svg`, `file.svg`, `globe.svg`, `window.svg`), which nothing uses.

**Change:**
- Add the PRISM mark used in the app header (`PrismLogo`), drawn on a dark rounded square so it reads at 16 px on light and dark tabs:
  - `src/app/icon.svg` for current browsers;
  - `src/app/favicon.ico` (16, 32 and 48 px) for older ones;
  - `src/app/apple-icon.png` (180 px) for iOS home screens.
- Use static files only. `src/proxy.ts` lets `favicon.ico` and image extensions through without a session. A generated route such as `/icon` has no extension, so it would redirect signed-out visitors to `/login`.
- Delete the unused sample SVGs, and keep `frontend/public/` with a `.gitkeep`. The frontend `Dockerfile` copies `/app/public`, so the image build fails if the folder disappears.

## Acceptance criteria

- The tab shows the PRISM mark on `/login` (signed out) and `/dashboard` (signed in)
- `/icon.svg`, `/favicon.ico` and `/apple-icon.png` return 200 without a session cookie
- Nothing references the deleted sample SVGs, `npm run build` passes, and the frontend Docker image still builds

## Out of scope

- The landing site, which already has its own icon
- A web manifest or PWA icons

## Assigned To

Unassigned

## Human review required?

No.
