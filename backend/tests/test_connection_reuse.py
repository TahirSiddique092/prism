"""Slice 29: reuse Redis and Postgres connections so cached searches are fast.

Unit tests use fake connections. The opt-in integration tests at the bottom run
against the real services (PRISM_CONNECTION_INTEGRATION=1 plus REDIS_URL /
POSTGRES_URL) and write nothing but one short-lived Redis key.
"""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from psycopg2.extensions import TRANSACTION_STATUS_IDLE, TRANSACTION_STATUS_INTRANS

import backend.modules.postgres as pg
from backend.modules.cache import (
    get_cached_search,
    get_redis_client,
    reset_redis_client,
    set_cached_search,
)


@pytest.fixture(autouse=True)
def clean_shared_clients():
    reset_redis_client()
    pg.reset_pool()
    yield
    reset_redis_client()
    pg.reset_pool()


# ============================================================================
# Fakes
# ============================================================================

class FakeRedis:
    """Just enough of redis.Redis for the cache module."""

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def scan_iter(self, match=None, count=None):
        prefix = match.rstrip("*")
        return [k for k in list(self.store) if k.startswith(prefix)]

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    def close(self):
        pass


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _maybe_fail(self):
        if self.conn.fail_with is not None:
            err, self.conn.fail_with = self.conn.fail_with, None
            if self.conn.drop_on_fail:
                self.conn.closed = 2  # what psycopg2 sets when the server drops the connection
            raise err

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        self._maybe_fail()

    def executemany(self, sql, rows):
        self.conn.executed_many.append((sql, list(rows)))
        self._maybe_fail()

    def fetchall(self):
        return self.conn.rows


class FakePgConn:
    def __init__(self, rows=()):
        self.closed = 0
        self.autocommit = False
        self.rows = list(rows)
        self.info = SimpleNamespace(transaction_status=TRANSACTION_STATUS_IDLE)
        self.executed, self.executed_many = [], []
        self.commits = self.rollbacks = 0
        self.fail_with, self.drop_on_fail = None, False

    def cursor(self):
        return FakeCursor(self)

    # `with conn:` = one transaction, committed on success, rolled back on error
    def __enter__(self):
        return self

    def __exit__(self, exc_type, *rest):
        if exc_type is None:
            self.commits += 1
        else:
            self.rollbacks += 1
        return False

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = 1


@pytest.fixture
def pg_connect(monkeypatch):
    """Patch psycopg2.connect; each call returns the next FakePgConn."""
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pw@example.invalid/db")
    made = []

    def connect(url):
        conn = FakePgConn(rows=[(42, 7, 0.18)])
        made.append(conn)
        return conn

    with patch("backend.modules.postgres.psycopg2.connect", side_effect=connect) as mock_connect:
        mock_connect.made = made
        yield mock_connect


# ============================================================================
# Redis: one client per process
# ============================================================================

def test_twenty_searches_create_one_redis_client():
    from backend.modules.search.service import execute_semantic_search

    fake = FakeRedis()
    with patch("redis.from_url", return_value=fake) as from_url, \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[7]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors",
               return_value=[{"chunk_id": 42, "doc_id": 7, "score": 0.2}]), \
         patch("backend.modules.search.service.get_chunks_metadata",
               return_value={42: {"doc_title": "notes.pdf", "snippet": "text"}}):
        outcomes = [execute_semantic_search(user_id=1, query="weak entities") for _ in range(20)]

    assert from_url.call_count == 1
    assert [cached for _, cached in outcomes] == [False] + [True] * 19
    assert all(results == outcomes[0][0] for results, _ in outcomes)


def test_redis_client_is_configured_to_replace_dropped_connections():
    import redis

    with patch("redis.from_url", return_value=FakeRedis()) as from_url:
        get_redis_client()

    kwargs = from_url.call_args.kwargs
    assert kwargs["decode_responses"] is True
    assert kwargs["health_check_interval"] == 30
    assert redis.exceptions.ConnectionError in kwargs["retry_on_error"]
    assert kwargs["retry"] is not None
    assert kwargs["socket_connect_timeout"] == 3
    assert kwargs["socket_timeout"] == 3


