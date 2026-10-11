# ADR-008 — Frontend Search Page & Result View (slice-18)

## Context

slice-18 implements `/search`, the core page of the app: a search bar with
results listed below showing document title, matched snippet, similarity score,
a semantic/FULLTEXT indicator, and a Redis cache badge. The backend
(`POST /api/search`, slices 09 & 10) returns
`{ results: [{ chunk_id, doc_id, doc_title, snippet, score }], cached }`, where
`score` is the raw cosine distance (lower = closer) and `null` when the MySQL
FULLTEXT fallback produced the result.

## Decisions

- **Route handler proxy for the authenticated search.** `POST /api/search` is a
  Next route handler that reads the `httpOnly` `prism_token` cookie and forwards
  the query to Flask as `Authorization: Bearer <token>`, trimming the query and
  rejecting empty ones with 400. The JWT is never exposed to client JavaScript —
  consistent with the slice-16/17 proxy pattern.
- **The URL `?q=` param is the single source of truth.** The active query lives
  in the URL; the client reads it via `useSearchParams` and a single effect
  (keyed on the query) performs the fetch. This makes criterion 7 (query +
  results persist across navigation) fall out for free — landing on, reloading,
  or using back/forward to reach `/search?q=…` re-runs the same search — and
  guarantees exactly one backend call per query (no duplicate SSR + client
  fetch, so no double logging in `search_log`). Submitting a new query is a
  `router.push` to the new `?q=` URL; resubmitting the identical query refetches
  directly since the URL doesn't change.
- **Classification by score shape.** A `null`/absent `score` is rendered as a
  `fulltext` badge; a numeric score (including `0`) is a `semantic` match and
  shows the cosine distance. The `cached` flag is response-level, so the cache
  badge is shown once in the results header rather than per card.
- **Distinct empty vs. initial states.** `searchedQuery === null` shows a
  "search your library" prompt; a completed search with zero results shows a
  friendly "no matches" empty state — never a blank page (criterion 6).
- **State reset during render, not in an effect.** Per-query UI reset on URL
  change uses React's "adjust state during render" pattern (comparing the live
  query to a committed-query state) instead of a syncing effect, satisfying the
  `react-hooks/set-state-in-effect` rule while keeping loading primed on direct
  landings.
- **Shared utility CSS.** `.spinner`/`.alert-error` (referenced since slice-16
  but never defined) are added to `globals.css` alongside the search-specific
  styles so the loading and error states render correctly app-wide.

## Out of Scope

- No topic/date filters.
- No pagination — top 10 results only (the backend already caps at 10).
