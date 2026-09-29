# Research

## The problem

Students accumulate notes and PDFs across a semester but can't find specific content when they need it. Ctrl+F only matches exact words — if you wrote "combining tables" but search for "joins," you get nothing. The mismatch between how you remember something and how you originally wrote it makes your own notes unreliable.

## Who has this problem

Any student who collects technical documents and later struggles to retrieve specific ideas from them — not the file, but the *thought inside the file*. The pain is sharpest when studying for exams or solving problems under time pressure.

## Why now / why you

Three things make this buildable right now:

1. **Free, fast embedding models exist.** `sentence-transformers/all-MiniLM-L6-v2` runs on CPU in ~80ms per chunk — no GPU, no API cost.
2. **pgvector makes vector search a SQL extension.** It's now just `CREATE EXTENSION vector` on a Postgres instance — no dedicated vector infra needed.
3. **The DBMS syllabus demands it.** PRISM naturally exercises all four units — relational, advanced SQL, normalization, and next-gen DBs — without forcing anything artificially.

## What exists already

| Tool | What it does | What it misses |
| --- | --- | --- |
| Ctrl+F / grep | Exact keyword match in one file | Cross-document, meaning-based search |
| Notion / Obsidian | Keyword search across notes | Doesn't understand synonyms or paraphrases |
| Google Drive search | Finds file names and surface content | No semantic ranking of chunks |
| ChatGPT file upload | Answers questions about a doc | Not persistent; no local schema; re-upload every session |
| Elasticsearch | Full-text search at scale | No semantic layer; heavy infra for a student project |

**The gap:** None combine semantic search + relational metadata + graph relationships + a persistent normalized schema in one coherent system.

## Rough shape of the solution

A locally-run web app where users upload PDFs once. The system chunks and embeds each document, stores metadata in MySQL, vectors in pgvector, topic links in Neo4j, and caches queries in Redis. A plain-English search returns ranked, meaning-matched results with source and snippet — no exact word match needed.

## Open questions

- **Chunking strategy:** Fixed 200-word windows vs. sentence-boundary-aware splitting — does overlap size affect retrieval quality on academic text?
- **Topic extraction:** Manual tagging on upload vs. auto-extract with spaCy NER — auto is more impressive but adds scope.
- **Fallback threshold:** What cosine distance triggers the FULLTEXT fallback? Needs tuning on real sample docs.
- **User accounts:** Single-user demo vs. proper login — accounts make per-user analytics and window functions more meaningful.
- **pgvector vs. ChromaDB:** pgvector keeps everything in one Postgres instance (simpler, transactional); ChromaDB has a friendlier Python API.