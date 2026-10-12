# ADR-001 — Index tuning and EXPLAIN analysis (slice-21)

## Context

In Sprint 6 (Polish and deployment), query performance was evaluated on the two most expensive relational database queries in PRISM:
1. The `search_log` history query with window functions (`RANK() OVER ...` and `SUM(COUNT(*)) OVER ...`) from `backend/modules/analytics/db.py`.
2. The `search_results` multi-table join chain used in the unsearched documents Common Table Expression (CTE) from `backend/modules/analytics/db.py`.

Without proper index coverage, both queries perform full table scans across user boundaries or during relational join traversal.

Per slice-21 requirements:
- `EXPLAIN` and `EXPLAIN ANALYZE` outputs are captured before and after indexing.
- Estimated rows scanned must decrease for both queries.
- No speculative indexes are added — only targeting the two queries.
- No query rewriting or pgvector index changes are introduced.

---

## 1. Query 1: Search History Query (Window Function)

### Query Definition
```sql
SELECT
    query_text,
    COUNT(*)                                             AS search_count,
    RANK() OVER (ORDER BY COUNT(*) DESC)                 AS query_rank,
    MAX(searched_at)                                     AS last_searched,
    SUM(COUNT(*)) OVER ()                                AS total_searches
FROM search_log
WHERE user_id = 1
GROUP BY query_text
ORDER BY query_rank;
```

### Problem
Without an index on `user_id`, evaluating `WHERE user_id = ?` requires scanning every record in `search_log`, across all users.

### Index Solution
The composite index `idx_search_log_user_time ON search_log(user_id, searched_at)` was defined in `backend/db/migrations/001_init.sql` (slice-02).

### Before Index (Full Table Scan)
#### Tabular EXPLAIN:
```
id | select_type | table      | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                                       
---+-------------+------------+------------+------+---------------+------+---------+------+------+----------+---------------------------------------------
1  | SIMPLE      | search_log | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 500  | 20.0     | Using where; Using temporary; Using filesort
```

#### EXPLAIN ANALYZE:
```text
-> Sort: query_rank  (actual time=0.593..0.594 rows=10 loops=1)
    -> Table scan on <temporary>  (cost=2.5..2.5 rows=0) (actual time=0.555..0.557 rows=10 loops=1)
        -> Temporary table  (cost=0..0 rows=0) (actual time=0.555..0.555 rows=10 loops=1)
            -> Window aggregate with buffering: sum(`count(0)`) OVER ()   (actual time=0.543..0.547 rows=10 loops=1)
                -> Table scan on <temporary>  (cost=2.5..2.5 rows=0) (actual time=0.515..0.516 rows=10 loops=1)
                    -> Temporary table  (cost=0..0 rows=0) (actual time=0.515..0.515 rows=10 loops=1)
                        -> Window aggregate: rank() OVER (ORDER BY search_count desc )   (actual time=0.502..0.508 rows=10 loops=1)
                            -> Sort: search_count DESC  (actual time=0.497..0.498 rows=10 loops=1)
                                -> Table scan on <temporary>  (actual time=0.477..0.479 rows=10 loops=1)
                                    -> Aggregate using temporary table  (actual time=0.476..0.476 rows=10 loops=1)
                                        -> Filter: (search_log.user_id = 1)  (cost=51 rows=100) (actual time=0.0456..0.292 rows=100 loops=1)
                                            -> Table scan on search_log  (cost=51 rows=500) (actual time=0.043..0.257 rows=500 loops=1)
```

### After Index (`idx_search_log_user_time`)
#### Tabular EXPLAIN:
```
id | select_type | table      | partitions | type | possible_keys            | key                      | key_len | ref   | rows | filtered | Extra                          
---+-------------+------------+------------+------+--------------------------+--------------------------+---------+-------+------+----------+--------------------------------
1  | SIMPLE      | search_log | NULL       | ref  | idx_search_log_user_time | idx_search_log_user_time | 4       | const | 100  | 100.0    | Using temporary; Using filesort
```

