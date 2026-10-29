# slice-27 — Open a search result at its passage

**Sprint:** 7 — Hardening and UX
**Module:** documents, search, frontend
**Depends on:** slice-26 (pdf.js viewer)

## What to build

Clicking a search result opens the PDF at the page where the passage is, with the passage highlighted. Today the link only opens the document at page 1.

## Changes

### 1. Record the pages of each chunk
**Problem:** `process_document` (`backend/modules/documents/worker.py`) joins the text of all pages into one string before splitting it into sentences, so it doesn't know which page a chunk came from.

**Change:**
- Migration `007_chunk_pages.sql` (MySQL). `NULL` means "unknown", which covers old rows until they are backfilled:
  ```sql
  ALTER TABLE chunks ADD COLUMN page_start INT NULL, ADD COLUMN page_end INT NULL;
  ```
- While joining the page texts, record the offset where each page starts. Get sentence offsets from the punkt tokenizer's `span_tokenize`, the same tokenizer `sent_tokenize` uses. For each chunk, return the pages of its first and last sentence (1-based).
- Chunk text and chunk boundaries must stay exactly as they are today.
- `insert_chunks` also writes `page_start` and `page_end`, still as a prepared statement (ADR-017).

### 2. Backfill existing documents
- Add `backend/db/backfill_chunk_pages.py`, a manual CLI. It dry-runs by default; `--apply` writes.
- For each `ready` document whose chunks have no pages, it downloads the PDF and runs extraction and chunking again. It updates the pages by `chunk_index` only if the regenerated chunks match the stored ones exactly (same count, same text). Otherwise it skips the document and reports it.
- Add a short section on how to run it to `README.md`.

### 3. Return the page with each result
- `get_chunks_metadata` and `search_chunks_fulltext` also select `c.page_start`, and each search result gains `"page"` (an integer, or `null` when unknown). Cached results from before this slice have no `page`; the frontend treats that as `null`.
- New endpoint `GET /api/documents/:doc_id/chunks/:chunk_id` returns `{ chunk_id, chunk_text, page_start, page_end }`. It returns 404 unless the chunk belongs to a document of the signed-in user. Add a matching Next.js proxy route.

### 4. Jump and highlight in the viewer
- A search result links to `/documents/:doc_id?chunk=:chunk_id&page=:page`.
- When `chunk` is present, the document page opens the viewer at `page` straight away, fetches the chunk, and highlights its text on pages `page_start` to `page_end` using the pdf.js text layer.
- Matching ignores differences in spaces and line breaks between the PDF text and the chunk text.
- A bar above the viewer reads "Showing the passage from your search (page N)", with a **Clear highlight** button.
- If the text can't be matched, the viewer still opens at the page and the bar says the passage couldn't be highlighted. If the chunk has no page, the viewer opens at page 1 with no error.

## Acceptance criteria

- New uploads store `page_start` and `page_end` for every chunk. In a fixture PDF where a known sentence is on page 3, that sentence's chunk has `page_start = 3`
- For the fixture PDFs, chunk texts are byte-identical before and after this slice
- The backfill dry run changes nothing. `--apply` fills pages only where the regenerated chunks match, and lists the documents it skipped
- `/api/search` results include `page`
- The chunk endpoint returns 404 for another user's chunk and for a chunk of a different document
- Clicking a result opens the PDF at that page with the passage highlighted (checked by hand with `er-model.pdf` and `DBMS_UNIT2_MERGE.pdf`)
- A passage that spans two pages is highlighted on both
- A result without a page opens at page 1 without errors
- Tests cover the page mapping in the worker, the backfill matching rule, the endpoint's user scoping, the search result shape, and the frontend link and highlight logic (pdf.js mocked)

## Out of scope

- Stripping repeated slide headers and footers from chunks (sprint 7 open question 2)
- Highlighting the query words inside result snippets
- OCR for scanned PDFs

## Assigned To

Unassigned

## Human review required?

Yes. It adds a schema migration on `chunks` (non-destructive) and a backfill script that updates existing rows.
