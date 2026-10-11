# ADR-009 — Frontend Analytics Pages & API Handlers (slice-19)

## Context

slice-19 implements the three analytics pages wired to their respective backend API endpoints from sprint 4 (slices 14 & 15):
- `/analytics/history`: query history ranked by frequency using SQL window functions (`GET /api/analytics/history`).
- `/analytics/unsearched`: documents never surfaced in any search result using CTE (`GET /api/analytics/unsearched`).
- `/analytics/top-documents`: most-surfaced documents by appearance count using top_documents SQL view (`GET /api/analytics/top-documents`).

All three pages must be protected (redirect unauthenticated access to `/login`), share a common `/analytics` nav, show informative empty states instead of blank screens, and fetch data purely client-side on page load (no SSR needed).

## Decisions

- **Route handler proxies for authenticated endpoints.** `GET /api/analytics/history`, `GET /api/analytics/unsearched`, and `GET /api/analytics/top-documents` are Next.js route handlers that extract the `httpOnly` `prism_token` cookie and forward requests upstream with `Authorization: Bearer <token>`. Unauthenticated requests return 401; upstream unreachable errors return 502. The JWT is never exposed to client-side JavaScript or localStorage.
- **Shared `/analytics` navigation via layout.** A dedicated `src/app/analytics/layout.tsx` wraps all analytics sub-routes with `AppHeader` and `AnalyticsNav`. The shared tab nav visually indicates the active tab (`/analytics/history`, `/analytics/unsearched`, `/analytics/top-documents`) with accessible SVG icons and labels. Visiting the root `/analytics` route performs an immediate server-side redirect to `/analytics/history`.
- **Client-side data fetching with lifecycle safety.** Each analytics page (`HistoryClient`, `UnsearchedClient`, `TopDocumentsClient`) fetches data via `useEffect` upon mounting, with cancellation guard flags and distinct states: loading spinner, inline error alert with retry button, empty state, and populated data table.
- **Explicit sorting and invariant enforcement.**
  - `/analytics/history`: sorted by `query_rank` ascending (rank 1 at top). Exposes query, search count, rank, and last searched columns. Clicking a query navigates to `/search?q=...` to re-run the search.
  - `/analytics/unsearched`: displays title and upload date, alongside the required nudge message: *"These documents have never come up in a search — try searching for their topics"*.
  - `/analytics/top-documents`: sorted by `appearance_count` descending. Handles both numeric similarity scores (formatted to 4 decimal places) and `null` scores (displayed as "—").
- **Shared analytics utility module.** Common interfaces (`SearchHistoryItem`, `UnsearchedDocumentItem`, `TopDocumentItem`), navigation configuration (`ANALYTICS_NAV_ITEMS`), and pure sorting/formatting functions are centralized in `src/lib/analytics.ts` so both client components and the Node test suite share consistent data structures.

## Out of Scope

- No charts or graphs (tables only in v1).
- No export to CSV.
