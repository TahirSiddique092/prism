"""Redis client factory for the cache module (Slice 11).

Follows the same env-driven, lazy-construction pattern as
`auth/db.get_db_connection`: read REDIS_URL from the environment and build a
client on demand. The client is cached as a module-level singleton so we reuse
one connection pool across requests.
"""
import os

import redis

_client = None


def get_redis_client():
    """Return a shared Redis client built from REDIS_URL.

    Returns None if REDIS_URL is not configured. Construction errors are allowed
    to propagate here; callers in search_cache wrap usage in try/except so a
    Redis outage degrades gracefully rather than crashing the endpoint.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("REDIS_URL")
    if not url:
        return None

    _client = redis.Redis.from_url(url, decode_responses=True)
    return _client


def reset_client():
    """Reset the cached client. Primarily used in tests."""
    global _client
    _client = None
