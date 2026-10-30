# ADR-020 — Drop weak vector search results

## Context

Vector search always returned the 10 nearest passages, however weak. On the course PDFs, a precise question such as "before insert trigger with delimiter" listed a references slide (distance 0.616) and an unrelated FULLTEXT slide (0.641) after the trigger examples. AGENTS.md fixes the FULLTEXT fallback at a best distance of 0.75. That rule decides whether the vector results are usable at all, but it doesn't trim a weak tail when the best match is good.

## Measurements

Offline replica of the search: the same embedding model and the same chunking as production, on the 3 course PDFs (225 passages). Cosine distance is computed as pgvector's `<=>` does. Results kept out of the top 10 for each candidate cutoff (the best match is always kept):

| Query | Best | 0.55 | **0.60** | 0.65 |
|---|---|---|---|---|
| how do you map a weak entity to a table | 0.384 | 10 | **10** | 10 |
| before insert trigger with delimiter | 0.399 | 5 | **7** | 10 |
| what is a composite attribute | 0.362 | 6 | **10** | 10 |
| difference between a primary key and a foreign key | 0.469 | 3 | **9** | 10 |
| what is total participation in an ER diagram | 0.401 | 9 | **10** | 10 |
| how to map a many-to-many relationship to relations | 0.402 | 10 | **10** | 10 |
| what is a stored procedure | 0.274 | 5 | **10** | 10 |
| explain cardinality ratio | 0.478 | 4 | **7** | 9 |
| relational database | 0.337 | 10 | **10** | 10 |
| types of SQL joins | 0.319 | 10 | **10** | 10 |

Off-topic queries (photosynthesis, football, baking, gibberish) and a topic absent from the PDFs (normalization) all had a best distance of 0.77–0.93. The existing fallback already handles them.

- **0.55** drops relevant passages, for example the CREATE / DROP PROCEDURE examples at 0.553 and 0.554, and most results for keys and cardinality.
- **0.65** keeps the irrelevant FULLTEXT slide (0.641) and a weak-entity slide returned for "cardinality" (0.647).
- **0.60** drops 7 passages across these queries: 3 irrelevant, 3 marginal, 1 somewhat relevant ("types of participation", 0.629). Nothing relevant below 0.60 is lost.

## Decision

- After the fallback check, vector results with cosine distance **> 0.60** (similarity below 0.40) are dropped (`RESULT_DISTANCE_CUTOFF` in `search/service.py`).
- The **best match is always kept**. A query whose best match is between 0.60 and 0.75 gets that one result instead of none, and anything above 0.75 still goes to the FULLTEXT fallback, as before.
- FULLTEXT results have no distance and are not filtered.

## Consequences

- Searches return between 1 and 10 results. Only the returned results are logged, so analytics count fewer, more relevant appearances.
- Results cached before the change can be served until their 1-hour TTL ends.
- The value comes from 10 queries on one course's PDFs. It should be re-measured if the embedding model or the kind of documents changes.
