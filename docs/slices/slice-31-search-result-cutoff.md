# slice-31 — Drop weak search results

**Sprint:** 7 — Hardening and UX (resolves open question 1)
**Module:** search

## What to build

Vector search always returns the 10 nearest passages, however weak they are. Drop results that are too far from the query, so the list ends where the relevant passages end.

## Changes

**Problem:** On the course PDFs, "before insert trigger with delimiter" returns its trigger examples followed by a references slide (cosine distance 0.616) and an unrelated FULLTEXT slide (0.641). The FULLTEXT fallback only looks at the best match (> 0.75), so it never trims a weak tail.

**Change:**
- In `execute_semantic_search`, after the fallback check, drop vector matches with cosine distance above `RESULT_DISTANCE_CUTOFF = 0.60`. Always keep the best match.
- The value was measured offline on the 3 course PDFs (225 passages) and 15 queries. The table and reasoning are in ADR-020.
- The FULLTEXT fallback (best match > 0.75) is unchanged. FULLTEXT results aren't filtered.
- Mention the cutoff in AGENTS.md (stack rules), ADD.md, `docs/data/nosql-schema.md` and the README.

## Acceptance criteria

- Vector matches at 0.38, 0.45, 0.59, 0.61 and 0.70 return the first three. A match exactly at 0.60 is kept
- If the best match is between 0.60 and 0.75, exactly one result is returned and the FULLTEXT fallback isn't used
- If the best match is above 0.75, the FULLTEXT fallback runs as before
- Only the returned results are cached and logged to `search_results`
- ADR-020 records the measurements behind 0.60
- All existing tests still pass, and new tests cover each criterion above

## Out of scope

- Grouping results by document or removing overlapping passages
- Changing the 0.75 fallback threshold or the embedding model
- Making the cutoff configurable

## Assigned To

Unassigned

## Human review required?

No.