#### EXPLAIN ANALYZE:
```text
-> Sort: query_rank  (actual time=0.31..0.311 rows=10 loops=1)
    -> Table scan on <temporary>  (cost=2.5..2.5 rows=0) (actual time=0.303..0.304 rows=10 loops=1)
        -> Temporary table  (cost=0..0 rows=0) (actual time=0.302..0.302 rows=10 loops=1)
            -> Window aggregate with buffering: sum(`count(0)`) OVER ()   (actual time=0.295..0.298 rows=10 loops=1)
                -> Table scan on <temporary>  (cost=2.5..2.5 rows=0) (actual time=0.276..0.277 rows=10 loops=1)
                    -> Temporary table  (cost=0..0 rows=0) (actual time=0.276..0.276 rows=10 loops=1)
                        -> Window aggregate: rank() OVER (ORDER BY search_count desc )   (actual time=0.268..0.273 rows=10 loops=1)
                            -> Sort: search_count DESC  (actual time=0.265..0.266 rows=10 loops=1)
                                -> Table scan on <temporary>  (actual time=0.252..0.253 rows=10 loops=1)
                                    -> Aggregate using temporary table  (actual time=0.251..0.251 rows=10 loops=1)
                                        -> Index lookup on search_log using idx_search_log_user_time (user_id=1)  (cost=13 rows=100) (actual time=0.0209..0.126 rows=100 loops=1)
```

### Query 1 Results Summary
| Metric | Before Index | After Index | Improvement |
| :--- | :--- | :--- | :--- |
| **Access Type** | `ALL` (Full Table Scan) | `ref` (`idx_search_log_user_time`) | Point index lookup |
| **Estimated Rows Scanned** | **500** rows | **100** rows | **80.0% reduction** |
| **Filtered Percentage** | 20.0% | 100.0% | 5x precision |
| **Optimizer Cost** | 51.0 | 13.0 | **74.5% reduction** |
| **Execution Time** | ~0.59 ms | ~0.31 ms | **47.5% faster** |

---

## 2. Query 2: Search Results Join Chain (Unsearched Docs CTE)

### Query Definition
```sql
WITH searched_docs AS (
    SELECT DISTINCT d.doc_id
    FROM search_results sr
    JOIN chunks c ON sr.chunk_id = c.chunk_id
    JOIN documents d ON c.doc_id = d.doc_id
    JOIN search_log sl ON sr.log_id = sl.log_id
    WHERE sl.user_id = 1
)
SELECT doc_id, title, uploaded_at
FROM documents
WHERE user_id = 1
  AND doc_id NOT IN (SELECT doc_id FROM searched_docs);
```

### Problem
In the CTE `searched_docs`, joining `search_results` (`sr`) without secondary indexes forces MySQL to scan the entire `search_results` table (`type: ALL`, 2,500 rows) and join back to `search_log` via single-row primary key lookups 2,500 times.

### Index Solution
Added explicit indexes in migration `backend/db/migrations/004_index_tuning.sql`:
- `CREATE INDEX idx_search_results_log_id ON search_results(log_id);`
- `CREATE INDEX idx_search_results_chunk_id ON search_results(chunk_id);`

### Before Index (Full Table Scan on `search_results`)
#### Tabular EXPLAIN:
```
id | select_type | table      | partitions | type   | possible_keys                    | key         | key_len | ref                    | rows | filtered | Extra                               
---+-------------+------------+------------+--------+----------------------------------+-------------+---------+------------------------+------+----------+-------------------------------------
1  | PRIMARY     | documents  | NULL       | ref    | user_id                          | user_id     | 4       | const                  | 20   | 100.0    | NULL                                
1  | PRIMARY     | <derived3> | NULL       | ref    | <auto_key0>                      | <auto_key0> | 4       | prism.documents.doc_id | 10   | 100.0    | Using where; Not exists; Using index
3  | DERIVED     | sr         | NULL       | ALL    | NULL                             | NULL        | NULL    | NULL                   | 2500 | 100.0    | Using temporary                     
3  | DERIVED     | sl         | NULL       | eq_ref | PRIMARY,idx_search_log_user_time | PRIMARY     | 4       | prism.sr.log_id        | 1    | 20.0     | Using where                         
3  | DERIVED     | c          | NULL       | eq_ref | PRIMARY,doc_id                   | PRIMARY     | 4       | prism.sr.chunk_id      | 1    | 100.0    | NULL                                
3  | DERIVED     | d          | NULL       | eq_ref | PRIMARY,user_id                  | PRIMARY     | 4       | prism.c.doc_id         | 1    | 100.0    | Using index                         
```

