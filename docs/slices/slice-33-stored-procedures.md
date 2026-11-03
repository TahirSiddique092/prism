# slice-33 — Stored procedures for the analytics queries

**Sprint:** 8 — DBMS features and admin
**Module:** analytics, infra (migrations)
**Depends on:** slice-32 (logging helper)

## What to build

Move two analytics queries into MySQL stored procedures and call them from the backend. The API responses stay exactly the same.

| Procedure | Query it holds | Used by |
|---|---|---|
| `sp_search_history(IN p_user_id INT)` | The search-history query with window functions (`RANK() OVER`, `SUM(COUNT(*)) OVER ()`) | `GET /api/analytics/history` |
| `sp_unsearched_documents(IN p_user_id INT)` | The unsearched-documents query with a CTE (`WITH searched_docs AS …`) | `GET /api/analytics/unsearched` |

## Changes

### 1. Let the migration runner create routines
**Problem:** `backend/db/migrate.py` only runs the first `DELIMITER // … //` block of a migration file, so one file can hold at most one trigger, procedure or function.

**Change:**
- Run every `DELIMITER` block in a file, in order.
- Write each routine as `DROP PROCEDURE IF EXISTS …` followed by `CREATE PROCEDURE …`, so applying a migration again is safe.
- Keep tolerating "trigger already exists" (1304), as today.

### 2. Migration `008_stored_procedures.sql`
Create both procedures. Inside their bodies, quote strings with single quotes: Aiven runs MySQL with `ANSI_QUOTES`, where double quotes mean identifiers.

### 3. Call them from the backend
- `get_search_history` and `get_unsearched_documents` (`backend/modules/analytics/db.py`) call the procedures with `cursor.callproc(...)` and read the result with `stored_results()`.
- The procedures take only integer arguments, so ADR-017 (prepared statements for free text) is not affected.
- Each call logs a `[DB] PROCEDURE` line (slice-32).

### 4. Docs
- In `docs/data/relational-schema.md`, add a "Stored procedures" part next to the trigger and view (§ 5), and update the analytics entries under Key queries (§ 7).
- Add a short ADR on why these two queries became procedures and how they are called.

## Acceptance criteria

- After migrating, `SHOW PROCEDURE STATUS WHERE Db = DATABASE()` lists `sp_search_history` and `sp_unsearched_documents`
- For the same data, `/api/analytics/history` and `/api/analytics/unsearched` return exactly the same JSON as before
- Each call prints a `[DB] PROCEDURE` line with the procedure name, the user ID, the row count and the time
- Applying the migration a second time does not fail
- A migration file with two `DELIMITER` blocks creates both routines (unit test of the runner's parsing)
- An opt-in integration test (`PRISM_MYSQL_INTEGRATION=1`) calls both procedures on a real MySQL server, using TEMPORARY tables (procedures can see a session's temporary tables), and compares the output with the old inline queries
- All existing tests still pass

## Out of scope

- Moving other queries into procedures
- Procedures that take free-text arguments
- Changing what the analytics pages show

## Assigned To

Unassigned

## Human review required?

Yes. It changes the migration runner (infra) and adds a schema migration.
