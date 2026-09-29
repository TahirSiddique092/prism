# slice-13 — Related documents via Cypher

**Sprint:** 4 — Graph and analytics
**Module:** graph

## What to build

`GET /api/documents/:doc_id/related` — query Neo4j to find documents that share the most topics with the given document.

## Cypher query

```cypher
MATCH (d1:Document {doc_id: $doc_id})-[:ABOUT]->(t:Topic)<-[:ABOUT]-(d2:Document)
WHERE d2.doc_id <> $doc_id
RETURN d2.doc_id, d2.title, COUNT(t) AS shared_topics
ORDER BY shared_topics DESC
LIMIT 5
```

## Acceptance criteria

- Returns up to 5 related documents ordered by number of shared topics
- Only returns documents belonging to the authenticated user
- Returns an empty list (not an error) if no related documents exist
- `shared_topics` count is included in the response
- Returns 404 if `doc_id` doesn't belong to the current user

## Out of scope

- No cross-user related document discovery
- No topic suggestions

## Assigned To

Dev A

## Human review required?

No.
