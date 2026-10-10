# ADR-003 — Related documents via Cypher (slice-13)

## Context

slice-13 adds `GET /api/documents/:doc_id/related`, returning up to 5 documents
that share the most topics with the given document, scoped to the authenticated
user.

## Decisions

- **User scoping baked into the Cypher.** The spec's example query matches any
  `d2` sharing a topic. Acceptance criterion 2 requires results limited to the
  user's own documents, so the query constrains both the source document and
  every candidate to be `UPLOADED` by the same `User`:
  `(u:User {user_id})-[:UPLOADED]->(d1)... (d2)<-[:UPLOADED]-(u)`.
- **Ownership / 404 resolved in MySQL.** MySQL is the source of truth for
  document ownership, so the route calls `get_document_by_id(doc_id, user_id)`
  and returns 404 before touching Neo4j — consistent with the `/url` and
  `DELETE` endpoints. The graph is queried only for an owned document.
- **Graceful degradation to an empty list.** No criterion specifies behaviour
  when Neo4j is unreachable. `get_related_documents` catches all errors and
  returns `[]` (logged), so a graph outage yields "no related documents"
  (HTTP 200) rather than a 500. This matches the "empty list, not an error"
  spirit of criterion 3.

## Out of scope

No cross-user discovery, no topic suggestions (per the slice).
