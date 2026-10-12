# ADR-010 — Frontend Document Detail Page (slice-20)

## Context

slice-20 implements `/documents/:doc_id`: a page showing a document's metadata,
its topic tags, up to 5 related documents (from the Neo4j topic graph), and an
inline PDF viewer. It is a frontend slice, but one acceptance criterion — "shows
document title, upload date, status, chunk count, **and topic tags**" — has no
backend data source. At the start of this slice the backend exposed:

- `GET /api/documents` — the full list `[{ doc_id, title, uploaded_at, status, chunk_count }]`
- `GET /api/documents/:doc_id/related` — `[{ doc_id, title, shared_topics }]` (slice-13)
- `GET /api/documents/:doc_id/url` — `{ view_url }` pre-signed MinIO link (slice-08)

There was **no endpoint returning a single document's own topic tags**, and no
single-document metadata endpoint. Topics are written to Neo4j on upload
(slice-12) via `(Document)-[:ABOUT]->(Topic)`. The MySQL `topics`/`doc_topics`
tables exist in the schema but are never populated by the upload flow, so the
only authoritative source of a document's topics is Neo4j.

## Decisions

- **New backend endpoint `GET /api/documents/:doc_id`.** Returns
  `{ doc_id, title, uploaded_at, status, chunk_count, topics }` in one call.
  Metadata and `chunk_count` come from MySQL; `topics` come from Neo4j. This is a
  read-only addition to the `documents`/`graph` modules — it touches neither
  auth/JWT, nor destructive operations, nor infra/secrets, so per AGENTS.md it
  does not require human review. It was unavoidable: the slice's "topic tags"
  criterion cannot be met without a backend source.
- **`get_document_topics(doc_id, user_id)` in the graph module.** Mirrors
  `get_related_documents` (slice-13): user-scoped Cypher
  (`(u:User)-[:UPLOADED]->(d:Document)-[:ABOUT]->(t:Topic)`), alphabetically
  ordered, and degrades gracefully to `[]` on any Neo4j failure so a down graph
  never turns the detail page into an error. Ownership/404 remains authoritative
  in MySQL via `get_document_by_id`; the graph is queried only after ownership is
  confirmed, so one user can never read another user's topics.
- **Topics read from Neo4j, not MySQL `doc_topics`.** Although the relational
  schema has `topics`/`doc_topics`, nothing populates them. Reading them would
  always return empty. Neo4j is the live source of truth for topics, consistent
  with slices 12 and 13.
- **Route-handler proxies reuse the slice-16/17/18 pattern.** `GET
  /api/documents/[id]`, `.../related`, and `.../url` read the `httpOnly`
  `prism_token` cookie and forward it as `Authorization: Bearer <token>`,
  passing the upstream status through (notably 404) so the page can render its
  not-found state. The JWT is never exposed to client JS.
- **Metadata + related fetched server-side; view URL fetched client-side.** The
  server component fetches metadata (fatal — drives `notFound()` on 404 and
  `redirect("/login")` on 401) and related docs (best-effort, degrades to the
  "No related documents found" state). The pre-signed view URL is fetched
  client-side on mount so the embedded `<iframe>` never points at a link that
  expired between server render and interaction, and so PDF load/error states
  have somewhere to live.
- **Whole body inside one Suspense boundary.** `/documents/[id]` is the app's
  first dynamic-segment route. Under Next 16 Cache Components, `params`,
  `cookies()`, and `AppHeader`'s `usePathname()` all read request-time data that
  is only permitted inside Suspense. The interactive header therefore renders
  inside the boundary, with a hook-free static header skeleton as the prerendered
  fallback.
- **Ownership mismatch surfaces as 404, not 403.** A `doc_id` belonging to
  another user returns the same "Document not found" page as a non-existent id,
  so the page never leaks the existence of another user's document. A co-located
  `not-found.tsx` renders this within the app shell.

## Out of Scope

- No chunk listing on this page.
- No topic editing.
