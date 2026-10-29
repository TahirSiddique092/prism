# slice-25 — Analytics accuracy

**Sprint:** 7 — Hardening and UX
**Module:** analytics, search, documents, frontend

## What to build

The analytics queries add up correctly, but the pages mislead in four ways, and one list includes documents it shouldn't. All five were found by testing against live data on 29 Oct 2026.

## Changes

### 1. Show times in the viewer's time zone
**Problem:** MySQL stores `TIMESTAMP` values in UTC. The API sends them without a time zone, e.g. `"2026-10-29T16:00:09"`, so the browser reads them as local time. In India every time shows 5 h 30 min early: a search made at 9:30 PM appears as 4:00 PM. This affects `last_searched` (Search History) and `uploaded_at` (document list, document detail, Unsearched Documents).

**Change:**
- In `get_db_config` (`backend/modules/auth/db.py`), set the session time zone to UTC (`"time_zone": "+00:00"`). `TIMESTAMP` values then always come back in UTC, whatever the server's setting.
- Add one small shared helper (e.g. `backend/modules/timeutils.py`, `to_utc_iso(value)`) that turns a naive UTC `datetime` into ISO 8601 with a `Z` suffix. Use it everywhere `last_searched` and `uploaded_at` are serialised.
- Dates are formatted only in the browser, never during server rendering (the containers run in UTC).

### 2. Don't count restored searches
**Problem:** The search page runs the query in the URL (`/search?q=…`) every time it mounts. Opening a result and pressing Back therefore runs and logs the same search again: +1 to the search count and up to +10 passage appearances. Confirmed in a browser walk-through.

**Change:**
- `POST /api/search` accepts an optional `"log": false`. The search still runs and still uses the cache, but nothing is written to `search_log` or `search_results`. Without the field, behaviour is unchanged.
- The search page sends `log: true` only for a search the user submits (Enter or the Search button, including submitting the same query again). Restoring results on Back/Forward, on reload, or from an opened `/search?q=` link sends `log: false`.

### 3. Count searches, not passages, in Top Documents
**Problem:** `appearance_count` counts `search_results` rows, which are passages. Each search stores up to 10 passages, so one search can add 10 to a single document, and documents with more passages rank higher. On the 29 Oct data, `er-model.pdf` had 25 "appearances" from only 3 searches (10 + 10 + 5).

**Change:**
- Migration `006_top_documents_search_count.sql` recreates the `top_documents` view with an extra column. `appearance_count` and `avg_score` stay as they are:
  ```sql
  COUNT(DISTINCT sr.log_id) AS search_count
  ```
- `get_top_documents` orders by `search_count DESC, appearance_count DESC`, and the API response gains `search_count`.
- The Top Documents page shows "in N searches" as the main figure and "M passages" as the secondary one.
- Update the view definition in `docs/data/relational-schema.md`.

### 4. One score scale
**Problem:** The Search page shows the raw cosine distance (lower is better, e.g. `0.3844`). Top Documents shows similarity (`1 − distance`, higher is better). The same match therefore looks different on the two pages. The column `search_results.similarity_score` also actually holds the distance.

**Change:**
- The Search page shows similarity (`1 − score`), with the tooltip "Cosine similarity — higher is closer". The API is unchanged: it still returns the distance, and `null` for FULLTEXT results.
- Note in `docs/data/relational-schema.md` that `similarity_score` holds the cosine distance. The column is not renamed: that would be a destructive migration with no change in behaviour.

### 5. Leave out documents that cannot be searched
**Problem:** `/api/analytics/unsearched` lists documents that are still `processing` or have failed (`error`). They can never appear in results, yet the page asks the user to search for them.

**Change:** add `AND status = 'ready'` to `UNSEARCHED_DOCS_QUERY`.

## Acceptance criteria

- Whatever the MySQL server's time zone, every `last_searched` and `uploaded_at` in API responses ends in `Z` and equals the stored UTC instant
- In a browser set to Asia/Kolkata, a search made at 21:30 IST shows as "9:30 PM" on Search History
- `POST /api/search` with `"log": false` returns results and adds no row to `search_log` or `search_results`; without the field it adds exactly one `search_log` row, as today
- Opening a result and pressing Back shows the same results and adds no `search_log` row; submitting a query adds exactly one
- `top_documents` has a `search_count` column. A document whose passages appeared 10, 10 and 5 times across three searches has `search_count = 3` and `appearance_count = 25`
- Top Documents is ordered by `search_count` and shows both numbers
- A stored distance of 0.4634 is shown as 0.5366 on both the Search page and Top Documents
- A document in `processing` or `error` never appears in `/api/analytics/unsearched`
- All existing tests still pass, and new tests cover each criterion above

## Out of scope

- No change to search ranking or to the number of results (see sprint 7 open question 1)
- No renaming of `search_results.similarity_score`
- No new analytics pages

## Assigned To

Unassigned

## Human review required?

Yes. It changes `get_db_config` in the auth module (the time zone setting only).
