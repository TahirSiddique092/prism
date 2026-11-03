"""Slice 32: [DB] lines in the backend terminal for triggers, views, procedures and functions.

1. logged_db_call / log_db_event write one "[DB] KIND name ..." line
2. Deleting a document logs the before_document_delete trigger, confirmed by
   its deletion_audit row, or a WARNING if no row was written
3. Reading the top_documents view logs a VIEW line
4. The server configures INFO logging when it starts
"""
import logging
import re
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.modules.analytics.db import get_top_documents
from backend.modules.dblog import log_db_event, logged_db_call
from backend.modules.documents.db import delete_document

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def db_lines(caplog):
    caplog.set_level(logging.INFO, logger="prism.db")
    caplog.set_level(logging.INFO, logger="backend.modules.documents.db")

    def lines(level=None):
        return [r.getMessage() for r in caplog.records
                if r.getMessage().startswith("[DB]") and (level is None or r.levelno == level)]
    return lines


def _delete_conn(chunks=43, audit_id=7, rowcount=1, fail=None):
    """A mock connection for delete_document. ``fail`` names a query to raise on."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.rowcount = rowcount
    results = {"COUNT": (chunks,), "deletion_audit": (audit_id,) if audit_id else None}
    state = {}

    def execute(sql, params=None):
        key = "COUNT" if "COUNT(*)" in sql else "deletion_audit" if "deletion_audit" in sql else "DELETE"
        if fail == key:
            raise RuntimeError("Lost connection to MySQL server")
        state["last"] = key

    cursor.execute.side_effect = execute
    cursor.fetchone.side_effect = lambda: results.get(state.get("last"))
    return conn


# ============================================================================
# 1. Line format
# ============================================================================

def test_timed_call_logs_kind_rows_and_time(db_lines):
    with logged_db_call("VIEW", "top_documents read: user_id=2") as call:
        call.rows = 2

    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] VIEW      top_documents read: user_id=2 → 2 rows in \d+ ms", line)


def test_one_row_is_singular_and_no_count_is_left_out(db_lines):
    with logged_db_call("PROCEDURE", "sp_search_history(user_id=2)") as call:
        call.rows = 1
    with logged_db_call("FUNCTION", "fn_chunk_count(doc_id=4)"):
        pass

    first, second = db_lines()
    assert "→ 1 row in" in first
    assert re.fullmatch(r"\[DB\] FUNCTION  fn_chunk_count\(doc_id=4\) in \d+ ms", second)


def test_nothing_is_logged_when_the_query_fails(db_lines):
    with pytest.raises(RuntimeError):
        with logged_db_call("VIEW", "top_documents read: user_id=2"):
            raise RuntimeError("table doesn't exist")
    assert db_lines() == []


def test_log_db_event_pads_the_kind(db_lines):
    log_db_event("TRIGGER", "before_document_delete fired: doc_id=1 → deletion_audit.audit_id=2")
    assert db_lines() == ["[DB] TRIGGER   before_document_delete fired: doc_id=1 → deletion_audit.audit_id=2"]


# ============================================================================
# 2. Trigger
# ============================================================================

def test_delete_logs_the_trigger_with_audit_row_and_cascade(db_lines):
    assert delete_document(12, user_id=2, conn=_delete_conn(chunks=43, audit_id=7)) is True
    assert db_lines(logging.INFO) == [
        "[DB] TRIGGER   before_document_delete fired: doc_id=12 → deletion_audit.audit_id=7 (cascade removed 43 chunks)"
    ]


def test_missing_audit_row_logs_a_warning(db_lines):
    assert delete_document(12, user_id=2, conn=_delete_conn(audit_id=None)) is True
    assert db_lines(logging.WARNING) == [
        "[DB] TRIGGER   before_document_delete did not fire: no deletion_audit row for doc_id=12"
    ]


def test_failed_chunk_count_still_deletes_and_logs_without_cascade(db_lines, caplog):
    assert delete_document(12, user_id=2, conn=_delete_conn(fail="COUNT")) is True
    assert db_lines(logging.INFO) == [
        "[DB] TRIGGER   before_document_delete fired: doc_id=12 → deletion_audit.audit_id=7"
    ]
    assert any("Could not count chunks of doc 12" in r.getMessage() for r in caplog.records)


def test_failed_audit_check_still_deletes(db_lines, caplog):
    assert delete_document(12, user_id=2, conn=_delete_conn(fail="deletion_audit")) is True
    assert db_lines() == []
    assert any("Could not check the deletion_audit row for doc 12" in r.getMessage() for r in caplog.records)


def test_nothing_deleted_means_no_trigger_line(db_lines):
    assert delete_document(12, user_id=2, conn=_delete_conn(rowcount=0)) is False
    assert db_lines() == []


# ============================================================================
# 3. View
# ============================================================================

def test_top_documents_logs_the_view(db_lines):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        {"doc_id": 2, "title": "er-model.pdf", "search_count": 3, "appearance_count": 25, "avg_score": 0.46},
        {"doc_id": 3, "title": "er-to-relational-schema.pdf", "search_count": 1, "appearance_count": 5, "avg_score": 0.42},
    ]
    get_top_documents(user_id=2, conn=conn)

    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] VIEW      top_documents read: user_id=2 → 2 rows in \d+ ms", line)


def test_db_lines_carry_no_personal_data(db_lines):
    delete_document(12, user_id=2, conn=_delete_conn())
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        {"doc_id": 2, "title": "Private notes.pdf", "search_count": 1, "appearance_count": 1, "avg_score": 0.4},
    ]
    get_top_documents(user_id=2, conn=conn)

    lines = db_lines()
    assert len(lines) == 2
    for line in lines:
        assert "@" not in line and "Private notes" not in line
        assert not re.search(r"password|token|query_text|chunk_text", line, re.I)


# ============================================================================
# 4. Logging set-up
# ============================================================================

def test_configure_logging_enables_info_and_quietens_chatty_libraries():
    from backend.app import configure_logging

    saved = {name: logging.getLogger(name).level for name in ("httpx", "neo4j", "sentence_transformers")}
    try:
        with patch("logging.basicConfig") as basic:
            configure_logging()
        assert basic.call_args.kwargs["level"] == logging.INFO
        assert "%(name)s" in basic.call_args.kwargs["format"]
        for name in saved:
            assert logging.getLogger(name).level == logging.WARNING
    finally:
        for name, level in saved.items():
            logging.getLogger(name).setLevel(level)


def test_starting_the_server_configures_logging_first():
    calls = []
    with patch("logging.basicConfig", side_effect=lambda **kw: calls.append("logging")), \
         patch("backend.modules.documents.db.mark_interrupted_processing_failed",
               side_effect=lambda: calls.append("recovery") or 0), \
         patch("flask.Flask.run", side_effect=lambda **kw: calls.append("run")), \
         patch("backend.modules.documents.storage.ensure_bucket_exists"):
        runpy.run_path(str(APP_PATH), run_name="__main__")

    assert calls == ["logging", "recovery", "run"]


def test_search_info_lines_no_longer_contain_the_search_text(caplog):
    """INFO is now visible, so the existing search lines must not print the query."""
    from backend.modules.search import service

    caplog.set_level(logging.INFO, logger="backend.modules.search.service")
    secret = "my private exam question"
    with patch.object(service, "get_cached_search", return_value=[]):
        service.execute_semantic_search(user_id=5, query=secret)
    with patch.object(service, "get_cached_search", return_value=None), \
         patch.object(service, "set_cached_search"), \
         patch.object(service, "get_user_document_ids", return_value=[7]), \
         patch.object(service, "get_embeddings", return_value=[[0.1] * 384]), \
         patch.object(service, "search_chunk_vectors", return_value=[{"chunk_id": 1, "doc_id": 7, "score": 0.9}]), \
         patch.object(service, "search_chunks_fulltext", return_value=[]):
        service.execute_semantic_search(user_id=5, query=secret)

    messages = [r.getMessage() for r in caplog.records]
    assert any("Cache hit for a search by user 5" in m for m in messages)
    assert any("FULLTEXT fallback for a search by user 5" in m for m in messages)
    assert not any(secret in m for m in messages)
