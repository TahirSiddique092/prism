"""Acceptance criteria tests for slice-11: Redis cache layer.

Acceptance criteria verified (those testable without the search endpoint,
which lands in slice-09):
2. Cache key is normalised — "Joins in SQL" and "joins in sql" resolve to the
   same key.
3. TTL is set on every write — keys expire automatically after 1 hour (3600s).
4. Invalidation clears all of a user's search cache (and only that user's).
5. Cache read/write errors are caught — a Redis failure never propagates; reads
   degrade to a miss (None) and writes/invalidation become no-ops.

Not covered here (require slice-09 search endpoint to exist):
1. A repeated identical query returns the cached result without hitting pgvector.
6. GET /api/search response includes a `cached: true/false` field.
"""
from unittest.mock import patch

import fakeredis
import pytest

from backend.modules.cache import (
    get_cached_search,
    invalidate_user_cache,
    set_cached_search,
)
from backend.modules.cache import search_cache


@pytest.fixture
def fake_redis():
    """A fresh in-memory Redis patched in for every cache call."""
    server = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch.object(search_cache, "get_redis_client", return_value=server):
        yield server


# --- Criterion 2: key normalisation ---

def test_key_is_normalised_case_and_whitespace():
    assert search_cache._make_key(1, "Joins in SQL") == search_cache._make_key(
        1, "joins in sql"
    )
    assert search_cache._make_key(1, "  joins in sql  ") == search_cache._make_key(
        1, "joins in sql"
    )


def test_key_differs_by_user():
    assert search_cache._make_key(1, "joins in sql") != search_cache._make_key(
        2, "joins in sql"
    )


def test_normalised_queries_share_a_cache_entry(fake_redis):
    set_cached_search(1, "Joins in SQL", [{"chunk_id": 42}])
    assert get_cached_search(1, "joins in sql") == [{"chunk_id": 42}]


# --- Criterion 3: TTL set on every write ---

def test_ttl_is_set_to_3600_on_write(fake_redis):
    set_cached_search(1, "joins in sql", [{"chunk_id": 1}])
    key = search_cache._make_key(1, "joins in sql")
    ttl = fake_redis.ttl(key)
    assert 0 < ttl <= 3600


# --- round-trip ---

def test_get_returns_none_on_miss(fake_redis):
    assert get_cached_search(1, "never cached") is None


def test_set_then_get_roundtrips_list(fake_redis):
    results = [{"chunk_id": 1, "score": 0.1}, {"chunk_id": 2, "score": 0.2}]
    set_cached_search(7, "sql joins", results)
    assert get_cached_search(7, "sql joins") == results


# --- Criterion 4: invalidation ---

def test_invalidate_clears_only_target_user(fake_redis):
    set_cached_search(1, "query a", [{"chunk_id": 1}])
    set_cached_search(1, "query b", [{"chunk_id": 2}])
    set_cached_search(2, "query a", [{"chunk_id": 3}])

    invalidate_user_cache(1)

    assert get_cached_search(1, "query a") is None
    assert get_cached_search(1, "query b") is None
    # Other user's cache is untouched
    assert get_cached_search(2, "query a") == [{"chunk_id": 3}]


def test_invalidate_with_no_keys_is_safe(fake_redis):
    invalidate_user_cache(999)  # should not raise


# --- Criterion 5: graceful degradation ---

class _BoomRedis:
    def get(self, *a, **k):
        raise ConnectionError("redis down")

    def set(self, *a, **k):
        raise ConnectionError("redis down")

    def scan_iter(self, *a, **k):
        raise ConnectionError("redis down")

    def delete(self, *a, **k):
        raise ConnectionError("redis down")


def test_read_degrades_to_miss_on_redis_error():
    with patch.object(search_cache, "get_redis_client", return_value=_BoomRedis()):
        assert get_cached_search(1, "joins in sql") is None


def test_write_is_noop_on_redis_error():
    with patch.object(search_cache, "get_redis_client", return_value=_BoomRedis()):
        set_cached_search(1, "joins in sql", [{"chunk_id": 1}])  # must not raise


def test_invalidate_is_noop_on_redis_error():
    with patch.object(search_cache, "get_redis_client", return_value=_BoomRedis()):
        invalidate_user_cache(1)  # must not raise


def test_functions_noop_when_redis_not_configured():
    with patch.object(search_cache, "get_redis_client", return_value=None):
        assert get_cached_search(1, "q") is None
        set_cached_search(1, "q", [{"x": 1}])
        invalidate_user_cache(1)
