# ADR-007 — Frontend Dashboard & Document Management (slice-17)

## Context

slice-17 implements the authenticated user's home page (`/dashboard`), providing:
1. Listing of the user's uploaded documents with title, upload date, status (`processing`, `ready`, `error`), and chunk count.
2. PDF upload form accepting max 20MB files and comma-separated topics.
3. Immediate addition of newly uploaded documents with `processing` status (updated on manual refresh).
4. Deletion of documents with a confirmation prompt before sending `DELETE /api/documents/:doc_id` and removing from the UI without a full page reload.
5. Visible error badge for documents with `error` status.

## Decisions

- **Route handler proxies for authenticated operations.** Client interactions with documents (`GET /api/documents`, `POST /api/documents/upload`, `DELETE /api/documents/:id`) go through Next route handlers that read the `httpOnly` `prism_token` cookie and forward the JWT to the Flask backend as `Authorization: Bearer <token>`. The JWT remains unexposed to client JavaScript.
- **Multipart stream forwarding for uploads.** The upload handler validates PDF format and 20MB file limit before forwarding the `FormData` directly to the backend upload endpoint.
- **Optimistic client state update on upload.** Upon successful upload response (`201 Created` with `doc_id`), the document is immediately prepended to the local document list in `processing` status. Consistent with slice requirements, real-time polling is omitted; manual refresh re-fetches the latest document statuses from the server.
- **Native confirmation modal and local state removal.** Document deletion triggers a native modal confirmation dialog. Upon confirmation and successful `DELETE`, the document is removed from React state without triggering a full page reload.
- **Next 16 Partial Prerendering (PPR) compatibility.** The server-side initial document fetch inside `/dashboard` is wrapped in a `<Suspense>` boundary to integrate with Next 16's `cacheComponents` and PPR architecture.

## Out of Scope

- No drag-and-drop file upload.
- No real-time status polling (manual refresh only).
