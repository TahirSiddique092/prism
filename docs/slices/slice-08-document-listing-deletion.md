# slice-08 — Document listing and deletion with trigger

**Sprint:** 2 — Document pipeline
**Module:** documents

## What to build

`GET /api/documents` to list a user's documents, `GET /api/documents/:doc_id/url` to retrieve a secure view URL, and `DELETE /api/documents/:doc_id` to delete one. Deletion must cascade correctly via the trigger from slice-02.

## Endpoints

**GET /api/documents**
- Response: `[{ doc_id, title, uploaded_at, status, chunk_count }]`
- Only returns documents belonging to the authenticated user

**DELETE /api/documents/:doc_id**
- Deletes the document row from MySQL — trigger handles chunk and chunk_vector cleanup
- Deletes the file from MinIO
- Invalidates the user's Redis cache
- Response: `{ message: "deleted" }`
- Returns 404 if doc doesn't belong to the user

**GET /api/documents/:doc_id/url**
- Generates a temporary pre-signed URL from MinIO (e.g., 1-hour expiry)
- Response: `{ view_url: "..." }`
- Returns 404 if doc doesn't belong to the user

## Acceptance criteria

- `GET /api/documents` never returns documents from other users
- `DELETE` fires the MySQL trigger — `deletion_audit` gets a new row, `chunks` rows are removed, `chunk_vectors` rows are removed
- MinIO file is deleted after MySQL deletion succeeds
- Redis cache for the user is invalidated after deletion
- Deleting a non-existent or other user's doc returns 404, not 500
- `GET /api/documents/:doc_id/url` successfully returns a working pre-signed MinIO URL for the user's document

## Out of scope

- No bulk delete
- No restore / trash — deletion is permanent

## Assigned To

Dev B

## Human review required?

Yes — involves data deletion endpoint and trigger-based cascading deletes.
