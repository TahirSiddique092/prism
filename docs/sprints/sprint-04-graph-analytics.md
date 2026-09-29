# Sprint-04-graph-analytics

> A sprint is a feature-level chunk of the Architecture — sized to however much you'll realistically tackle in one work block (a few hours, an all-nighter, a weekend). Not tied to a calendar week.

## Goal

Neo4j topic graph populated on upload, related documents queryable via Cypher, and analytics endpoints serving search history (window functions), unsearched documents (CTE), and top documents (SQL view).

## Slices in this sprint

- [ ]  `slice-12-neo4j-topic-graph` — Neo4j topic graph on upload — **Dev A**
- [ ]  `slice-13-related-documents` — Related documents via Cypher — **Dev A**
- [ ]  `slice-14-analytics-search-history` — Analytics search history with window functions — **Dev B**
- [ ]  `slice-15-analytics-unsearched-topdocs` — Analytics unsearched docs CTE and top documents view — **Dev B**

## Depends on

- Sprint 2 — document upload pipeline (for graph writes on upload)
- Sprint 3 — search logging (for analytics queries over search_log and search_results)

## Notes for next time

*(Leave blank unless something actually broke, a slice was mis-sized, or the agent went off-script.)*
