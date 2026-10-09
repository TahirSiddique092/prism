"""Redis Cache service for PRISM (Slice 08 / Slice 09 / Slice 11).

Provides:
- get_redis_client: Connects to Redis using REDIS_URL.
- get_search_cache_key: Hashes query and scopes by user_id -> search:{user_id}:{md5(normalized_query)}.
- get_cached_search: Returns cached search results if present, or None.
- set_cached_search: Caches search results with TTL (default 3600 seconds).
- invalidate_user_cache: Deletes all cache entries matching search:{user_id}:*.
"""
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)


def get_redis_client():
    """Return a Redis client instance configured from REDIS_URL."""
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def get_search_cache_key(user_id: int, query: str) -> str:
    """Generate normalized cache key: search:{user_id}:{md5(query.strip().lower())}."""
    normalized_query = query.strip().lower()
    query_hash = hashlib.md5(normalized_query.encode("utf-8")).hexdigest()
    return f"search:{user_id}:{query_hash}"


def get_cached_search(user_id: int, query: str) -> list[dict] | None:
    """Retrieve cached search results for a user and query.
    
    Returns None if cache miss or if Redis is unreachable.
    """
    try:
        r = get_redis_client()
        key = get_search_cache_key(user_id, query)
        val = r.get(key)
        if val is not None:
            return json.loads(val)
        return None
    except Exception as e:
        logger.warning(f"Failed to read search cache for user {user_id}: {e}")
        return None


def set_cached_search(user_id: int, query: str, results: list[dict], ttl: int = 3600) -> bool:
    """Cache search results with an expiry TTL (in seconds).
    
    Degrades gracefully if Redis is unreachable.
    """
    try:
        r = get_redis_client()
        key = get_search_cache_key(user_id, query)
        r.set(key, json.dumps(results), ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"Failed to write search cache for user {user_id}: {e}")
        return False


def invalidate_user_cache(user_id: int) -> bool:
    """Invalidate all search cache keys for a given user: search:{user_id}:*
    
    Gracefully handles Redis errors and logs them without raising exceptions.
    """
    try:
        r = get_redis_client()
        pattern = f"search:{user_id}:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
        return True
    except Exception as e:
        logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")
        return False