def test_reset_redis_client_builds_a_new_client_next_time():
    with patch("redis.from_url", side_effect=lambda *a, **k: FakeRedis()) as from_url:
        first = get_redis_client()
        assert get_redis_client() is first
        reset_redis_client()
        assert get_redis_client() is not first
    assert from_url.call_count == 2


def test_search_still_works_when_redis_is_unreachable():
    import redis
    from backend.modules.search.service import execute_semantic_search

    down = MagicMock()
    down.get.side_effect = redis.exceptions.ConnectionError("unreachable")
    down.set.side_effect = redis.exceptions.ConnectionError("unreachable")
    with patch("redis.from_url", return_value=down), \
         patch("backend.modules.search.service.get_user_document_ids", return_value=[7]), \
         patch("backend.modules.search.service.get_embeddings", return_value=[[0.1] * 384]), \
         patch("backend.modules.search.service.search_chunk_vectors",
               return_value=[{"chunk_id": 42, "doc_id": 7, "score": 0.2}]), \
         patch("backend.modules.search.service.get_chunks_metadata",
               return_value={42: {"doc_title": "notes.pdf", "snippet": "text"}}):
        results, cached = execute_semantic_search(user_id=1, query="weak entities")

    assert cached is False
    assert [r["chunk_id"] for r in results] == [42]


def test_cache_helpers_share_the_client():
    fake = FakeRedis()
    with patch("redis.from_url", return_value=fake) as from_url:
        assert set_cached_search(3, "joins", [{"chunk_id": 1}]) is True
        assert get_cached_search(3, "  JOINS ") == [{"chunk_id": 1}]
    assert from_url.call_count == 1


# ============================================================================
# Postgres: pooled connections
# ============================================================================

def test_connection_is_reused_across_queries(pg_connect):
    for _ in range(5):
        pg.run_pg(lambda conn: conn.cursor().execute("SELECT 1"))

    assert pg_connect.call_count == 1
    assert pg_connect.made[0].autocommit is True
    assert pg_connect.made[0].closed == 0


def test_search_chunk_vectors_uses_the_pool(pg_connect):
    from backend.modules.search.db import search_chunk_vectors

    for _ in range(3):
        results = search_chunk_vectors([0.0] * 384, [7], limit=10)

    assert pg_connect.call_count == 1
    assert results == [{"chunk_id": 42, "doc_id": 7, "score": 0.18}]


def test_delete_chunk_vectors_uses_the_pool(pg_connect):
    from backend.modules.documents.db import delete_chunk_vectors

    delete_chunk_vectors(55)

    conn = pg_connect.made[0]
    assert conn.executed == [("DELETE FROM chunk_vectors WHERE doc_id = %s", (55,))]
    assert conn.closed == 0  # returned to the pool, not closed


