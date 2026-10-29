# ADR-017 — Prepared statements for free-text MySQL queries

## Context

Uploading `DBMS_UNIT2_MERGE.pdf` failed with `1064 (42000): You have an error
in your SQL syntax`. The PDF contains trigger examples with `DELIMITER //` and
`DELIMITER ;` lines.

With a plain cursor, `mysql-connector-python` inlines parameters into the SQL
string on the client. Recent versions then search the *whole* statement, data
included, for `delimiter <word>`. If found, they treat the statement as a
script: they strip anything that looks like a comment (`--`, `#`), split it at
the delimiters, and rejoin it. Their quote tracking ignores escaped quotes
(`\'`), so a `delimiter` inside the data is often taken for a real command.
The result is either:

- a broken statement: the chunk `INSERT` for that PDF failed with 1064; or
- silently altered data: the search `what's the delimiter in codd's rules` was
  stored as `what's the;\ncodd's rules`.

`requirements.txt` only pins `>=8.0.0`, so the Docker image gets the latest
driver, which has this behaviour.

## Decision

Every query that carries free text (PDF chunks, document titles, topic names,
search queries, user name and email) uses a **server-side prepared statement**
(`conn.cursor(prepared=True)`). The values travel to MySQL separately from the
SQL text, so the driver never inlines or rewrites them.

- `insert_chunks` replaces `executemany()` with one prepared multi-row
  `INSERT` per 500 rows: one round trip per batch, far below MySQL's 65,535
  placeholder limit.
- `find_user_by_email` builds its dict from `cursor.column_names`, because
  prepared dictionary cursors are not available in every supported driver
  version.
- Queries whose parameters are only integers or fixed values (IDs, `status`,
  analytics) are unaffected and unchanged.

Pinning an older driver was rejected: it would freeze an outdated dependency,
and the problem would return on the next upgrade.

## Consequences

- Free text is stored exactly as given, whatever it contains.
- `backend/tests/test_mysql_prepared_statements.py` covers each query.
  Its integration tests (opt-in: `PRISM_MYSQL_INTEGRATION=1` plus `MYSQL_URL`)
  run against a real server using TEMPORARY tables that shadow the real ones,
  so nothing persistent is written.
- New queries that take user-supplied text must use `cursor(prepared=True)`.
