# PRISM UI Implementation Specification

**Status:** DRAFT FOR FRONTEND IMPLEMENTATION  
**Scope:** PRISM v1 Next.js frontend  

This document is the implementation contract for the mockups. The mockups provide the visual/state reference; this document defines the shared behavior and component boundaries that should be preserved when translating them into Next.js/React.

## 1. Canonical page map

| Mockup Concept | Recommended Route | Purpose |
|---|---|---|
| `01-login` | `/login` | User authentication |
| `02-register` | `/register` | User onboarding |
| `03-dashboard` | `/dashboard` | Document management and upload |
| `04-search` | `/search` | Core semantic search interface |
| `05-document-detail` | `/documents/:doc_id` | Document metadata and Neo4j topic graph relations |
| `06-analytics-history` | `/analytics/history` | Ranked search queries |
| `07-analytics-unsearched` | `/analytics/unsearched` | Documents missing from search results |
| `08-analytics-top` | `/analytics/top-documents` | Most frequently matched documents |

Routes are a frontend reference. The Next.js app handles the routing, but all data fetching must use the Flask API.

## 2. State contract

| View | Required states | Expected behavior |
|---|---|---|
| Login / Register | `default`, `loading`, `error` | Loading disables submission. Authenticated users visiting these routes must redirect to `/dashboard`. |
| Dashboard | `loaded`, `empty`, `loading` | Upload errors show inline badges. Deletions require confirmation and update the list without full page reload. |
| Search | `active`, `loading`, `empty`, `error` | Search persists query in URL (`?q=`). Empty state is a friendly message, not a blank screen. |
| Document Detail | `loaded`, `empty-relations`, `error` | 404 handled gracefully if document ID is invalid or belongs to another user. |
| Analytics (All) | `loaded`, `empty`, `loading` | Fetched client-side on load. Empty states provide context (e.g., "No searches yet"). |

## 3. Shared application shell

Implement a reusable shell rather than duplicating page chrome across the authenticated routes.

### End-user shell (Authenticated)
- Global Navigation (Dashboard | Search | Analytics)
- User session context / Logout button
- Main content region

Suggested React components:

```text
AppShell
├── TopNavigation
├── UserMenu
└── PageContent
```

*Note: `/login` and `/register` sit outside this authenticated shell.*

## 4. Shared component contract

The following should become reusable components rather than page-specific copies:

```text
Button
Input
FileInput (Drag & Drop)
Badge (Status: processing/ready/error)
Tag (Topics)
Card
DataTable
EmptyState
LoadingSpinner
ConfirmationModal
DocumentRow
SearchResultCard
PdfViewer
```

## 5. Security & Auth boundary

- **JWT Storage:** The JWT returned from `/api/auth/login` and `/api/auth/register` must be stored securely. The PRD/slices specify an `httpOnly` cookie approach.
- **Route Protection:** All routes except `/login` and `/register` must check for authentication and redirect to `/login` if unauthenticated.
- **CORS:** The Flask backend will be configured to only accept requests from the Next.js Vercel domain. Ensure API requests send credentials properly.

## 6. Document upload behavior

The upload form requires specific handling:
- **Validation:** Client-side validation for PDF format and size (≤ 20MB) before hitting the API.
- **Topics:** Comma-separated strings need to be parsed into an array (`topics[]`) before sending to the backend.
- **Optimistic UI:** While the document is being processed by the backend (chunking/embedding), the UI should reflect a `processing` status. 
- *Note:* Real-time polling is out of scope for v1. Users will manually refresh to see status changes from `processing` to `ready`.

## 7. Search behavior

The search interface must surface backend context effectively:
- **Badges:** If a result has `cached: true`, display a small indicator. If `score` is null (indicating a FULLTEXT fallback), display a fallback indicator.
- **Navigation Persistence:** If a user clicks a result, goes to the Document Detail, and clicks "Back", the search query and results should still be present.

## 8. Data and API boundary

Do not place database access, SQL queries, Redis cache logic, or pgvector calculations in Next.js code. The frontend should act purely as a consumer of the Flask API.

All endpoints are defined in the `docs/ADD.md` and slice documentation. Ensure API Base URL is configurable via `NEXT_PUBLIC_API_URL`.

## 9. What is intentionally NOT part of this frozen UI

Do not add new v1 product surfaces for:
- Advanced topic editing after upload.
- Sorting/filtering controls on the dashboard.
- Search result pagination (returns top 10 only).
- Responsive mobile layouts (desktop is the primary target). 

Those remain outside the current PRISM v1 scope unless the repository requirements are formally changed.
