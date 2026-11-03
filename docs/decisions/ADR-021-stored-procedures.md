# ADR-021 — Stored procedures for the analytics queries

## Context

The project guide asked for stored procedures. The two analytics queries with the most SQL in them were run as inline SQL from `backend/modules/analytics/db.py`: search history (window functions) and unsearched documents (a CTE). Separately, the migration runner could only create one trigger or routine per file, because it ran just the first `DELIMITER //` block.

## Decision

- **`sp_search_history(IN p_user_id INT)` and `sp_unsearched_documents(IN p_user_id INT)`** hold those queries unchanged (migration 008). The backend calls them with `cursor.callproc` and reads the rows by column name. An integration test compares them with the old inline queries for every user.
- **Integer arguments only.** No free text passes through `callproc`, so the client-side rewriting described in ADR-017 cannot affect these calls.
- **Each call logs a `[DB] PROCEDURE` line** with the user ID, the row count and the time (slice-32).
- **The migration runner** now splits a MySQL script into ordered statements and runs any number of `DELIMITER` blocks. Each routine is written as `DROP … IF EXISTS` followed by `CREATE`, so a migration can be applied again.
- **`migrate.py` loads `.env` only when run as a script.** Importing it, as the new runner tests do, used to copy every value from `.env`, secrets included, into the importing process.
- **mysql-connector compatibility:** newer releases deprecate `stored_results()` as a method and will turn it into a property, so the code accepts both.

## Consequences

- The SQL for these two pages lives in the database. Changing it means writing a new migration, not editing Python.
- Inside a `DELIMITER` block, `//` ends a statement, so it must not appear in comments or strings there.
