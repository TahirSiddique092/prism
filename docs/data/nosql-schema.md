# PRISM — Non-Relational Stores (Vector, Graph, Key-Value, Object)

> Companion document: [relational-schema.md](relational-schema.md) covers the MySQL schema, the Level 0 / Level 1 data flow diagrams, and the authentication and analytics flows.

## 1. Why more than one database

PRISM uses **polyglot persistence**: each kind of data goes to the store that handles it best. MySQL is the source of truth for ownership and text. The four stores below each do one specialised job.

| Store | Engine | Job in PRISM | Hosted on (ADR-015) |
|---|---|---|---|
| Vector | PostgreSQL + **pgvector** | Find chunks whose *meaning* is closest to a query | Neon |
| Graph | **Neo4j** | Find documents that share topics | Neo4j Aura |
| Key-value | **Redis** | Return repeated searches instantly | Upstash |
| Object | **S3-compatible storage** | Keep the original PDF files | Neon Object Storage |

> **A note on pgvector.** It runs inside PostgreSQL, so technically it is SQL. It is grouped here because it acts as a *vector database*, one of the "next-generation" database types, and its job (similarity search over embeddings) is not relational.

### How the stores are linked

The stores share IDs that MySQL generates. No store keeps its own copy of ownership.

| ID | MySQL | pgvector | Neo4j | Redis | Object storage |
|---|---|---|---|---|---|
| `user_id` | `users`, `documents`, `search_log` | — | `User.user_id` | in the key: `search:{user_id}:…` | in the key: `{user_id}/…pdf` |
| `doc_id` | `documents`, `chunks` | `chunk_vectors.doc_id` | `Document.doc_id` | inside the cached value | — |
| `chunk_id` | `chunks` | `chunk_vectors.chunk_id` | — | inside the cached value | — |
| `minio_key` | `documents.minio_key` | — | — | — | the object key |

Every request that names a document first checks in MySQL that the logged-in user owns it, and only then reads the other stores. A maintenance script, `backend/db/reconcile.py`, checks that pgvector, Neo4j and object storage agree with MySQL (see [ADR-016](../decisions/ADR-016-cross-store-delete.md)).

---

## 2. Vector store — PostgreSQL + pgvector

### Schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunk_vectors (
    chunk_id  INTEGER PRIMARY KEY,   -- same value as MySQL chunks.chunk_id
    doc_id    INTEGER NOT NULL,      -- copied here so searches can filter by document
    embedding VECTOR(384)            -- all-MiniLM-L6-v2 output
);

CREATE INDEX idx_chunk_vectors_embedding
    ON chunk_vectors USING hnsw (embedding vector_cosine_ops);
```

| Concept | Value |
|---|---|
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2`, runs inside the Flask process |
| Dimensions | 384 |
| Distance | Cosine distance, operator `<=>`. 0 means identical meaning; larger means less similar. |
| Index | **HNSW**, a graph-based approximate nearest-neighbour index. Migration 005 replaced the original ivfflat index because HNSW needs no training data. |
| Confidence threshold | If the best distance is **> 0.75**, search falls back to MySQL FULLTEXT keyword search |

### Similarity query
```sql
SELECT chunk_id, doc_id, (embedding <=> %s::vector) AS score
FROM chunk_vectors
WHERE doc_id = ANY(%s)          -- the user's own doc_ids, fetched from MySQL
ORDER BY score ASC
LIMIT 10;
```

---

## 3. Graph store — Neo4j

### Graph model

```mermaid
flowchart LR
    U(("User<br/>user_id, email"))
    D(("Document<br/>doc_id, title"))
    T(("Topic<br/>name"))
    U -->|UPLOADED| D
    D -->|ABOUT| T
```

| Node | Properties | Identified by |
|---|---|---|
| `User` | `user_id`, `email` | `user_id` |
| `Document` | `doc_id`, `title` | `doc_id` |
| `Topic` | `name`, stored trimmed and lowercase (so "SQL" and "sql" are the same topic) | `name` |

| Relationship | Meaning |
|---|---|
| `(User)-[:UPLOADED]->(Document)` | Who owns the document |
| `(Document)-[:ABOUT]->(Topic)` | Topic tags entered at upload time |

