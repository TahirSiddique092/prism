"""Slice 25: analytics accuracy.

1. Timestamps go out as UTC marked with "Z" (the MySQL session is pinned to UTC)
2. POST /api/search with "log": false runs the search without logging it
3. top_documents counts searches (search_count) as well as passages
4. Unsearched documents only lists documents that are 'ready'

Unit tests use mocks. The integration tests at the bottom are opt-in
(PRISM_MYSQL_INTEGRATION=1 plus MYSQL_URL) and only touch TEMPORARY tables,
which shadow the real ones for that one connection.
"""
import datetime
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app import create_app
from backend.modules.analytics.db import (
    UNSEARCHED_DOCS_QUERY,
    get_search_history,
    get_unsearched_documents,
)
from backend.modules.auth.db import get_db_config
from backend.modules.auth.service import generate_token
from backend.modules.documents.db import get_user_documents
from backend.modules.timeutils import to_utc_iso

MIGRATION_006 = Path(__file__).parent.parent / "db" / "migrations" / "006_top_documents_search_count.sql"


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.fixture
def auth_header():
    return {"Authorization": f"Bearer {generate_token(user_id=1, email='user1@example.com')}"}


# ============================================================================
# 1. UTC timestamps
# ============================================================================

def test_to_utc_iso_marks_naive_utc_datetimes_with_z():
    assert to_utc_iso(datetime.datetime(2026, 10, 29, 16, 0, 9)) == "2026-10-29T16:00:09Z"


def test_to_utc_iso_converts_aware_datetimes_to_utc():
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    assert to_utc_iso(datetime.datetime(2026, 10, 29, 21, 30, tzinfo=ist)) == "2026-10-29T16:00:00Z"


def test_to_utc_iso_passes_through_none_and_strings():
    assert to_utc_iso(None) is None
    assert to_utc_iso("2026-10-29T16:00:09Z") == "2026-10-29T16:00:09Z"


@pytest.mark.parametrize("env", [
    {"MYSQL_URL": "mysql://u:p@db.example.com:3306/prism"},
    {"MYSQL_URL": "", "MYSQL_HOST": "localhost"},
])
def test_mysql_session_time_zone_is_utc(monkeypatch, env):
    for key, value in env.items():
        if value:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)
    assert get_db_config()["time_zone"] == "+00:00"


def _dict_conn(rows):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = rows
    return conn


def test_search_history_last_searched_is_utc_with_z():
    rows = [{
        "query_text": "weak entity", "search_count": 1, "query_rank": 1,
        "last_searched": datetime.datetime(2026, 10, 29, 16, 0, 9), "total_searches": 1,
    }]
    assert get_search_history(1, conn=_dict_conn(rows))[0]["last_searched"] == "2026-10-29T16:00:09Z"


def test_unsearched_uploaded_at_is_utc_with_z():
    rows = [{"doc_id": 3, "title": "a.pdf", "uploaded_at": datetime.datetime(2026, 10, 29, 15, 57, 49)}]
    assert get_unsearched_documents(1, conn=_dict_conn(rows))[0]["uploaded_at"] == "2026-10-29T15:57:49Z"


def test_document_list_uploaded_at_is_utc_with_z():
    rows = [{
        "doc_id": 3, "title": "a.pdf", "uploaded_at": datetime.datetime(2026, 10, 29, 15, 57, 49),
        "status": "ready", "chunk_count": 26,
    }]
    assert get_user_documents(1, conn=_dict_conn(rows))[0]["uploaded_at"] == "2026-10-29T15:57:49Z"


def test_document_detail_uploaded_at_is_utc_with_z(client, auth_header):
    doc = {
        "doc_id": 3, "user_id": 1, "title": "a.pdf", "minio_key": "1/a.pdf",
        "uploaded_at": datetime.datetime(2026, 10, 29, 15, 57, 49), "status": "ready",
    }
    with patch("backend.modules.documents.routes.get_document_by_id", return_value=doc), \
         patch("backend.modules.documents.routes.get_document_chunk_count", return_value=26), \
         patch("backend.modules.documents.routes.get_document_topics", return_value=[]):
        res = client.get("/api/documents/3", headers=auth_header)

    assert res.status_code == 200
    assert res.get_json()["uploaded_at"] == "2026-10-29T15:57:49Z"


# ============================================================================
# 2. Restored searches are not logged
# ============================================================================

RESULTS = [{"chunk_id": 42, "doc_id": 7, "doc_title": "notes.pdf", "snippet": "text", "score": 0.2}]


def _search(client, auth_header, body):
    with patch("backend.modules.search.routes.execute_semantic_search", return_value=(RESULTS, True)), \
         patch("backend.modules.search.routes.log_search_async") as log_search:
        res = client.post("/api/search", json=body, headers=auth_header)
    return res, log_search


def test_search_with_log_false_returns_results_without_logging(client, auth_header):
    res, log_search = _search(client, auth_header, {"query": "weak entity", "log": False})

    assert res.status_code == 200
    assert res.get_json() == {"results": RESULTS, "cached": True}
    log_search.assert_not_called()


