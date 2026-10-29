import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { NextRequest } from "next/server.js";
import { GET as openDocument } from "../src/app/api/documents/[id]/open/route.ts";
import { AUTH_COOKIE } from "../src/lib/auth.ts";
import {
  PAGE_GAP,
  PAGE_PADDING,
  ZOOM_STEPS,
  clampPage,
  contentHeight,
  currentPageFor,
  fitWidthScale,
  formatZoom,
  pageAtOffset,
  pageOffsets,
  pageStepForKey,
  pagesToRender,
  parsePageInput,
  stepZoom,
} from "../src/lib/pdfViewer.ts";

// Three A4-ish pages at scale 1 (PDF points)
const SIZES = [
  { width: 600, height: 800 },
  { width: 600, height: 800 },
  { width: 600, height: 800 },
];

describe("Slice 26 — PDF viewer", () => {
  describe("page navigation", () => {
    it("previous/next stay within the document", () => {
      assert.strictEqual(clampPage(0, 3), 1);
      assert.strictEqual(clampPage(4, 3), 3);
      assert.strictEqual(clampPage(2, 3), 2);
      assert.strictEqual(clampPage(Number.NaN, 3), 1);
    });

    it("accepts a typed page number only if the page exists", () => {
      assert.strictEqual(parsePageInput(" 2 ", 3), 2);
      assert.strictEqual(parsePageInput("3", 3), 3);
      assert.strictEqual(parsePageInput("0", 3), null);
      assert.strictEqual(parsePageInput("4", 3), null);
      assert.strictEqual(parsePageInput("1.5", 3), null);
      assert.strictEqual(parsePageInput("abc", 3), null);
      assert.strictEqual(parsePageInput("", 3), null);
    });

    it("PageUp/PageDown move one page; other keys don't", () => {
      assert.strictEqual(pageStepForKey("PageDown"), 1);
      assert.strictEqual(pageStepForKey("PageUp"), -1);
      assert.strictEqual(pageStepForKey("ArrowDown"), 0);
      assert.strictEqual(pageStepForKey("Enter"), 0);
    });
  });

  describe("layout", () => {
    it("stacks pages with padding above and a gap between", () => {
      assert.deepStrictEqual(pageOffsets(SIZES, 1), [16, 16 + 800 + 16, 16 + 2 * (800 + 16)]);
      assert.deepStrictEqual(pageOffsets(SIZES, 0.5), [16, 16 + 400 + 16, 16 + 2 * (400 + 16)]);
      assert.strictEqual(PAGE_PADDING, 16);
      assert.strictEqual(PAGE_GAP, 16);
    });

    it("total height includes padding top and bottom", () => {
      assert.strictEqual(contentHeight(SIZES, 1), 32 + 3 * 816);
    });

    it("finds the page at a scroll position", () => {
      const offsets = pageOffsets(SIZES, 1);
      assert.strictEqual(pageAtOffset(offsets, 0), 1);
      assert.strictEqual(pageAtOffset(offsets, offsets[1]), 2);
      assert.strictEqual(pageAtOffset(offsets, offsets[1] - 1), 1);
      assert.strictEqual(pageAtOffset(offsets, 99999), 3);
    });

    it("the page box shows the page filling the view, and the last page at the bottom", () => {
      const offsets = pageOffsets(SIZES, 1);
      const total = contentHeight(SIZES, 1);
      assert.strictEqual(currentPageFor(offsets, 0, 700, total), 1);
      // Scrolled to page 2's top (as goToPage does)
      assert.strictEqual(currentPageFor(offsets, offsets[1] - PAGE_PADDING, 700, total), 2);
      // Scrolled to the very bottom: last page even though it can't reach the top
      assert.strictEqual(currentPageFor(offsets, total - 700, 700, total), 3);
    });

    it("draws only the pages in view plus one either side", () => {
      const sizes = Array.from({ length: 20 }, () => ({ width: 600, height: 800 }));
      const offsets = pageOffsets(sizes, 1);
      assert.deepStrictEqual(pagesToRender(offsets, offsets[9], 700), [9, 11]);
      assert.deepStrictEqual(pagesToRender(offsets, 0, 700), [1, 2]);
    });
  });

  describe("zoom", () => {
    it("steps through the zoom levels and stops at the ends", () => {
      assert.strictEqual(stepZoom(1, 1), 1.1);
      assert.strictEqual(stepZoom(1, -1), 0.9);
      assert.strictEqual(stepZoom(1.37, 1), 1.5); // from a fit-width scale
      assert.strictEqual(stepZoom(1.37, -1), 1.25);
      assert.strictEqual(stepZoom(3, 1), ZOOM_STEPS[ZOOM_STEPS.length - 1]);
      assert.strictEqual(stepZoom(0.5, -1), ZOOM_STEPS[0]);
    });

    it("fit width fills the scroll area minus padding", () => {
      assert.strictEqual(fitWidthScale(1232, 600), 2);
      assert.strictEqual(fitWidthScale(0, 600), 1); // not measured yet
      assert.strictEqual(formatZoom(1.2499), "125%");
    });
  });

  it("loads the pdf.js worker from the bundle, never a CDN", () => {
    const source = readFileSync(new URL("../src/components/PdfViewer.tsx", import.meta.url), "utf8");
    assert.match(source, /new URL\(\s*"pdfjs-dist\/build\/pdf\.worker\.min\.mjs",\s*import\.meta\.url\s*\)/);
    assert.doesNotMatch(source, /https?:\/\//);
  });
});

describe("Slice 26 — GET /api/documents/:id/open", () => {
  const originalFetch = globalThis.fetch;
  const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token";
  const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
  const request = (id: string, withCookie = true) =>
    new NextRequest(`http://localhost:3000/api/documents/${id}/open`, {
      method: "GET",
      headers: withCookie ? { cookie: `${AUTH_COOKIE}=${mockToken}` } : {},
    });

  after(() => {
    globalThis.fetch = originalFetch;
  });

  it("redirects to a freshly fetched pre-signed URL every time", async () => {
    let calls = 0;
    const forwarded: string[] = [];
    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      calls += 1;
      forwarded.push(`${url} ${(init?.headers as Record<string, string>)["Authorization"]}`);
      return new Response(JSON.stringify({ view_url: `https://storage.example.com/doc.pdf?sig=${calls}` }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const first = await openDocument(request("7"), ctx("7"));
    const second = await openDocument(request("7"), ctx("7"));

    assert.strictEqual(first.status, 307);
    assert.strictEqual(first.headers.get("location"), "https://storage.example.com/doc.pdf?sig=1");
    assert.strictEqual(second.headers.get("location"), "https://storage.example.com/doc.pdf?sig=2");
    assert.match(forwarded[0], /\/api\/documents\/7\/url Bearer /);
  });

  it("sends a signed-out visitor to /login (relative, so the browser keeps its host)", async () => {
    const res = await openDocument(request("7", false), ctx("7"));
    assert.strictEqual(res.status, 307);
    assert.strictEqual(res.headers.get("location"), "/login");
  });

  it("sends an expired session to /login", async () => {
    globalThis.fetch = (async () => new Response("{}", { status: 401 })) as typeof fetch;
    const res = await openDocument(request("7"), ctx("7"));
    assert.strictEqual(res.headers.get("location"), "/login");
  });

  it("returns 404 for a document the user doesn't own", async () => {
    globalThis.fetch = (async () => new Response(JSON.stringify({ error: "Document not found" }), { status: 404 })) as typeof fetch;
    const res = await openDocument(request("99"), ctx("99"));
    assert.strictEqual(res.status, 404);
  });

  it("returns 400 for a non-numeric id and 502 when Flask is unreachable", async () => {
    assert.strictEqual((await openDocument(request("abc"), ctx("abc"))).status, 400);
    globalThis.fetch = (async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof fetch;
    assert.strictEqual((await openDocument(request("7"), ctx("7"))).status, 502);
  });
});