**Example.** Two documents tagged "joins" become connected through one shared `Topic` node:

```mermaid
flowchart LR
    U((User 1))
    D1((DBMS Notes))
    D2((SQL Cheatsheet))
    T1((joins))
    T2((normalization))
    U -->|UPLOADED| D1
    U -->|UPLOADED| D2
    D1 -->|ABOUT| T1
    D1 -->|ABOUT| T2
    D2 -->|ABOUT| T1
```

### Cypher queries

**Write on upload.** `MERGE` means "create only if it doesn't already exist", so repeating the write never creates duplicates.
```cypher
MERGE (u:User {user_id: $user_id}) SET u.email = $email
MERGE (d:Document {doc_id: $doc_id}) SET d.title = $title
MERGE (u)-[:UPLOADED]->(d)
WITH d
UNWIND $topics AS topic_name
MERGE (t:Topic {name: topic_name})
MERGE (d)-[:ABOUT]->(t)
```

**Topics of one document** (document detail page)
```cypher
MATCH (u:User {user_id: $user_id})-[:UPLOADED]->(d:Document {doc_id: $doc_id})-[:ABOUT]->(t:Topic)
RETURN t.name AS name ORDER BY t.name
```

**Related documents.** These are the documents that share the most topics with this one, from the same user only.
```cypher
MATCH (u:User {user_id: $user_id})-[:UPLOADED]->(d1:Document {doc_id: $doc_id})
      -[:ABOUT]->(t:Topic)<-[:ABOUT]-(d2:Document)<-[:UPLOADED]-(u)
WHERE d2.doc_id <> $doc_id
RETURN d2.doc_id AS doc_id, d2.title AS title, COUNT(t) AS shared_topics
ORDER BY shared_topics DESC
LIMIT 5
```
The results are then filtered against MySQL, so only documents that still exist are returned.

**Delete.** Removes the document with its relationships, then any topic no document is about any more.
```cypher
MATCH (:User {user_id: $user_id})-[:UPLOADED]->(d:Document {doc_id: $doc_id})
DETACH DELETE d

MATCH (t:Topic) WHERE NOT (t)<-[:ABOUT]-() DELETE t
```

---

## 4. Key-value cache — Redis

| Aspect | Value |
|---|---|
| Key | `search:{user_id}:{md5(normalized query)}` |
| Normalisation | Lowercase, trim, and collapse repeated spaces, so "Joins  in SQL" and "joins in sql" share one key |
| Value | JSON array of results: `[{ chunk_id, doc_id, doc_title, snippet, score }]` |
| Expiry (TTL) | 3600 s (1 hour) |
| Cleared when | The user uploads a document · a document finishes processing · the user deletes a document |
| How it is cleared | `SCAN` for keys matching `search:{user_id}:*`, then `DEL` (`SCAN` does not block Redis; see ADR-001-redis-cache) |

If Redis cannot be reached, a read counts as a cache miss and a write is skipped. Search still works, just without the speed-up.

Example entry:
```
KEY   search:7:5d41402abc4b2a76b9719d911017c592
TTL   3600
VALUE [{"chunk_id":112,"doc_id":4,"doc_title":"dbms-notes.pdf",
        "snippet":"A join combines rows from two tables…","score":0.31}, …]
```

---

## 5. Object storage — S3-compatible

| Aspect | Value |
|---|---|
| Bucket | `prism-documents` (configurable with `S3_BUCKET`) |
| Object key | `{user_id}/{uuid4}.pdf`, also saved as `documents.minio_key` in MySQL |
| Content type | `application/pdf` |
| Write | When a PDF is uploaded (maximum 20 MB) |
| Read (backend) | The background worker downloads the PDF to extract its text |
| Read (browser) | Through a **pre-signed URL** valid for 1 hour, so the PDF opens in the built-in viewer without being made public |
| Delete | When the document is deleted |

The code uses the standard S3 API (boto3), so the same code runs against MinIO, Neon Object Storage, Cloudflare R2 or AWS S3.

---

## 6. Summary — what each operation touches