#### EXPLAIN ANALYZE:
```text
-> Nested loop antijoin  (cost=1053 rows=10000) (actual time=2.57..2.57 rows=0 loops=1)
    -> Index lookup on documents using user_id (user_id=1)  (cost=2.75 rows=20) (actual time=0.0281..0.0478 rows=20 loops=1)
    -> Covering index lookup on searched_docs using <auto_key0> (doc_id=documents.doc_id)  (cost=1588..1611 rows=10) (actual time=0.126..0.126 rows=1 loops=20)
        -> Materialize CTE searched_docs  (cost=1586..1586 rows=500) (actual time=2.51..2.51 rows=100 loops=1)
            -> Table scan on <temporary>  (cost=1527..1536 rows=500) (actual time=2.43..2.44 rows=100 loops=1)
                -> Temporary table with deduplication  (cost=1527..1527 rows=500) (actual time=2.43..2.43 rows=100 loops=1)
                    -> Nested loop inner join  (cost=1477 rows=500) (actual time=0.0707..2.33 rows=500 loops=1)
                        -> Nested loop inner join  (cost=1302 rows=500) (actual time=0.067..2.11 rows=500 loops=1)
                            -> Nested loop inner join  (cost=1127 rows=500) (actual time=0.0622..1.7 rows=500 loops=1)
                                -> Table scan on sr  (cost=252 rows=2500) (actual time=0.0524..0.513 rows=2500 loops=1)
                                -> Filter: (sl.user_id = 1)  (cost=0.25 rows=0.2) (actual time=364e-6..379e-6 rows=0.2 loops=2500)
                                    -> Single-row index lookup on sl using PRIMARY (log_id=sr.log_id)  (cost=0.25 rows=1) (actual time=208e-6..233e-6 rows=1 loops=2500)
                            -> Single-row index lookup on c using PRIMARY (chunk_id=sr.chunk_id)  (cost=0.25 rows=1) (actual time=665e-6..688e-6 rows=1 loops=500)
                        -> Single-row covering index lookup on d using PRIMARY (doc_id=c.doc_id)  (cost=0.25 rows=1) (actual time=293e-6..315e-6 rows=1 loops=500)
```

### After Index (`idx_search_results_log_id`, `idx_search_results_chunk_id`)
#### Tabular EXPLAIN:
```
id | select_type | table      | partitions | type   | possible_keys                                         | key                       | key_len | ref                    | rows | filtered | Extra                               
---+-------------+------------+------------+--------+-------------------------------------------------------+---------------------------+---------+------------------------+------+----------+-------------------------------------
1  | PRIMARY     | documents  | NULL       | ref    | user_id                                               | user_id                   | 4       | const                  | 20   | 100.0    | NULL                                
1  | PRIMARY     | <derived3> | NULL       | ref    | <auto_key0>                                           | <auto_key0>               | 4       | prism.documents.doc_id | 10   | 100.0    | Using where; Not exists; Using index
3  | DERIVED     | sl         | NULL       | ref    | PRIMARY,idx_search_log_user_time                      | idx_search_log_user_time  | 4       | const                  | 100  | 100.0    | Using index; Using temporary        
3  | DERIVED     | sr         | NULL       | ref    | idx_search_results_log_id,idx_search_results_chunk_id | idx_search_results_log_id | 4       | prism.sl.log_id        | 5    | 100.0    | NULL                                
3  | DERIVED     | c          | NULL       | eq_ref | PRIMARY,doc_id                                        | PRIMARY                   | 4       | prism.sr.chunk_id      | 1    | 100.0    | NULL                                
3  | DERIVED     | d          | NULL       | eq_ref | PRIMARY,user_id                                       | PRIMARY                   | 4       | prism.c.doc_id         | 1    | 100.0    | Using index                         
```

