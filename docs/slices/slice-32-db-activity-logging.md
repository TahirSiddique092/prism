# slice-32 — Database activity logs in the backend terminal

**Sprint:** 8 — DBMS features and admin
**Module:** infra (logging), documents, analytics

## What to build

Whenever the backend uses a database object (a trigger, a stored procedure, a stored function or a view), print one clear line in the backend terminal (`docker compose logs -f backend`). The DBMS features can then be seen working during a demo. This slice sets up the logging and covers the existing trigger and view; slices 33–35 log the procedures and functions they add.

## Changes

### 1. Show INFO logs
**Problem:** The backend never configures logging, so every `logger.info(...)` call is dropped: Python's default level is WARNING. Only warnings, errors and Flask's request lines reach the terminal.

**Change:** configure logging once when the server starts (`backend/app.py`), at INFO level, with a timestamp and the logger name. The backend image already sets `PYTHONUNBUFFERED=1`, so lines appear immediately.

### 2. One helper, one format
Add `backend/modules/dblog.py` with `log_db_event(kind, name, **details)`. Every line starts with `[DB]`, followed by the kind (TRIGGER, PROCEDURE, FUNCTION or VIEW), the object's name, its details, the number of rows and the time taken:

```
[DB] TRIGGER   before_document_delete fired: doc_id=12 → deletion_audit.audit_id=7 (cascade removed 43 chunks)
[DB] VIEW      top_documents read: user_id=2 → 2 rows in 18 ms
[DB] PROCEDURE sp_search_history(user_id=2) → 3 rows in 21 ms                 (added by slice-33)
[DB] FUNCTION  fn_chunk_count in the document list: user_id=2 → 3 rows in 9 ms (added by slice-34)
```

Lines contain IDs, counts and timings only. They never contain passwords, tokens, email addresses, search text or document text.

### 3. Log the trigger
**Problem:** `before_document_delete` runs inside MySQL, so the backend never sees it fire.

**Change:** in `delete_document` (`backend/modules/documents/db.py`), on the same connection:
1. count the document's chunks before the `DELETE` (the cascade removes them);
2. run the `DELETE`;
3. read the newest `deletion_audit` row for that `doc_id`.

Log a TRIGGER line with the new `audit_id` and the number of chunks the cascade removed. If no audit row was written, log a WARNING that the trigger did not fire. These extra queries are best-effort: if they fail, the delete still succeeds and a warning is logged.

### 4. Log the view
`get_top_documents` (`backend/modules/analytics/db.py`) logs a VIEW line each time it reads `top_documents`.

### 5. Keep search text out of the existing INFO lines
**Problem:** Once INFO is visible, two existing lines in `search/service.py` (cache hit and FULLTEXT fallback) would print the user's search text.

**Change:** they log the user ID instead (and the query length for a cache hit).

## Acceptance criteria

- Deleting a document prints a `[DB] TRIGGER` line with the `doc_id`, the new `deletion_audit.audit_id` and the number of chunks removed by the cascade
- If no `deletion_audit` row appears after a delete, a WARNING line says the trigger did not fire
- If the extra trigger-check queries fail, the delete still returns 200
- Opening Top Documents prints a `[DB] VIEW` line with the user ID, the row count and the time
- INFO lines that already exist in the backend (for example the FULLTEXT fallback message) now appear in `docker compose logs`
- No `[DB]` line contains a password, token, email address, search text or document text
- The cache-hit and FULLTEXT-fallback INFO lines don't contain the search text
- Tests capture the log output (pytest `caplog`) and check each line above

## Out of scope

- Logging every SQL statement
- Log files, log rotation, or sending logs anywhere else
- MySQL's own server-side logs (`general_log`)

## Assigned To

Unassigned

## Human review required?

No.
