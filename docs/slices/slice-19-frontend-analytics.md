# slice-19 — Frontend — analytics pages

**Sprint:** 5 — Frontend
**Module:** frontend

## What to build

Three analytics pages, each wired to their respective API endpoints from sprint 4.

## Pages

**`/analytics/history`**
- Table of past queries with columns: query, search count, rank, last searched
- Sorted by rank ascending (rank 1 at top)

**`/analytics/unsearched`**
- List of documents never surfaced in any search result
- Each row shows title and upload date
- A nudge message: "These documents have never come up in a search — try searching for their topics"

**`/analytics/top-documents`**
- List of most-surfaced documents with appearance count and average similarity score
- Sorted by appearance count descending

## Acceptance criteria

- All three pages are accessible from a shared `/analytics` nav
- Each page shows an empty state if no data exists — no blank screens
- Data is fetched client-side on page load — no SSR needed here
- All three pages are protected — unauthenticated access redirects to `/login`

## Out of scope

- No charts or graphs — tables only in v1
- No export to CSV

## Assigned To

Dev B

## Human review required?

No.
