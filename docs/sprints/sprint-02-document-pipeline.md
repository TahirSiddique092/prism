# Sprint-02-document-pipeline

> A sprint is a feature-level chunk of the Architecture — sized to however much you'll realistically tackle in one work block (a few hours, an all-nighter, a weekend). Not tied to a calendar week.

## Goal

Users can upload PDFs which are stored in MinIO, parsed into sentence-boundary chunks, embedded into pgvector, and listed/deleted via the API.

## Slices in this sprint

- [ ]  `slice-05-minio-file-upload` — MinIO integration and file upload — **Dev A**
- [ ]  `slice-06-pdf-chunking` — PDF parsing and sentence-boundary chunking — **Dev A**
- [ ]  `slice-07-embedding-pgvector` — Embedding and pgvector insert — **Dev A**
- [ ]  `slice-08-document-listing-deletion` — Document listing and deletion with trigger — **Dev B**

## Depends on

Sprint 1 — auth middleware and database schemas must exist.

## Notes for next time

*(Leave blank unless something actually broke, a slice was mis-sized, or the agent went off-script.)*
