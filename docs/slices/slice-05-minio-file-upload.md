# slice-05 — MinIO integration and file upload

**Sprint:** 2 — Document pipeline
**Module:** documents

## What to build

Wire MinIO into Flask using `boto3`. Accept a PDF file from the client, validate it, and store it in MinIO. Return a `minio_key` that the rest of the pipeline uses to retrieve the file.

## Acceptance criteria

- MinIO bucket `prism-documents` is created on startup if it doesn't exist
- `POST /api/documents/upload` accepts `multipart/form-data` with a `file` field and a `topics[]` field
- Only `.pdf` files accepted — return 400 for any other type
- File is stored in MinIO under key `{user_id}/{uuid4}.pdf`
- Document metadata row inserted into MySQL `documents` table with `minio_key` stored
- Response returns `{ doc_id, minio_key }` immediately — chunking is async (handled in slice-06/07)
- File size limit: 20MB — return 413 if exceeded

## Out of scope

- No chunking or embedding here — that's slice-06 and slice-07
- No topic linking to Neo4j yet — that's slice-12

## Assigned To

Dev A

## Human review required?

No.
