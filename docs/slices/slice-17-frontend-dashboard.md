# slice-17 — Frontend — dashboard

**Sprint:** 5 — Frontend
**Module:** frontend

## What to build

`/dashboard` — the user's home page. Shows their uploaded documents and a form to upload a new PDF with topic tags.

## Acceptance criteria

- Lists all the user's documents with title, upload date, status (`processing` / `ready` / `error`), and chunk count
- Upload form accepts a PDF file (max 20MB) and a comma-separated topics input
- After upload, the document appears in the list immediately with status `processing` — status updates on page refresh
- Delete button on each document triggers `DELETE /api/documents/:doc_id` with a confirmation prompt before firing
- Deleted document disappears from the list without a full page reload
- Documents with status `error` show a visible error badge

## Out of scope

- No drag-and-drop upload
- No real-time status polling — manual refresh only

## Assigned To

Dev B

## Human review required?

No.
