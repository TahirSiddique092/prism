# slice-18 — Frontend — search page and result view

**Sprint:** 5 — Frontend
**Module:** frontend

## What to build

`/search` — the core page of the app. A search bar at the top, results listed below with source, snippet, score, and a cache indicator.

## Acceptance criteria

- Search bar submits on Enter or button click — calls `POST /api/search`
- While waiting for results, a loading state is shown
- Each result card shows: document title, matched text snippet, similarity score, and whether it was a semantic or FULLTEXT fallback result
- A small badge shows `cached` if the result came from Redis
- Clicking a result card navigates to `/documents/:doc_id`
- Zero results shows a friendly empty state — not a blank page
- Previous query and results persist if the user navigates away and returns (use URL query param `?q=`)

## Out of scope

- No filters by topic or date
- No pagination — top 10 results only

## Assigned To

Dev A

## Human review required?

No.
