/**
 * Shared analytics models, navigation descriptors, and formatting helpers (slice-19).
 */

export interface SearchHistoryItem {
  query_text: string;
  search_count: number;
  query_rank: number;
  last_searched: string | null;
  total_searches: number;
}

export interface UnsearchedDocumentItem {
  doc_id: number;
  title: string;
  uploaded_at: string | null;
}

export interface TopDocumentItem {
  doc_id: number;
  title: string;
  /** Number of searches the document appeared in (slice-25). */
  search_count: number;
  /** Number of its passages returned across those searches (up to 10 per search). */
  appearance_count: number;
  /** Average cosine distance; shown as similarity via formatSimilarity. */
  avg_score: number | null;
}

export const ANALYTICS_NAV_ITEMS = [
  {
    href: "/analytics/history",
    label: "Search History",
    id: "history",
  },
  {
    href: "/analytics/unsearched",
    label: "Unsearched Documents",
    id: "unsearched",
  },
  {
    href: "/analytics/top-documents",
    label: "Top Documents",
    id: "top-documents",
  },
] as const;

export const UNSEARCHED_NUDGE_MESSAGE =
  "These documents have never come up in a search — try searching for their topics";

/**
 * Formats an ISO string to "Month Day, Year" (e.g. "Oct 11, 2026").
 */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return String(isoString);
  }
}

/**
 * Formats an ISO string to "Month Day, Year, Time" (e.g. "Oct 11, 2026, 1:45 PM").
 */
export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return String(isoString);
  }
}

/**
 * Sorts search history items by query_rank ascending (rank 1 at top).
 */
export function sortHistoryByRank(items: SearchHistoryItem[]): SearchHistoryItem[] {
  return [...items].sort((a, b) => a.query_rank - b.query_rank);
}

/**
 * Sorts top documents by search_count, then appearance_count, both descending
 * (the backend's order, slice-25).
 */
export function sortTopDocsByCount(items: TopDocumentItem[]): TopDocumentItem[] {
  return [...items].sort(
    (a, b) =>
      (b.search_count ?? 0) - (a.search_count ?? 0) ||
      b.appearance_count - a.appearance_count
  );
}
