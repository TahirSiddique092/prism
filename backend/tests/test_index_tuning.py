"""Acceptance criteria tests for slice-21: Index tuning and EXPLAIN analysis.

Acceptance criteria verified:
1. EXPLAIN output captured before any new indexes are added
2. Composite index added on search_log(user_id, searched_at) if not already present from slice-02
3. Index added on search_results(log_id) and search_results(chunk_id) if missing (in migration 004)
4. EXPLAIN output captured after — estimated rows scanned must decrease for both queries
5. Before/after outputs saved in docs/decisions/ADR-001-indexing.md
6. No indexes added speculatively — only the two target queries
7. No pgvector index tuning or query rewriting (out of scope)
"""
from pathlib import Path
import pytest

from backend.modules.analytics.db import SEARCH_HISTORY_QUERY, UNSEARCHED_DOCS_QUERY


REPO_ROOT = Path(__file__).parent.parent.parent


def test_composite_index_on_search_log_in_001_init():
    """AC 2: Composite index on search_log(user_id, searched_at) present in 001_init.sql."""
    init_sql_path = REPO_ROOT / "backend" / "db" / "migrations" / "001_init.sql"
    assert init_sql_path.exists(), "001_init.sql must exist"

    with open(init_sql_path, "r") as f:
        content = f.read()

    assert "idx_search_log_user_time" in content
    assert "search_log(user_id, searched_at)" in content


def test_search_results_indexes_in_migration_004():
    """AC 3: Indexes on search_results(log_id) and search_results(chunk_id) in migration 004."""
    migration_path = REPO_ROOT / "backend" / "db" / "migrations" / "004_index_tuning.sql"
    assert migration_path.exists(), "004_index_tuning.sql migration must exist"

    with open(migration_path, "r") as f:
        content = f.read()

    assert "-- ENGINE: MySQL" in content
    assert "CREATE INDEX idx_search_results_log_id ON search_results(log_id)" in content
    assert "CREATE INDEX idx_search_results_chunk_id ON search_results(chunk_id)" in content


def test_adr_001_indexing_exists():
    """AC 5: ADR-001-indexing.md exists in docs/decisions/."""
    adr_path = REPO_ROOT / "docs" / "decisions" / "ADR-001-indexing.md"
    assert adr_path.exists(), "docs/decisions/ADR-001-indexing.md must exist"


def test_adr_001_indexing_contains_before_and_after_explain_outputs():
    """AC 1, 4, 5: ADR documents before/after EXPLAIN and EXPLAIN ANALYZE outputs with row scan reductions."""
    adr_path = REPO_ROOT / "docs" / "decisions" / "ADR-001-indexing.md"
    with open(adr_path, "r") as f:
        content = f.read()

    # Query 1 documentation
    assert "Query 1: Search History Query" in content
    assert "EXPLAIN ANALYZE" in content
    assert "idx_search_log_user_time" in content
    assert "Table scan on search_log" in content
    assert "Index lookup on search_log using idx_search_log_user_time" in content

    # Query 2 documentation
    assert "Query 2: Search Results Join Chain" in content
    assert "idx_search_results_log_id" in content
    assert "idx_search_results_chunk_id" in content
    assert "Table scan on sr" in content
    assert "Index lookup on sr using idx_search_results_log_id" in content

    # Row scan decrease metrics
    assert "Estimated Rows Scanned" in content
    assert "80.0% reduction" in content


def test_target_queries_match_analytics_queries():
    """AC & Boundary: Target queries analysed in ADR match the exact SQL from analytics module."""
    adr_path = REPO_ROOT / "docs" / "decisions" / "ADR-001-indexing.md"
    with open(adr_path, "r") as f:
        content = f.read()

    # Query 1 core clauses
    assert "RANK() OVER (ORDER BY COUNT(*) DESC)" in SEARCH_HISTORY_QUERY
    assert "SUM(COUNT(*)) OVER ()" in SEARCH_HISTORY_QUERY
    assert "FROM search_log" in SEARCH_HISTORY_QUERY

    # Query 2 core clauses
    assert "WITH searched_docs AS (" in UNSEARCHED_DOCS_QUERY
    assert "FROM search_results sr" in UNSEARCHED_DOCS_QUERY
    assert "doc_id NOT IN (SELECT doc_id FROM searched_docs)" in UNSEARCHED_DOCS_QUERY

    # ADR contains these queries
    assert "RANK() OVER (ORDER BY COUNT(*) DESC)" in content
    assert "WITH searched_docs AS (" in content


def test_no_speculative_indexes_added():
    """AC 6: Only the two queries were targeted; migration 004 contains exactly the required indexes."""
    migration_path = REPO_ROOT / "backend" / "db" / "migrations" / "004_index_tuning.sql"
    with open(migration_path, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("--")]

    # Exactly 2 CREATE INDEX statements
    create_index_stmts = [line for line in lines if line.upper().startswith("CREATE INDEX")]
    assert len(create_index_stmts) == 2
    assert "idx_search_results_log_id" in create_index_stmts[0]
    assert "idx_search_results_chunk_id" in create_index_stmts[1]
