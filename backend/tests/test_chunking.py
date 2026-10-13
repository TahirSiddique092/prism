"""Regression tests for the document chunker (slice-06 chunking rules).

Guards the previously-fixed infinite-loop bug and the hard word-cap invariant.
"""
from backend.modules.documents.worker import (
    chunk_sentences,
    count_words,
    MAX_WORDS,
    MIN_CHUNK_WORDS,
)


def test_terminates_and_caps_on_single_oversized_sentence():
    """A single sentence far larger than the cap must not loop and must be split."""
    giant = " ".join(["word"] * 600)  # one 600-word "sentence"
    chunks = chunk_sentences([giant, "A short trailing sentence that is here."])

    # Every chunk stays within the hard cap.
    assert all(count_words(c) <= MAX_WORDS for c in chunks)
    # 600 words split into 250-word windows => 3 chunks from the giant sentence.
    assert len([c for c in chunks if c.startswith("word")]) == 3


def test_overlap_does_not_cause_infinite_loop():
    """Two near-cap sentences in a row used to re-trigger a cut forever."""
    big = " ".join(["alpha"] * 200) + "."
    sentences = [big, big, big]
    chunks = chunk_sentences(sentences)  # must return, not hang

    assert len(chunks) >= 3
    assert all(count_words(c) <= MAX_WORDS for c in chunks)


def test_normal_text_chunks_near_target():
    sentences = [f"This is sentence number {i} with several words in it." for i in range(100)]
    chunks = chunk_sentences(sentences)

    assert len(chunks) > 1
    assert all(count_words(c) <= MAX_WORDS for c in chunks)
    # Chunks carry sentence overlap, so content repeats across boundaries.
    assert all(count_words(c) >= MIN_CHUNK_WORDS for c in chunks)


def test_short_document_produces_no_subminimum_noise():
    # Below the minimum-words threshold => dropped (no tiny chunk emitted).
    assert chunk_sentences(["Too short."]) == []