#### EXPLAIN ANALYZE:
```text
-> Nested loop antijoin  (cost=1053 rows=10000) (actual time=1.7..1.7 rows=0 loops=1)
    -> Index lookup on documents using user_id (user_id=1)  (cost=2.75 rows=20) (actual time=0.0288..0.0425 rows=20 loops=1)
    -> Covering index lookup on searched_docs using <auto_key0> (doc_id=documents.doc_id)  (cost=647..670 rows=10) (actual time=0.0826..0.0826 rows=1 loops=20)
        -> Materialize CTE searched_docs  (cost=644..644 rows=500) (actual time=1.64..1.64 rows=100 loops=1)
            -> Table scan on <temporary>  (cost=585..594 rows=500) (actual time=1.59..1.6 rows=100 loops=1)
                -> Temporary table with deduplication  (cost=585..585 rows=500) (actual time=1.58..1.58 rows=100 loops=1)
                    -> Nested loop inner join  (cost=535 rows=500) (actual time=0.0452..1.48 rows=500 loops=1)
                        -> Nested loop inner join  (cost=360 rows=500) (actual time=0.0423..1.21 rows=500 loops=1)
                            -> Nested loop inner join  (cost=185 rows=500) (actual time=0.0372..0.731 rows=500 loops=1)
                                -> Covering index lookup on sl using idx_search_log_user_time (user_id=1)  (cost=10.3 rows=100) (actual time=0.0164..0.0291 rows=100 loops=1)
                                -> Index lookup on sr using idx_search_results_log_id (log_id=sl.log_id)  (cost=1.25 rows=5) (actual time=0.0058..0.00658 rows=5 loops=100)
                            -> Single-row index lookup on c using PRIMARY (chunk_id=sr.chunk_id)  (cost=0.25 rows=1) (actual time=757e-6..786e-6 rows=1 loops=500)
                        -> Single-row covering index lookup on d using PRIMARY (doc_id=c.doc_id)  (cost=0.25 rows=1) (actual time=352e-6..382e-6 rows=1 loops=500)
```

### Query 2 Results Summary
| Metric | Before Index | After Index | Improvement |
| :--- | :--- | :--- | :--- |
| **Join Driving Order** | `sr` -> `sl` -> `c` -> `d` | `sl` -> `sr` -> `c` -> `d` | Filtered by user first |
| **`search_results` Access Type** | `ALL` (Full Table Scan) | `ref` (`idx_search_results_log_id`) | Targeted index lookup |
| **Estimated Rows Scanned (`sr`)** | **2,500** rows | **5** rows per log (500 total) | **80.0% reduction** |
| **CTE Materialization Cost** | 1,586.0 | 644.0 | **59.4% reduction** |
| **CTE Inner Join Cost** | 1,477.0 | 535.0 | **63.8% reduction** |
| **Execution Time** | ~2.57 ms | ~1.70 ms | **33.9% faster** |

---

## Decision

1. **Keep `idx_search_log_user_time` on `search_log(user_id, searched_at)`**: Created in `001_init.sql`, this index prevents full table scans on `search_log` and enables both Query 1 and Query 2 to filter by user at the start of execution.
2. **Add `idx_search_results_log_id` and `idx_search_results_chunk_id`**: Created in `backend/db/migrations/004_index_tuning.sql`. This allows the query planner to invert the join order in the CTE, using `log_id` to join directly to `search_results` and eliminating full table scans on `search_results`.
3. **No Speculative Indexing**: No other indexes were added. No query rewriting or pgvector index changes were made, in accordance with the slice boundaries.

## Status

Accepted.
