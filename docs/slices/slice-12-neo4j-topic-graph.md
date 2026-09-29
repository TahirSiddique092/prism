# slice-12 — Neo4j topic graph on upload

**Sprint:** 4 — Graph and analytics
**Module:** graph

## What to build

When a document is uploaded with topic tags, write the corresponding nodes and relationships to Neo4j. Also write the user node if it doesn't exist yet.

## Graph schema

```
(User {user_id, email})
(Document {doc_id, title})
(Topic {name})

(User)-[:UPLOADED]->(Document)
(Document)-[:ABOUT]->(Topic)
```

## Acceptance criteria

- Uploading a document with `topics: ["Normalization", "SQL"]` creates `Topic` nodes for each and `[:ABOUT]` relationships to the document
- `MERGE` is used for `User` and `Topic` nodes — no duplicates created on repeated uploads
- `(User)-[:UPLOADED]->(Document)` relationship is created on every upload
- Topic names are stored lowercase and trimmed — "Normalization" and "normalization" are the same node
- If Neo4j is unreachable, the upload still succeeds — graph write failure is logged but does not block the response

## Out of scope

- No auto topic extraction — topics come from the upload form only
- No topic editing after upload

## Assigned To

Dev A

## Human review required?

No.
