/**
 * Layout and navigation helpers for the pdf.js viewer (slice-26).
 *
 * Kept free of pdf.js and the DOM so they can be unit-tested. Pages are
 * stacked vertically: PAGE_PADDING above the first page, PAGE_GAP between
 * pages. The viewer component uses the same constants for its styles, so
 * the offsets computed here match the rendered layout exactly.
 */

export const PAGE_PADDING = 16;
export const PAGE_GAP = 16;

/** Zoom levels the − / + buttons step through. */
export const ZOOM_STEPS = [0.5, 0.67, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];

export interface PageSize {
  /** Width at scale 1, in PDF points. */
  width: number;
  /** Height at scale 1, in PDF points. */
  height: number;
}

/** A page number limited to 1…numPages. */
export function clampPage(page: number, numPages: number): number {
  if (numPages < 1 || !Number.isFinite(page)) return 1;
  return Math.min(Math.max(Math.round(page), 1), numPages);
}

/** The page typed into the toolbar box, or null if it isn't a page of this document. */
export function parsePageInput(text: string, numPages: number): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const page = Number(trimmed);
  return page >= 1 && page <= numPages ? page : null;
}

/** The next zoom level above (direction 1) or below (direction -1) the current scale. */
export function stepZoom(scale: number, direction: 1 | -1): number {
  if (direction > 0) {
    return ZOOM_STEPS.find((step) => step > scale + 0.001) ?? ZOOM_STEPS[ZOOM_STEPS.length - 1];
  }
  return [...ZOOM_STEPS].reverse().find((step) => step < scale - 0.001) ?? ZOOM_STEPS[0];
}

/** Scale at which the widest page fills the available width. */
export function fitWidthScale(containerWidth: number, pageWidth: number): number {
  const available = containerWidth - 2 * PAGE_PADDING;
  if (pageWidth <= 0 || available <= 0) return 1;
  return available / pageWidth;
}

/** "125%" style label for a scale. */
export function formatZoom(scale: number): string {
  return `${Math.round(scale * 100)}%`;
}

/** How many pages a key press moves: PageDown → 1, PageUp → -1, anything else → 0. */
export function pageStepForKey(key: string): -1 | 0 | 1 {
  if (key === "PageDown") return 1;
  if (key === "PageUp") return -1;
  return 0;
}

/** Top offset (CSS px) of every page at the given scale. */
export function pageOffsets(sizes: PageSize[], scale: number): number[] {
  const offsets: number[] = [];
  let top = PAGE_PADDING;
  for (const size of sizes) {
    offsets.push(top);
    top += size.height * scale + PAGE_GAP;
  }
  return offsets;
}

/** The page (1-based) whose area contains the given scroll position. */
export function pageAtOffset(offsets: number[], y: number): number {
  let low = 0;
  let high = offsets.length - 1;
  let found = 0;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (offsets[mid] <= y) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return found + 1;
}

/** Height (CSS px) of all pages with their padding and gaps at the given scale. */
export function contentHeight(sizes: PageSize[], scale: number): number {
  const pages = sizes.reduce((sum, size) => sum + size.height * scale + PAGE_GAP, 0);
  return 2 * PAGE_PADDING + pages;
}

/**
 * The current page for a scroll position: the page under a point a third of
 * the way down the visible area, so a page counts as current once it fills
 * most of the view. Scrolled to the very bottom, it is the last page, even if
 * that page is too short to reach the one-third point.
 */
export function currentPageFor(
  offsets: number[],
  scrollTop: number,
  viewHeight: number,
  totalHeight = Infinity
): number {
  if (offsets.length === 0) return 1;
  if (viewHeight > 0 && scrollTop + viewHeight >= totalHeight - 1) return offsets.length;
  return pageAtOffset(offsets, scrollTop + viewHeight / 3);
}

/** First and last page (1-based) to render: those in view plus `buffer` pages either side. */
export function pagesToRender(
  offsets: number[],
  scrollTop: number,
  viewHeight: number,
  buffer = 1
): [number, number] {
  if (offsets.length === 0) return [1, 0];
  const first = pageAtOffset(offsets, scrollTop);
  const last = pageAtOffset(offsets, scrollTop + viewHeight);
  return [Math.max(1, first - buffer), Math.min(offsets.length, last + buffer)];
}
