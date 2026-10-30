"""Slice 31: drop weak vector search results (ADR-020).

Vector results further than RESULT_DISTANCE_CUTOFF (0.60 cosine distance) are
dropped, except the best match. The FULLTEXT fallback (best match above 0.75)
is unchanged.
"""
from unittest.mock import patch

import pytest

from backend.app import create_app
from backend.modules.auth.service import generate_token
from backend.modules.search import service
from backend.modules.search.service import (
    RESULT_DISTANCE_CUTOFF,
    VECTOR_SIMILARITY_THRESHOLD,
    drop_weak_matches,
    execute_semantic_search,
)


def _matches(*distances):
    return [{"chunk_id": 100 + i, "doc_id": 7, "score": d} for i, d in enumerate(distances)]


def _metadata(chunk_ids):
    return {cid: {"doc_title": "notes.pdf", "snippet": f"passage {cid}", "page": 1} for cid in chunk_ids}


def _search(vector_matches, fulltext=()):
    with patch.object(service, "get_cached_search", return_value=None), \
         patch.object(service, "set_cached_search") as cache_write, \
         patch.object(service, "get_user_document_ids", return_value=[7]), \
         patch.object(service, "get_embeddings", return_value=[[0.1] * 384]), \
         patch.object(service, "search_chunk_vectors", return_value=vector_matches), \
         patch.object(service, "get_chunks_metadata", side_effect=_metadata) as metadata, \
         patch.object(service, "search_chunks_fulltext", return_value=list(fulltext)) as fulltext_search:
        results, cached = execute_semantic_search(user_id=1, query="cardinality ratio")
    return results, cache_write, metadata, fulltext_search


def test_cutoff_sits_below_the_fallback_threshold():
    assert RESULT_DISTANCE_CUTOFF == 0.60
    assert VECTOR_SIMILARITY_THRESHOLD == 0.75


def test_matches_beyond_the_cutoff_are_dropped():
    kept = drop_weak_matches(_matches(0.38, 0.45, 0.59, 0.61, 0.70))
    assert [m["score"] for m in kept] == [0.38, 0.45, 0.59]


def test_a_match_exactly_at_the_cutoff_is_kept():
    assert [m["score"] for m in drop_weak_matches(_matches(0.40, 0.60, 0.6001))] == [0.40, 0.60]


def test_the_best_match_is_always_kept():
    # Between the cutoff and the fallback threshold: one result, not none
    assert [m["score"] for m in drop_weak_matches(_matches(0.68, 0.70, 0.74))] == [0.68]


def test_no_matches_stays_empty():
    assert drop_weak_matches([]) == []


def test_search_returns_and_caches_only_the_kept_results():
    results, cache_write, metadata, fulltext_search = _search(_matches(0.38, 0.45, 0.59, 0.61, 0.70))

    assert [r["score"] for r in results] == [0.38, 0.45, 0.59]
    metadata.assert_called_once_with([100, 101, 102])
    assert cache_write.call_args.args[2] == results
    fulltext_search.assert_not_called()


def test_weak_best_match_below_the_fallback_threshold_returns_one_result():
    results, _, _, fulltext_search = _search(_matches(0.68, 0.71))

    assert [r["score"] for r in results] == [0.68]
    fulltext_search.assert_not_called()


def test_fallback_is_unchanged_above_075():
    fulltext = [{"chunk_id": 9, "doc_id": 7, "doc_title": "notes.pdf", "snippet": "x", "score": None, "page": 2}]
    results, _, metadata, fulltext_search = _search(_matches(0.80, 0.82), fulltext=fulltext)

    fulltext_search.assert_called_once()
    metadata.assert_not_called()
    assert results == fulltext


def test_only_kept_results_are_logged():
    client = create_app({"TESTING": True}).test_client()
    token = generate_token(user_id=1, email="user1@example.com")
    kept = [{"chunk_id": 100, "doc_id": 7, "doc_title": "notes.pdf", "snippet": "x", "score": 0.4, "page": 1}]

    with patch("backend.modules.search.routes.execute_semantic_search", return_value=(kept, False)), \
         patch("backend.modules.search.routes.log_search_async") as log_search:
        res = client.post("/api/search", json={"query": "cardinality ratio"}, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert log_search.call_args.kwargs["results"] == kept


@pytest.mark.parametrize("distances, expected", [
    # Measured on the course PDFs (ADR-020): the tail of "before insert trigger with delimiter"
    ((0.399, 0.451, 0.456, 0.496, 0.523, 0.552, 0.574, 0.604, 0.616, 0.641), 7),
    # "explain cardinality ratio"
    ((0.478, 0.531, 0.531, 0.540, 0.567, 0.572, 0.587, 0.629, 0.647, 0.673), 7),
    # "how do you map a weak entity to a table": nothing weak, nothing dropped
    ((0.384, 0.388, 0.388, 0.389, 0.425, 0.425, 0.440, 0.481, 0.492, 0.494), 10),
])
def test_measured_queries(distances, expected):
    assert len(drop_weak_matches(_matches(*distances))) == expected