@pytest.mark.parametrize("body", [{"query": "weak entity"}, {"query": "weak entity", "log": True}])
def test_submitted_search_is_logged_once(client, auth_header, body):
    res, log_search = _search(client, auth_header, body)

    assert res.status_code == 200
    log_search.assert_called_once()
    assert log_search.call_args.kwargs["query"] == "weak entity"


@pytest.mark.parametrize("bad", ["false", 0, None])
def test_search_rejects_a_non_boolean_log_flag(client, auth_header, bad):
    res, log_search = _search(client, auth_header, {"query": "weak entity", "log": bad})

    assert res.status_code == 400
    log_search.assert_not_called()


# ============================================================================
# 3 & 4. top_documents.search_count and ready-only unsearched documents
# ============================================================================

def test_migration_006_adds_search_count_to_the_view():
    sql = MIGRATION_006.read_text()
    assert sql.startswith("-- ENGINE: MySQL")
    assert "CREATE OR REPLACE VIEW top_documents AS" in sql
    assert "COUNT(DISTINCT sr.log_id)    AS search_count" in sql
    # Columns the analytics module relies on are still there
    for column in ("d.user_id", "d.doc_id", "d.title", "AS appearance_count", "AS avg_score"):
        assert column in sql


def test_migration_006_is_one_statement_for_the_migration_runner():
    # migrate.py splits MySQL scripts on ";" — a ";" inside a comment would break it
    script = MIGRATION_006.read_text().split("-- ENGINE: MySQL", 1)[1]
    statements = [s.strip() for s in script.split(";") if s.strip()]
    assert len(statements) == 1


def test_unsearched_query_only_lists_ready_documents():
    assert "AND status = 'ready'" in UNSEARCHED_DOCS_QUERY


# ============================================================================
# Integration (opt-in): real MySQL, TEMPORARY tables only
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)


@pytest.fixture
def mysql_conn():
    import mysql.connector

    conn = mysql.connector.connect(**get_db_config())
    try:
        yield conn
    finally:
        conn.close()  # TEMPORARY tables are dropped with the session


def _top_documents_select():
    """The SELECT behind the view in migration 006 (views can't read TEMPORARY tables)."""
    sql = MIGRATION_006.read_text()
    return sql.split("CREATE OR REPLACE VIEW top_documents AS", 1)[1].strip().rstrip(";")


@integration
def test_integration_search_count_counts_searches_not_passages(mysql_conn):
    cur = mysql_conn.cursor()
    for ddl in (
        "CREATE TEMPORARY TABLE documents (doc_id INT PRIMARY KEY, user_id INT, title VARCHAR(255))",
        "CREATE TEMPORARY TABLE chunks (chunk_id INT PRIMARY KEY, doc_id INT)",
        "CREATE TEMPORARY TABLE search_results (result_id INT AUTO_INCREMENT PRIMARY KEY,"
        " log_id INT, chunk_id INT, `rank` INT, similarity_score FLOAT)",
    ):
        cur.execute(ddl)
    cur.execute("INSERT INTO documents VALUES (1, 9, 'er-model.pdf'), (2, 9, 'schema.pdf')")
    cur.executemany("INSERT INTO chunks VALUES (%s, %s)", [(c, 1) for c in range(1, 11)] + [(11, 2), (12, 2)])
    # er-model.pdf: 10, 10 and 5 passages in three searches; schema.pdf: 2 passages in one
    rows = [(log_id, chunk, rank, 0.4) for log_id, n in ((1, 10), (2, 10), (3, 5))
            for rank, chunk in enumerate(range(1, n + 1), start=1)]
    rows += [(3, 11, 6, 0.5), (3, 12, 7, 0.5)]
    cur.executemany("INSERT INTO search_results (log_id, chunk_id, `rank`, similarity_score) VALUES (%s, %s, %s, %s)", rows)

    cur.execute(f"SELECT title, search_count, appearance_count FROM ({_top_documents_select()}) t "
                "WHERE user_id = 9 ORDER BY search_count DESC")
    assert cur.fetchall() == [("er-model.pdf", 3, 25), ("schema.pdf", 1, 2)]
    cur.close()


@integration
def test_integration_timestamps_come_back_in_utc(mysql_conn):
    cur = mysql_conn.cursor()
    cur.execute("SELECT @@session.time_zone")
    assert cur.fetchone()[0] == "+00:00"

    cur.execute("CREATE TEMPORARY TABLE search_log (log_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT,"
                " query_text TEXT, searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    # Written by a session in IST: 21:30 IST is 16:00 UTC
    cur.execute("SET time_zone = '+05:30'")
    cur.execute("INSERT INTO search_log (user_id, query_text, searched_at) VALUES (9, 'weak entity', '2026-10-29 21:30:00')")
    cur.execute("SET time_zone = '+00:00'")
    cur.close()

    history = get_search_history(9, conn=mysql_conn)
    assert history[0]["last_searched"] == "2026-10-29T16:00:00Z"
