# slice-06 — PDF parsing and sentence-boundary chunking

**Sprint:** 2 — Document pipeline
**Module:** documents

## What to build

A background task that retrieves a PDF from MinIO, extracts its text using PyMuPDF, splits it into sentence-boundary-aware chunks using `nltk.sent_tokenize`, and inserts the raw chunks into MySQL `chunks` table.

## Chunking rules

- Use `nltk.sent_tokenize` to split text into sentences first
- Accumulate sentences into a chunk until word count reaches ~200
- Carry over the last 1–2 sentences of each chunk into the next (overlap)
- Skip chunks with fewer than 20 words (headers, page numbers, etc.)

## Acceptance criteria

- Given a 10-page PDF, the task produces chunks stored in MySQL `chunks` table with correct `doc_id` and `chunk_index`
- No chunk exceeds 250 words
- Overlap of 1–2 sentences exists between consecutive chunks
- Chunks shorter than 20 words are discarded
- Task is triggered automatically after slice-05 stores the file (use Python `threading.Thread` for async — no Celery needed)
- If parsing fails (corrupt PDF, no text layer), `documents.status` is set to `error` and the failure is logged

## Out of scope

- No embedding here — that's slice-07
- No support for scanned/image PDFs

## Assigned To

Dev A

## Human review required?

No.