def test_connection_idle_too_long_is_replaced(pg_connect, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(pg.time, "monotonic", lambda: clock[0])

    pg.run_pg(lambda conn: None)
    clock[0] += pg.MAX_IDLE_SECONDS + 1
    pg.run_pg(lambda conn: None)

    assert pg_connect.call_count == 2
    assert pg_connect.made[0].closed == 1  # expired connection was closed


def test_dropped_connection_is_retried_once_on_a_new_connection(pg_connect):
    pg.run_pg(lambda conn: None)  # put one connection in the pool
    stale = pg_connect.made[0]
    stale.fail_with = psycopg2.OperationalError("server closed the connection unexpectedly")
    stale.drop_on_fail = True

    def query(conn):
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchall()

    assert pg.run_pg(query) == [(42, 7, 0.18)]
    assert pg_connect.call_count == 2
    # The new connection was kept for the next query
    pg.run_pg(query)
    assert pg_connect.call_count == 2


def test_error_on_a_live_connection_is_raised_without_retry(pg_connect):
    def failing(conn):
        conn.fail_with = psycopg2.OperationalError("canceling statement due to statement timeout")
        conn.cursor().execute("SELECT pg_sleep(60)")

    with pytest.raises(psycopg2.OperationalError):
        pg.run_pg(failing)

    assert pg_connect.call_count == 1
    pg.run_pg(lambda conn: None)
    assert pg_connect.call_count == 1  # still healthy, so it was kept


def test_connection_left_in_a_transaction_is_not_reused(pg_connect):
    def leave_open(conn):
        conn.info.transaction_status = TRANSACTION_STATUS_INTRANS

    pg.run_pg(leave_open)
    pg.run_pg(lambda conn: None)

    assert pg_connect.call_count == 2
    assert pg_connect.made[0].closed == 1


def test_missing_postgres_url_raises(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(RuntimeError, match="PostgreSQL connection unavailable"):
        pg.run_pg(lambda conn: None)


# ============================================================================
# Worker: vectors are inserted in one transaction on a pooled connection
# ============================================================================

def _run_worker(fail_insert=None):
    from backend.modules.documents import worker

    chunks = [{"chunk_id": 1, "chunk_text": "first"}, {"chunk_id": 2, "chunk_text": "second"}]
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"%PDF"))}
    page = MagicMock(get_text=MagicMock(return_value="Some text on the page."))

    def connect(url):
        conn = FakePgConn()
        if fail_insert is not None:
            conn.fail_with = fail_insert
        connect.made.append(conn)
        return conn
    connect.made = []

    with patch.dict(os.environ, {"POSTGRES_URL": "postgresql://example.invalid/db"}), \
         patch.object(worker, "get_s3_client", return_value=s3), \
         patch.object(worker, "fitz", MagicMock(open=MagicMock(return_value=[page]))), \
         patch.object(worker, "_ensure_nltk"), \
         patch.object(worker, "nltk", MagicMock(sent_tokenize=MagicMock(return_value=["s"]))), \
         patch.object(worker, "chunk_sentences", return_value=["first", "second"]), \
         patch.object(worker, "insert_chunks"), \
         patch.object(worker, "update_document_status") as status, \
         patch.object(worker, "_invalidate_owner_cache"), \
         patch("backend.modules.documents.db.get_chunks_for_document", return_value=chunks), \
         patch("backend.modules.documents.db.delete_chunks") as delete_chunks, \
         patch("backend.modules.documents.embed.get_embeddings", return_value=[[0.1], [0.2]]), \
         patch("backend.modules.postgres.psycopg2.connect", side_effect=connect):
        worker.process_document(9, "1/x.pdf")
    return connect.made, status, delete_chunks


def test_worker_inserts_vectors_in_one_transaction():
    made, status, delete_chunks = _run_worker()

    conn = made[0]
    (sql, rows), = conn.executed_many
    assert sql == "INSERT INTO chunk_vectors (chunk_id, doc_id, embedding) VALUES (%s, %s, %s)"
    assert [r[0] for r in rows] == [1, 2]
    assert conn.commits == 1 and conn.rollbacks == 0
    assert conn.closed == 0  # returned to the pool
    status.assert_called_with(9, "ready")
    delete_chunks.assert_not_called()


def test_worker_rolls_back_and_marks_error_when_insert_fails():
    made, status, delete_chunks = _run_worker(fail_insert=psycopg2.IntegrityError("duplicate key"))

    assert made[0].rollbacks == 1 and made[0].commits == 0
    delete_chunks.assert_called_once_with(9)
    status.assert_called_with(9, "error")


# ============================================================================
# Integration (opt-in): real Redis and Postgres
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_CONNECTION_INTEGRATION") != "1",
    reason="set PRISM_CONNECTION_INTEGRATION=1 with REDIS_URL / POSTGRES_URL to run against real services",
)


@integration
def test_integration_redis_recovers_after_connection_is_closed():
    import socket

    client = get_redis_client()
    key = "search:-1:slice29-probe"
    client.set(key, "ok", ex=60)
    # Simulate the server dropping every idle connection
    for conn in list(client.connection_pool._available_connections):
        conn._sock.shutdown(socket.SHUT_RDWR)
    try:
        assert client.get(key) == "ok"
    finally:
        client.delete(key)


@integration
def test_integration_postgres_recovers_after_connection_is_dropped():
    import socket

    def select_one(conn):
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0]

    assert pg.run_pg(select_one) == 1
    pooled = pg._idle[-1][0]
    # Simulate the server dropping the idle connection by shutting down its
    # socket (pg_terminate_backend can't target it through Neon's pooler).
    sock = socket.socket(fileno=os.dup(pooled.fileno()))
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()

    assert pg.run_pg(select_one) == 1
    assert pooled.closed
    assert pg._idle[-1][0] is not pooled
