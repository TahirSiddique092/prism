"""Cache module (Slice 11).

A reusable cache layer that wraps Redis. Consumed by `search` to cache query
results and invalidated by `documents` on upload or deletion.

Public API:
- get_cached_search(user_id, query) -> list | None
- set_cached_search(user_id, query, results) -> None
- invalidate_user_cache(user_id) -> None

All functions degrade gracefully: a Redis failure is logged and never raised,
so a cache outage can never crash a consuming endpoint.
"""
try:
    from backend.modules.cache.search_cache import (
        get_cached_search,
        set_cached_search,
        invalidate_user_cache,
    )
except ImportError:
    from modules.cache.search_cache import (
        get_cached_search,
        set_cached_search,
        invalidate_user_cache,
    )

__all__ = [
    "get_cached_search",
    "set_cached_search",
    "invalidate_user_cache",
]
