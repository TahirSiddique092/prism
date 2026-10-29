"""Shared PostgreSQL (pgvector) connections, reused across requests (slice-29).

Opening a connection to the managed Postgres takes ~1.75 s (TCP + TLS + auth),
so connections are kept and lent out instead of being opened per query:

- ``run_pg(work)`` calls ``work(conn)`` with a pooled connection and takes the
  connection back afterwards.
- A connection idle for longer than ``MAX_IDLE_SECONDS`` is closed instead of
  reused: Neon suspends idle compute after 5 minutes and drops its connections.
- If a connection still turns out to be dead, ``work`` runs once more on a new
  one.

Pooled connections are in autocommit mode, so a read is one round trip and
nothing has to be rolled back when the connection is returned. Writes that must
be atomic wrap themselves in ``with conn:``, which runs one transaction.
"""
import logging
import os
import threading
import time

import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_IDLE

logger = logging.getLogger(__name__)

# Idle connections kept for reuse; extra connections opened under load are
# closed when returned.
MAX_IDLE_CONNECTIONS = 5
# Below Neon's 5-minute suspend, so a kept connection is still alive when reused.
MAX_IDLE_SECONDS = 240

_idle = []  # (connection, monotonic time it was returned), most recent last
_idle_lock = threading.Lock()


def _connect():
    url = os.getenv("POSTGRES_URL")
    if not url:
        raise RuntimeError("PostgreSQL connection unavailable")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def _close_quietly(conn):
    try:
        conn.close()
    except Exception:
        pass


def _borrow():
    """Take the most recently returned live connection, or open a new one."""
    now = time.monotonic()
    expired = []
    conn = None
    with _idle_lock:
        while _idle:
            candidate, returned_at = _idle.pop()
            if candidate.closed or now - returned_at > MAX_IDLE_SECONDS:
                expired.append(candidate)
                continue
            conn = candidate
            break
    for old in expired:
        _close_quietly(old)
    return conn if conn is not None else _connect()


def _give_back(conn):
    """Keep a healthy connection for reuse; close anything else."""
    if conn.closed:
        return
    # Autocommit connections are idle between statements, and `with conn:`
    # rolls back on error. Any other state means the connection can't be trusted.
    if conn.info.transaction_status != TRANSACTION_STATUS_IDLE:
        _close_quietly(conn)
        return
    with _idle_lock:
        if len(_idle) < MAX_IDLE_CONNECTIONS:
            _idle.append((conn, time.monotonic()))
            return
    _close_quietly(conn)


def run_pg(work):
    """Run ``work(conn)`` on a pooled connection and return its result.

    Raises RuntimeError if POSTGRES_URL is not set. If the server has dropped
    the borrowed connection, ``work`` runs once more on a newly opened one.
    Any other error is raised unchanged.
    """
    conn = _borrow()
    try:
        result = work(conn)
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        if not conn.closed:
            _give_back(conn)
            raise
        logger.info("PostgreSQL connection was dropped by the server; retrying on a new connection")
        conn = _connect()
        try:
            result = work(conn)
        except BaseException:
            _give_back(conn)
            raise
    except BaseException:
        _give_back(conn)
        raise
    _give_back(conn)
    return result


def reset_pool():
    """Close every idle connection. Primarily used in tests."""
    with _idle_lock:
        conns = [conn for conn, _ in _idle]
        _idle.clear()
    for conn in conns:
        _close_quietly(conn)