| Operation | MySQL | pgvector | Neo4j | Redis | Object storage |
|---|---|---|---|---|---|
| Register / login | read / write | | | | |
| Upload | write | write | write | clear | write |
| Search | read + log | read | | read / write | |
| Document detail | read | | read | | |
| View PDF | read | | | | pre-signed link |
| Related documents | read (ownership + existence) | | read | | |
| Delete | delete (+ audit trigger) | delete | delete | clear | delete |
| Analytics | read | | | | |

---

## 7. Data flow diagrams

**Notation:** rectangle = external entity · rounded box = process · cylinder = data store · arrow = data flow. These are Level 2 breakdowns of the Level 1 processes in [relational-schema.md § 7](relational-schema.md#7-data-flow-diagrams).

### Level 2 — 2.0 Upload & process document

```mermaid
flowchart TB
    S[Student]
    P21([2.1 Validate<br/>.pdf, ≤ 20 MB])
    P22([2.2 Store file])
    P23([2.3 Record document])
    P24([2.4 Write topic graph<br/>background])
    P25([2.5 Extract & chunk text<br/>background])
    P26([2.6 Embed chunks<br/>background])
    P27([2.7 Mark ready &<br/>clear cache])

    D5[(D5 Object storage)]
    D1a[(D1.2 documents)]
    D1b[(D1.3 chunks)]
    D1t[(D1.4 topics / doc_topics)]
    D2[(D2 chunk_vectors)]
    D3[(D3 Neo4j)]
    D4[(D4 Redis)]

    S -->|PDF + topic tags| P21
    P21 -->|PDF| P22
    P22 -->|"PDF → {user_id}/{uuid}.pdf"| D5
    P22 -->|object key| P23
    P23 -->|"INSERT (status = processing)"| D1a
    P23 -->|normalised topic names| D1t
    P23 -->|"doc_id, object key"| S
    P23 -->|clear user's searches| D4
    P23 -->|doc_id, title, topics| P24
    P24 -->|MERGE User, Document, Topic| D3
    P23 -->|doc_id, object key| P25
    D5 -->|PDF bytes| P25
    P25 -->|"INSERT chunks<br/>(~200 words, 2-sentence overlap)"| D1b
    D1b -->|chunk_id, chunk_text| P26
    P26 -->|384-d vectors| D2
    P26 --> P27
    P27 -->|"status = ready"| D1a
    P27 -->|clear user's searches| D4
```

The user gets a response right after step 2.3. Steps 2.4 to 2.7 run in background threads, and the dashboard shows the document as `processing` until step 2.7 completes. If text extraction or embedding fails, the status is set to `error`.

### Level 2 — 3.0 Search

```mermaid
flowchart TB
    S[Student]
    P31([3.1 Check cache])
    P32([3.2 Get user's doc_ids])
    P33([3.3 Embed query])
    P34([3.4 Vector search])
    P35{{"3.5 Best distance<br/>≤ 0.75?"}}
    P36([3.6 Fetch snippets<br/>& titles])
    P37([3.7 FULLTEXT fallback])
    P38([3.8 Cache results])
    P39([3.9 Log search<br/>background])

    D4[(D4 Redis)]
    D1a[(D1.2 documents)]
    D1b[(D1.3 chunks)]
    D2[(D2 chunk_vectors)]
    D1c[(D1.5 search_log)]
    D1d[(D1.6 search_results)]

    S -->|query| P31
    D4 -->|hit: cached results| P31
    P31 -->|"hit → results (cached = true)"| S
    P31 -->|miss| P32
    D1a -->|doc_ids| P32
    P32 --> P33 --> P34
    D2 -->|top 10 chunk_id + distance| P34
    P34 --> P35
    P35 -->|yes| P36
    D1b -->|chunk text, doc title| P36
    P35 -->|no| P37
    D1b -->|MATCH … AGAINST rows| P37
    P36 --> P38
    P37 --> P38
    P38 -->|"SET key, TTL 1 h"| D4
    P38 -->|ranked results| S
    P38 --> P39
    P31 -->|hit| P39
    P39 -->|query| D1c
    P39 -->|rank 1–10, score| D1d
```

Every search is logged (step 3.9), including cache hits, so the analytics reflect what users actually asked.

### Level 2 — 4.0 View document

```mermaid
flowchart LR
    S[Student]
    P41([4.1 Check ownership])
    P42([4.2 Detail:<br/>metadata + topics])
    P43([4.3 Sign PDF URL])
    P44([4.4 Related documents])

    D1[(D1.2 documents<br/>D1.3 chunks)]
    D3[(D3 Neo4j)]
    D5[(D5 Object storage)]

    S -->|doc_id| P41
    D1 -->|owner, object key| P41
    P41 --> P42
    P41 --> P43
    P41 --> P44
    D1 -->|status, chunk count| P42
    D3 -->|topic names| P42
    P42 -->|title, status, chunks, topics| S
    P43 -->|pre-signed GET| D5
    P43 -->|"view_url (1 h)"| S
    D5 -.->|PDF streamed directly to browser| S
    D3 -->|shared-topic documents| P44
    P44 -->|"up to 5: title, shared_topics"| S
```

### Level 2 — 5.0 Delete document

```mermaid
flowchart LR
    S[Student]
    P51([5.1 Check ownership])
    P52([5.2 Delete row])
    P53([5.3 Delete vectors])
    P56([5.4 Delete graph node])
    P54([5.5 Delete file])
    P55([5.6 Clear cache])

    D1[(D1 MySQL<br/>documents → chunks → search_results)]
    DA[(D1.7 deletion_audit)]
    D2[(D2 chunk_vectors)]
    D3[(D3 Neo4j)]
    D5[(D5 Object storage)]
    D4[(D4 Redis)]

    S -->|doc_id| P51
    D1 -->|owner, object key| P51
    P51 --> P52
    P52 -->|"DELETE (cascades)"| D1
    D1 -. trigger .-> DA
    P52 --> P53
    P53 -->|"DELETE WHERE doc_id"| D2
    P53 --> P56
    P56 -->|"DETACH DELETE Document,<br/>orphan Topics"| D3
    P56 --> P54
    P54 -->|delete object| D5
    P54 --> P55
    P55 -->|"SCAN + DEL search:{user_id}:*"| D4
    P55 -->|"{ message: deleted }"| S
```

### Sequence — Upload

```mermaid
sequenceDiagram
    autonumber
    actor S as Student
    participant FE as Next.js
    participant API as Flask API
    participant OS as Object storage
    participant MY as MySQL
    participant RD as Redis
    participant N4 as Neo4j
    participant W as Worker thread
    participant PG as pgvector

    S->>FE: Choose PDF + topic tags
    FE->>API: POST /api/documents/upload (JWT)
    API->>OS: put {user_id}/{uuid}.pdf
    API->>MY: INSERT documents (processing)
    MY-->>API: doc_id
    API->>MY: INSERT topics + doc_topics
    API->>RD: clear search:{user_id}:*
    par background
        API-)N4: MERGE User/Document/Topic
    and background
        API-)W: process_document(doc_id)
    end
    API-->>FE: 201 { doc_id, minio_key }
    FE-->>S: "Processing…"
    W->>OS: get PDF
    W->>W: extract text, sentence-split, chunk
    W->>MY: INSERT chunks
    W->>W: embed chunks (384-d)
    W->>PG: INSERT chunk_vectors
    W->>MY: UPDATE status = ready
    W->>RD: clear search:{user_id}:*
```

### Sequence — Search

```mermaid
sequenceDiagram
    autonumber
    actor S as Student
    participant FE as Next.js
    participant API as Flask API
    participant RD as Redis
    participant MY as MySQL
    participant PG as pgvector

    S->>FE: "how do joins work"
    FE->>API: POST /api/search (JWT)
    API->>RD: GET search:{user_id}:{md5}
    alt cache hit
        RD-->>API: cached results
    else cache miss
        API->>MY: SELECT doc_id FROM documents WHERE user_id
        API->>API: embed query
        API->>PG: ORDER BY embedding <=> query LIMIT 10
        PG-->>API: chunk_ids + distances
        alt best distance ≤ 0.75
            API->>MY: SELECT chunk text + doc title
        else low confidence
            API->>MY: FULLTEXT MATCH … AGAINST
        end
        API->>RD: SET key (TTL 1 h)
    end
    API-)MY: INSERT search_log + search_results (background)
    API-->>FE: { results, cached }
    FE-->>S: Ranked results with snippets
```
