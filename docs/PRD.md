# PRD

## Goal

A web app where users upload their study PDFs once and search through them using plain English — not exact keywords. A query like "how do joins work" surfaces relevant content even if the document uses different words.

## Users

Students who collect technical PDFs and notes across a course and need to retrieve specific concepts quickly — especially under exam pressure when re-reading everything isn't an option.

## Core features

- **Register / Login** — email and password, one account per user, sessions persist across browser closes
- **Upload a PDF** — parse, chunk, and store it so it's searchable immediately after upload
- **Semantic search** — type a natural language query, get the top results ranked by meaning, not keyword match
- **Result view** — each result shows the source document, the matched text snippet, and a similarity score
- **Document reader** — open and read the full original PDF directly inside the system without downloading
- **Fallback search** — if semantic confidence is low, automatically fall back to full-text keyword search
- **Search history** — view past queries ranked by how often they've been searched
- **Related documents** — surface other documents that share topics with the one you're viewing
- **Unsearched docs** — show documents the user has uploaded but never seen in any search result
- **Query cache** — repeated searches return instantly without re-running the vector lookup

## Out of scope

- No social login, OAuth, or 2FA — email + password only in v1
- No mobile app or responsive design — desktop browser only
- No real-time collaboration or shared document libraries between users
- No support for image-only or scanned PDFs — text layer required

## Success criteria

- A user can register, upload a PDF, and get a search result within 60 seconds of first visit
- A query returns relevant results even when zero words from the query appear in the matched chunk
- Every unit of the DBMS syllabus (Units 1–4) is exercised by at least one concrete, demonstrable feature
- The EXPLAIN output for the two most common queries shows a measurable improvement after indexing
- Frontend is publicly accessible via Vercel URL; backend API is reachable via OCI public IP

## Open questions

- **Chunking:** 200-word fixed windows or sentence-boundary-aware? Needs a quick test on sample academic PDFs before Week 1.
- **Topic extraction:** Manual tags on upload vs. auto-extract with spaCy — scope decision needed before building the Neo4j layer.
- **Similarity threshold:** What cosine distance score triggers the FULLTEXT fallback? Set empirically during Week 3 testing.
- **Vector store:** pgvector (one Postgres instance, transactional) vs. ChromaDB (friendlier Python API) — pick one before architecture is written.
- **CORS & API security:** Flask API on OCI needs CORS configured to only allow the Vercel frontend origin. How do we handle API keys or session tokens between frontend and backend?