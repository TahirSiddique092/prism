# slice-28 — Dashboard status updates and retry

**Sprint:** 7 — Hardening and UX
**Module:** documents, frontend

## What to build

The dashboard shows processing status as it changes, failed documents can be retried, and documents can no longer get stuck in "processing".

## Changes

### 1. Live status
**Problem:** After an upload, the dashboard keeps showing "processing" until the page is reloaded. In a test on 29 Oct 2026, all three uploads still showed "processing" after 45 s, although they finished about a minute after upload.

**Change:** while any document is `processing`, the dashboard polls `GET /api/documents` every 3 seconds. It stops when none are, and polls once more when the window regains focus.

### 2. Retry failed documents
**Problem:** A document in `error` can only be deleted and uploaded again.

**Change:**
- Add `POST /api/documents/:doc_id/retry`. It works only for the owner, and only when the status is `error`; otherwise it returns 409.
- It deletes the document's chunks (MySQL) and vectors (pgvector), sets the status to `processing`, and starts `process_document` again.
- The dashboard shows a **Retry** button on errored documents.

### 3. Recover documents stuck in processing
**Problem:** Processing runs in a thread inside the API process. If the backend restarts partway through, the document stays `processing` forever.

**Change:** when the backend starts, every document still marked `processing` is set to `error` and logged, so it can be retried. Processing only ever runs inside the API process, so nothing can still be in progress at start-up. This assumes one backend process, which is how it runs today (ADR-015).

## Acceptance criteria

- After an upload, the status badge changes to `ready` (or `error`) without a reload, within 3 s of the change. Polling stops once nothing is processing
- Retry on an errored document returns 202, the status becomes `processing` and then `ready`, and the chunk count equals that of a fresh upload (no duplicates)
- Retry returns 409 for a `ready` document and 404 for another user's document
- After a backend restart with a document stuck in `processing`, that document shows `error` and can be retried
- All existing tests still pass, and new tests cover each criterion above

## Out of scope

- A job queue (Celery, RQ) or multiple backend processes
- Progress percentages during processing

## Assigned To

Unassigned

## Human review required?

Yes. Retry deletes a document's chunks and vectors before processing it again.
