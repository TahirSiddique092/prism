/**
 * Opening a search result at its passage (slice-27).
 *
 * A result links to /documents/:id?chunk=:chunkId&page=:page. The document
 * page fetches the chunk's text and pages, opens the viewer at the first page
 * and highlights the passage in the pdf.js text layer.
 *
 * The chunk text comes from the backend's PDF extraction (PyMuPDF), while the
 * text layer comes from pdf.js. Spacing, line breaks and some symbols differ
 * between the two, so text is compared with only letters and digits kept.
 */

export interface PassageTarget {
  chunkId: number;
  /** First page of the passage, if the search result knew it. */
  page: number | null;
}

export interface PassageHighlight {
  text: string;
  pageStart: number;
  pageEnd: number;
}

/** Where a page sits within a passage. */
export type PagePosition = "only" | "start" | "middle" | "end";

/** Link from a search result to its passage. */
export function passageHref(docId: number, chunkId: number, page?: number | null): string {
  const base = `/documents/${docId}?chunk=${chunkId}`;
  return page ? `${base}&page=${page}` : base;
}

function positiveInt(value: string | null): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const n = Number(value);
  return n >= 1 ? n : null;
}

/** The passage a document page was opened for, read from ?chunk=&page=. */
export function parsePassageParams(params: { get(name: string): string | null }): PassageTarget | null {
  const chunkId = positiveInt(params.get("chunk"));
  if (chunkId === null) return null;
  return { chunkId, page: positiveInt(params.get("page")) };
}

/** How a page relates to a passage spanning pageStart…pageEnd, or null if outside it. */
export function pagePosition(page: number, pageStart: number, pageEnd: number): PagePosition | null {
  if (page < pageStart || page > pageEnd) return null;
  if (pageStart === pageEnd) return "only";
  if (page === pageStart) return "start";
  if (page === pageEnd) return "end";
  return "middle";
}

/** Letters and digits only, lower-cased, ligatures and widths unified (NFKC). */
export function normalizeForMatch(text: string): string {
  return text.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

const ANCHOR = 48; // characters compared to find where the passage starts or ends
const MIN_ANCHOR = 16; // shortest anchor accepted anywhere on the page
const MIN_EDGE = 4; // shortest piece accepted at the very top or bottom of a page
const ANCHOR_SHIFTS = [0, 12, 24, 36]; // retry a little inside the passage if its edge differs

/** Index in `page` where `passage` starts, or null. */
function locateStart(page: string, passage: string): number | null {
  for (const shift of ANCHOR_SHIFTS) {
    const anchor = passage.slice(shift, shift + ANCHOR);
    if (anchor.length < MIN_ANCHOR) break;
    const at = page.indexOf(anchor);
    if (at >= 0) return Math.max(0, at - shift);
  }
  // The passage starts at the bottom of this page and continues on the next.
  for (let length = Math.min(ANCHOR, passage.length); length >= MIN_EDGE; length--) {
    if (page.endsWith(passage.slice(0, length))) return page.length - length;
  }
  return null;
}

/** Index in `page` just after where `passage` ends, or null. */
function locateEnd(page: string, passage: string): number | null {
  for (const shift of ANCHOR_SHIFTS) {
    const end = passage.length - shift;
    const anchor = passage.slice(Math.max(0, end - ANCHOR), end);
    if (anchor.length < MIN_ANCHOR) break;
    const at = page.indexOf(anchor);
    if (at >= 0) return Math.min(page.length, at + anchor.length + shift);
  }
  // The passage started on the previous page and ends at the top of this one.
  for (let length = Math.min(ANCHOR, passage.length); length >= MIN_EDGE; length--) {
    if (page.startsWith(passage.slice(passage.length - length))) return length;
  }
  return null;
}

/**
 * Which text items of a page belong to the passage.
 *
 * `items` are the page's text items in order (pdf.js textContentItemsStr).
 * Returns their indices, or null if the passage can't be found on the page.
 */
export function findPassageItems(items: string[], passageText: string, position: PagePosition): number[] | null {
  const passage = normalizeForMatch(passageText);
  if (!passage) return null;

  let page = "";
  const itemAt: number[] = []; // item index of each character of `page`
  items.forEach((item, index) => {
    const normalized = normalizeForMatch(item);
    page += normalized;
    for (let k = 0; k < normalized.length; k++) itemAt.push(index);
  });
  if (!page) return null;

  let start: number | null = 0;
  let end: number | null = page.length;
  if (position === "only") {
    start = locateStart(page, passage);
    end = locateEnd(page, passage);
    if (start !== null && end !== null && end <= start) end = null;
    if (start === null && end === null) return null;
    if (start === null) start = Math.max(0, (end as number) - passage.length);
    if (end === null) end = Math.min(page.length, start + passage.length);
  } else if (position === "start") {
    start = locateStart(page, passage);
  } else if (position === "end") {
    end = locateEnd(page, passage);
  }
  if (start === null || end === null || end <= start) return null;

  const indices = new Set<number>();
  for (let pos = start; pos < end; pos++) indices.add(itemAt[pos]);
  return [...indices].sort((a, b) => a - b);
}
