"""Cache service wrapping Redis (Slice 08 / Slice 11).

Provides Redis cache client and user-scoped search cache invalidation.
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_redis_client():
    """Return a Redis client instance configured from REDIS_URL."""
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


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
