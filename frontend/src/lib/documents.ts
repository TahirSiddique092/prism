/**
 * Dashboard document-list helpers (slice-28).
 */

/** How often the dashboard re-reads the list while a document is processing. */
export const STATUS_POLL_MS = 3000;

interface ListedDocument {
  doc_id: number;
  status: string;
  chunk_count: number;
}

/** True while any document is still being processed (the dashboard polls until it isn't). */
export function hasProcessing(docs: ListedDocument[]): boolean {
  return docs.some((doc) => doc.status === "processing");
}

/** The list after a retry was accepted: that document is processing again, with no chunks yet. */
export function markRetrying<T extends ListedDocument>(docs: T[], docId: number): T[] {
  return docs.map((doc) => (doc.doc_id === docId ? { ...doc, status: "processing", chunk_count: 0 } : doc));
}
