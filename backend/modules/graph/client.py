"""Neo4j driver factory for the graph module (Slice 12).

Follows the same env-driven, lazy-singleton pattern as the cache and auth
modules: read NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from the environment and
build one driver on demand, reused across requests.
"""
import os

from neo4j import GraphDatabase

_driver = None


def get_driver():
    """Return a shared Neo4j driver built from NEO4J_* env vars.

    Returns None if NEO4J_URI is not configured. The driver is created lazily;
    it does not open a connection until a session runs a query, so construction
    here never blocks on an unreachable server.
    """
    global _driver
    if _driver is not None:
        return _driver

    uri = os.getenv("NEO4J_URI")
    if not uri:
        return None

    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    # Keep connection acquisition short so a down Neo4j fails fast rather than
    # hanging the (background) graph write.
    _driver = GraphDatabase.driver(
        uri,
        auth=(user, password),
        connection_acquisition_timeout=5,
    )
    return _driver


def reset_driver():
    """Close and clear the cached driver. Primarily used in tests."""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:
            pass
    _driver = None
