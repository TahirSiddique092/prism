"""Neo4j driver factory for the graph module (Slice 12).

Follows the same env-driven, lazy-singleton pattern as the cache and auth
modules: read NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from the environment and
build one driver on demand, reused across requests.
"""
import os
import threading

from neo4j import GraphDatabase

_driver = None
_driver_lock = threading.Lock()


def get_driver():
    """Return a shared Neo4j driver built from NEO4J_* env vars.

    Returns None if NEO4J_URI is not configured. The driver is created lazily
    under a lock (uploads each spawn a background thread, so two could race to
    build it otherwise, leaking a pool). It does not open a connection until a
    session runs a query.
    """
    global _driver
    if _driver is not None:
        return _driver

    with _driver_lock:
        # Re-check inside the lock: another thread may have built it meanwhile.
        if _driver is not None:
            return _driver

        uri = os.getenv("NEO4J_URI")
        if not uri:
            return None

        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        # Keep every network wait short so a down/unreachable Neo4j fails fast
        # rather than hanging the request thread (reads run synchronously):
        #   - connection_timeout bounds the TCP connect,
        #   - connection_acquisition_timeout bounds pool checkout,
        #   - max_transaction_retry_time bounds driver-level retries.
        _driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5,
        )
    return _driver


def reset_driver():
    """Close and clear the cached driver. Primarily used in tests."""
    global _driver
    with _driver_lock:
        if _driver is not None:
            try:
                _driver.close()
            except Exception:
                pass
        _driver = None
