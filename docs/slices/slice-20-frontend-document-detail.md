# slice-20 — Frontend — document detail page

**Sprint:** 5 — Frontend
**Module:** frontend

## What to build

`/documents/:doc_id` — shows a document's metadata, its topic tags, a list of related documents pulled from Neo4j, and an inline PDF viewer.

## Acceptance criteria

- Shows document title, upload date, status, chunk count, and topic tags
- Lists up to 5 related documents with their titles and shared topic count
- Each related document links to its own `/documents/:doc_id` page
- If no related documents exist, shows "No related documents found" — not an error
- Returns 404 page if `doc_id` doesn't belong to the current user
- Page is protected — unauthenticated access redirects to `/login`
- Includes an inline PDF viewer that displays the original document (via a pre-signed URL)

## Out of scope

- No chunk listing on this page
- No topic editing

## Assigned To

Dev A

## Human review required?

No.
