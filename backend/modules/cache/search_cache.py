"""Search-result caching backed by Redis (Slice 11).

Cache design (per slice-11 spec):
- Key format: search:{user_id}:{md5(query.strip().lower())}
- Value: JSON-serialised list of result objects
- TTL: 3600 seconds (set on every write)
- Invalidation: delete all keys matching search:{user_id}:* when a user
  uploads or deletes a document

Every Redis interaction is wrapped so that a cache failure is logged and
swallowed. A read failure behaves like a cache miss (returns None) and a write
failure is a no-op, so the search endpoint always degrades to a live query.
"""
import hashlib
import json
import logging

try:
    from backend.modules.cache.client import get_redis_client
except ImportError:
    from modules.cache.client import get_redis_client

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600


def _make_key(user_id, query: str) -> str:
    """Build a normalised cache key for a user's query.

    Normalisation (strip + lowercase) ensures "Joins in SQL" and "joins in sql"
    resolve to the same key.
    """
    normalised = (query or "").strip().lower()
    digest = hashlib.md5(normalised.encode("utf-8")).hexdigest()
    return f"search:{user_id}:{digest}"


def get_cached_search(user_id, query: str):
    """Return the cached result list for (user_id, query), or None on a miss.

    Returns None on any Redis error so the caller falls through to a live query.
    """
    try:
        client = get_redis_client()
        if client is None:
            return None
        raw = client.get(_make_key(user_id, query))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Cache read failed for user %s: %s", user_id, e)
        return None


def set_cached_search(user_id, query: str, results) -> None:
    """Cache a result list for (user_id, query) with a 3600s TTL.

    No-op on any Redis error.
    """
    try:
        client = get_redis_client()
        if client is None:
            return
        client.set(
            _make_key(user_id, query),
            json.dumps(results),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as e:
        logger.warning("Cache write failed for user %s: %s", user_id, e)


def invalidate_user_cache(user_id) -> None:
    """Delete all cached search results for a user (search:{user_id}:*).

    Uses SCAN rather than KEYS to avoid blocking Redis on large keyspaces.
    No-op on any Redis error.
    """
    try:
        client = get_redis_client()
        if client is None:
            return
        pattern = f"search:{user_id}:*"
        keys = list(client.scan_iter(match=pattern, count=100))
        if keys:
            client.delete(*keys)
    except Exception as e:
        logger.warning("Cache invalidation failed for user %s: %s", user_id, e)
