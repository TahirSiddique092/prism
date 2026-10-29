"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { formatSimilarity, SIMILARITY_TOOLTIP } from "@/lib/scores";

export interface SearchResult {
  chunk_id: number;
  doc_id: number;
  doc_title: string;
  snippet: string;
  /** Raw cosine distance (lower = closer); null when the FULLTEXT fallback was used. */
  score: number | null;
}

/** True when the result came from the MySQL FULLTEXT fallback rather than pgvector. */
function isFallback(result: SearchResult): boolean {
  return result.score === null || result.score === undefined;
}

export default function SearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeQuery = (searchParams.get("q") ?? "").trim();

  // The text in the input box — seeded from the URL, editable independently.
  const [inputQuery, setInputQuery] = useState(activeQuery);

  const [results, setResults] = useState<SearchResult[]>([]);
  const [cached, setCached] = useState(false);
  // Seed loading from the URL so landing directly on /search?q=… shows the
  // loading state immediately, before the fetch effect has a chance to run.
  const [loading, setLoading] = useState(() => Boolean(activeQuery));
  const [error, setError] = useState<string | null>(null);
  // Distinguishes "no search run yet" from "searched and got zero results".
  const [searchedQuery, setSearchedQuery] = useState<string | null>(null);

  // The query the user just submitted, if any. Only a submitted search is
  // logged for analytics; results restored from the URL (Back/Forward, reload,
  // an opened link) are fetched with log: false so they aren't counted again
  // (slice-25).
  const submittedQuery = useRef<string | null>(null);

  // When the URL's `?q=` changes (back/forward, a shared link, or a new submit)
  // reset the per-query UI synchronously during render — React's recommended
  // alternative to a state-syncing effect.
  const [committedQuery, setCommittedQuery] = useState(activeQuery);
  if (activeQuery !== committedQuery) {
    setCommittedQuery(activeQuery);
    setInputQuery(activeQuery);
    setError(null);
    if (activeQuery) {
      setLoading(true);
    } else {
      setResults([]);
      setCached(false);
      setSearchedQuery(null);
      setLoading(false);
    }
  }

  // The URL's `?q=` param is the single source of truth: whenever it changes we
  // (re)run the search. This makes back/forward and reload restore results for
  // free (criterion 7) and keeps every search to exactly one backend call. All
  // state updates happen inside the async callback (never synchronously in the
  // effect body) so loading is primed by the render-time block above.
  useEffect(() => {
    if (!activeQuery) return;

    let ignore = false;
    const log = submittedQuery.current === activeQuery;
    submittedQuery.current = null;

    (async () => {
      try {
        const res = await fetch("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: activeQuery, log }),
        });

        const data = await res.json().catch(() => ({}));
        if (ignore) return;

        if (!res.ok) {
          setResults([]);
          setCached(false);
          setError(
            typeof data?.error === "string"
              ? data.error
              : "Search failed. Please try again."
          );
          setSearchedQuery(activeQuery);
          return;
        }

        setResults(Array.isArray(data?.results) ? data.results : []);
        setCached(Boolean(data?.cached));
        setSearchedQuery(activeQuery);
      } catch {
        if (ignore) return;
        setResults([]);
        setCached(false);
        setError("Network error while searching. Please try again.");
        setSearchedQuery(activeQuery);
      } finally {
        if (!ignore) setLoading(false);
      }
    })();

    return () => {
      ignore = true;
    };
  }, [activeQuery]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputQuery.trim();
    if (!trimmed) return;

    if (trimmed === activeQuery) {
      // Same query resubmitted — the URL won't change, so refetch manually.
      refetch(trimmed);
      return;
    }

    // Record the query in the URL; the effect above performs the fetch and this
    // creates a history entry so navigating away and back restores the query.
    submittedQuery.current = trimmed;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  const inFlight = useRef(false);
  async function refetch(query: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Resubmitting the same query is a real search, so it is logged.
        body: JSON.stringify({ query, log: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setResults([]);
        setCached(false);
        setError(
          typeof data?.error === "string"
            ? data.error
            : "Search failed. Please try again."
        );
      } else {
        setResults(Array.isArray(data?.results) ? data.results : []);
        setCached(Boolean(data?.cached));
      }
      setSearchedQuery(query);
    } catch {
      setResults([]);
      setCached(false);
      setError("Network error while searching. Please try again.");
      setSearchedQuery(query);
    } finally {
      setLoading(false);
      inFlight.current = false;
    }
  }

  const showEmptyState =
    !loading && !error && searchedQuery !== null && results.length === 0;
  const showResults = !loading && !error && results.length > 0;
  const showInitialPrompt = !loading && !error && searchedQuery === null;

  return (
    <main className="main-content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Semantic Search</h1>
          <p className="page-subtitle">
            Ask in plain English. PRISM embeds your query and finds the closest
            passages across your library, falling back to full-text matching
            when needed.
          </p>
        </div>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="search-bar" role="search">
        <div className="search-input-wrap">
          <svg
            className="search-input-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="search"
            className="form-input search-input"
            placeholder="e.g. How does a B-tree index speed up range queries?"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            aria-label="Search query"
            autoFocus
            data-testid="search-input"
          />
        </div>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !inputQuery.trim()}
          data-testid="search-button"
        >
          {loading ? (
            <>
              <span className="spinner" />
              <span>Searching…</span>
            </>
          ) : (
            <span>Search</span>
          )}
        </button>
      </form>

      {/* Loading state */}
      {loading && (
        <div className="search-loading" data-testid="search-loading" aria-live="polite">
          <span className="spinner spinner-lg" />
          <p>Searching your library for “{activeQuery}”…</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="alert-error" role="alert" data-testid="search-error">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* Results header */}
      {showResults && (
        <div className="search-results-header">
          <span data-testid="results-count">
            {results.length} result{results.length === 1 ? "" : "s"} for{" "}
            <strong style={{ color: "var(--color-text-primary)" }}>
              “{searchedQuery}”
            </strong>
          </span>
          {cached && (
            <span className="badge badge-cached" data-testid="cached-badge" title="Served from Redis cache">
              <span className="badge-dot" style={{ background: "#a855f7" }} />
              cached
            </span>
          )}
        </div>
      )}

      {/* Results list */}
      {showResults && (
        <div className="search-results" data-testid="search-results">
          {results.map((result) => (
            <Link
              key={result.chunk_id}
              href={`/documents/${result.doc_id}`}
              className="result-card"
              data-testid={`result-card-${result.chunk_id}`}
            >
              <div className="result-card-head">
                <span className="result-title" data-testid={`result-title-${result.chunk_id}`}>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#EF4444"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  {result.doc_title}
                </span>
                <div className="result-meta">
                  {isFallback(result) ? (
                    <span
                      className="badge badge-fallback"
                      data-testid={`match-type-${result.chunk_id}`}
                      title="Returned by MySQL FULLTEXT fallback"
                    >
                      fulltext
                    </span>
                  ) : (
                    <span
                      className="badge badge-semantic"
                      data-testid={`match-type-${result.chunk_id}`}
                      title="Returned by pgvector semantic search"
                    >
                      semantic
                    </span>
                  )}
                  {!isFallback(result) && (
                    <span
                      className="result-score"
                      data-testid={`result-score-${result.chunk_id}`}
                      title={SIMILARITY_TOOLTIP}
                    >
                      {formatSimilarity(result.score)}
                    </span>
                  )}
                </div>
              </div>
              <p className="result-snippet" data-testid={`result-snippet-${result.chunk_id}`}>
                {result.snippet}
              </p>
            </Link>
          ))}
        </div>
      )}

      {/* Empty state — searched but no matches */}
      {showEmptyState && (
        <div className="empty-state" data-testid="empty-state">
          <div className="empty-icon-wrap">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <h3 className="empty-title">No matches for “{searchedQuery}”</h3>
          <p className="empty-desc">
            We couldn&apos;t find anything in your library for that query. Try
            rephrasing, using different keywords, or uploading more documents.
          </p>
          <Link href="/dashboard" className="btn btn-secondary btn-sm">
            Go to your documents
          </Link>
        </div>
      )}

      {/* Initial prompt — nothing searched yet */}
      {showInitialPrompt && (
        <div className="empty-state" data-testid="initial-prompt">
          <div className="empty-icon-wrap">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <h3 className="empty-title">Search your study library</h3>
          <p className="empty-desc">
            Type a question above and hit Enter. Results are ranked by semantic
            similarity, with a full-text fallback for exact-keyword matches.
          </p>
        </div>
      )}
    </main>
  );
}
