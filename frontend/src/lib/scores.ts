/**
 * Match scores shown in the UI (slice-25).
 *
 * pgvector returns cosine DISTANCE (lower = closer), and the API passes it on
 * unchanged. Every page shows the same match as cosine SIMILARITY,
 * 1 − distance (higher = closer), so a score means the same thing everywhere.
 */

export const SIMILARITY_TOOLTIP = "Cosine similarity — higher is closer";

/** 1 − distance to 4 decimals, or null when there is no score (FULLTEXT results). */
export function formatSimilarity(distance: number | null | undefined): string | null {
  if (distance === null || distance === undefined || Number.isNaN(distance)) {
    return null;
  }
  return (1 - distance).toFixed(4);
}
