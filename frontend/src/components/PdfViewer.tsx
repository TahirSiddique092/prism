"use client";

import {
  memo,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import type { PDFDocumentProxy, RenderTask, TextLayer } from "pdfjs-dist";
import {
  PAGE_GAP,
  PAGE_PADDING,
  clampPage,
  contentHeight,
  currentPageFor,
  fitWidthScale,
  formatZoom,
  pageOffsets,
  pageStepForKey,
  pagesToRender,
  parsePageInput,
  stepZoom,
  type PageSize,
} from "@/lib/pdfViewer";

type PdfJs = typeof import("pdfjs-dist");

let pdfjsPromise: Promise<PdfJs> | null = null;

/**
 * Load pdf.js once, in the browser only. The worker file is bundled by Next
 * from pdfjs-dist (`new URL(…, import.meta.url)`), so nothing loads from a CDN.
 */
function loadPdfjs(): Promise<PdfJs> {
  pdfjsPromise ??= import("pdfjs-dist").then((pdfjs) => {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString();
    return pdfjs;
  });
  return pdfjsPromise;
}

interface PdfViewerProps {
  /** Pre-signed URL of the PDF. */
  url: string;
  /** Document title, used for the viewer's accessible name. */
  title: string;
  /** Same-origin link that opens a fresh copy of the PDF in a new tab. */
  openHref: string;
}

interface ViewState {
  top: number;
  width: number;
  height: number;
}

/**
 * Document viewer built on pdf.js (slice-26): continuous scrolling with a
 * text layer (selectable text), page navigation, zoom, fit to width, full
 * screen, and open in a new tab. Only the pages in view (plus one either
 * side) are drawn, so long PDFs stay light.
 */
export default function PdfViewer({ url, title, openHref }: PdfViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  // Page to keep in view after the scale changes (zoom, fit, resize).
  const pendingPageRef = useRef<number | null>(null);
  const currentPageRef = useRef(1);

  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [sizes, setSizes] = useState<PageSize[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [fitWidth, setFitWidth] = useState(true);
  const [manualScale, setManualScale] = useState(1);
  const [view, setView] = useState<ViewState>({ top: 0, width: 0, height: 0 });
  const [pageDraft, setPageDraft] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const numPages = sizes.length;
  const maxPageWidth = useMemo(() => sizes.reduce((max, s) => Math.max(max, s.width), 0), [sizes]);
  const scale = fitWidth ? fitWidthScale(view.width, maxPageWidth) : manualScale;
  const offsets = useMemo(() => pageOffsets(sizes, scale), [sizes, scale]);
  const totalHeight = useMemo(() => contentHeight(sizes, scale), [sizes, scale]);
  const currentPage = currentPageFor(offsets, view.top, view.height, totalHeight);
  const [firstToRender, lastToRender] = pagesToRender(offsets, view.top, view.height);

  // Load the document and every page's size (cheap: no drawing yet).
  useEffect(() => {
    let cancelled = false;
    let task: ReturnType<PdfJs["getDocument"]> | null = null;

    loadPdfjs()
      .then(async (pdfjs) => {
        if (cancelled) return;
        task = pdfjs.getDocument({ url });
        const doc = await task.promise;
        const pages = await Promise.all(
          Array.from({ length: doc.numPages }, (_, i) => doc.getPage(i + 1))
        );
        if (cancelled) return;
        setSizes(
          pages.map((page) => {
            const { width, height } = page.getViewport({ scale: 1 });
            return { width, height };
          })
        );
        setPdf(doc);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });

    return () => {
      cancelled = true;
      task?.destroy();
    };
  }, [url]);

  // Track the scroll area's size; fit-to-width follows it (window resize, full screen).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      pendingPageRef.current = currentPageRef.current;
      setView({ top: el.scrollTop, width: el.clientWidth, height: el.clientHeight });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  // After the scale changes, scroll so the page that was in view still is.
  useLayoutEffect(() => {
    const page = pendingPageRef.current;
    const el = scrollRef.current;
    if (page === null || !el || offsets.length === 0) return;
    pendingPageRef.current = null;
    el.scrollTop = offsets[clampPage(page, offsets.length) - 1] - PAGE_PADDING;
  }, [offsets]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(document.fullscreenElement === viewerRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  useEffect(
    () => () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    },
    []
  );

  function handleScroll() {
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null;
      const el = scrollRef.current;
      if (el) setView((v) => ({ ...v, top: el.scrollTop }));
    });
  }

  function goToPage(page: number) {
    const el = scrollRef.current;
    if (!el || numPages === 0) return;
    el.scrollTo({ top: offsets[clampPage(page, numPages) - 1] - PAGE_PADDING });
  }

  function zoom(direction: 1 | -1) {
    pendingPageRef.current = currentPage;
    setManualScale(stepZoom(scale, direction));
    setFitWidth(false);
  }

  function fitToWidth() {
    pendingPageRef.current = currentPage;
    setFitWidth(true);
  }

  function commitPageDraft() {
    if (pageDraft !== null) {
      const page = parsePageInput(pageDraft, numPages);
      if (page !== null) goToPage(page);
    }
    setPageDraft(null);
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      viewerRef.current?.requestFullscreen().catch(() => {});
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const step = pageStepForKey(e.key);
    if (step === 0 || numPages === 0) return;
    e.preventDefault();
    goToPage(currentPage + step);
  }

  const ready = pdf !== null && numPages > 0;

  return (
    <div
      ref={viewerRef}
      className="pdf-viewer"
      role="region"
      aria-label={`PDF viewer: ${title}`}
      onKeyDown={handleKeyDown}
      data-testid="pdf-viewer"
    >
      <div className="pdf-toolbar" data-testid="pdf-toolbar">
        <div className="pdf-toolbar-group">
          <button
            type="button"
            className="pdf-tool-btn"
            onClick={() => goToPage(currentPage - 1)}
            disabled={!ready || currentPage <= 1}
            aria-label="Previous page"
            title="Previous page (PageUp)"
            data-testid="pdf-prev"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <input
            className="pdf-page-input"
            value={pageDraft ?? (ready ? String(currentPage) : "")}
            onChange={(e) => setPageDraft(e.target.value)}
            onFocus={(e) => e.target.select()}
            onBlur={commitPageDraft}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitPageDraft();
              if (e.key === "Escape") setPageDraft(null);
            }}
            disabled={!ready}
            inputMode="numeric"
            aria-label="Page number"
            data-testid="pdf-page-input"
          />
          <span className="pdf-page-count" data-testid="pdf-page-count">
            / {ready ? numPages : "–"}
          </span>
          <button
            type="button"
            className="pdf-tool-btn"
            onClick={() => goToPage(currentPage + 1)}
            disabled={!ready || currentPage >= numPages}
            aria-label="Next page"
            title="Next page (PageDown)"
            data-testid="pdf-next"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>

        <div className="pdf-toolbar-group">
          <button
            type="button"
            className="pdf-tool-btn"
            onClick={() => zoom(-1)}
            disabled={!ready}
            aria-label="Zoom out"
            title="Zoom out"
            data-testid="pdf-zoom-out"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <span className="pdf-zoom-level" data-testid="pdf-zoom-level">
            {ready ? formatZoom(scale) : "–"}
          </span>
          <button
            type="button"
            className="pdf-tool-btn"
            onClick={() => zoom(1)}
            disabled={!ready}
            aria-label="Zoom in"
            title="Zoom in"
            data-testid="pdf-zoom-in"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <button
            type="button"
            className={`pdf-tool-btn pdf-tool-text${fitWidth ? " active" : ""}`}
            onClick={fitToWidth}
            disabled={!ready}
            aria-pressed={fitWidth}
            title="Fit page width"
            data-testid="pdf-fit-width"
          >
            Fit width
          </button>
        </div>

        <div className="pdf-toolbar-group pdf-toolbar-end">
          <a
            className="pdf-tool-btn pdf-tool-text"
            href={openHref}
            target="_blank"
            rel="noopener noreferrer"
            title="Open the PDF in a new tab"
            data-testid="pdf-open-new-tab"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            New tab
          </a>
          <button
            type="button"
            className="pdf-tool-btn pdf-tool-text"
            onClick={toggleFullscreen}
            aria-pressed={isFullscreen}
            title={isFullscreen ? "Exit full screen (Esc)" : "Full screen"}
            data-testid="pdf-fullscreen"
          >
            {isFullscreen ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="4 14 10 14 10 20" />
                <polyline points="20 10 14 10 14 4" />
                <line x1="14" y1="10" x2="21" y2="3" />
                <line x1="3" y1="21" x2="10" y2="14" />
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="15 3 21 3 21 9" />
                <polyline points="9 21 3 21 3 15" />
                <line x1="21" y1="3" x2="14" y2="10" />
                <line x1="3" y1="21" x2="10" y2="14" />
              </svg>
            )}
            {isFullscreen ? "Exit full screen" : "Full screen"}
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="pdf-scroll"
        onScroll={handleScroll}
        tabIndex={0}
        data-testid="pdf-scroll"
      >
        {loadError && (
          <div className="pdf-viewer-state" data-testid="pdf-viewer-error">
            <p>This PDF couldn&apos;t be displayed here.</p>
            <a className="btn btn-secondary btn-sm" href={openHref} target="_blank" rel="noopener noreferrer">
              Open in new tab
            </a>
          </div>
        )}

        {!loadError && !ready && (
          <div className="pdf-viewer-state" data-testid="pdf-viewer-loading">
            <span className="spinner spinner-lg" style={{ marginBottom: 12 }} />
            <p>Loading PDF…</p>
          </div>
        )}

        {ready && (
          <div className="pdf-pages" style={{ padding: PAGE_PADDING }}>
            {sizes.map((size, i) => (
              <PdfPage
                key={i + 1}
                pdf={pdf}
                pageNumber={i + 1}
                size={size}
                scale={scale}
                draw={i + 1 >= firstToRender && i + 1 <= lastToRender}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface PdfPageProps {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  size: PageSize;
  scale: number;
  /** Draw the page; off-screen pages are empty placeholders of the right size. */
  draw: boolean;
}

const PdfPage = memo(function PdfPage({ pdf, pageNumber, size, scale, draw }: PdfPageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!draw) return;
    let cancelled = false;
    let renderTask: RenderTask | null = null;
    let textLayer: TextLayer | null = null;

    (async () => {
      const [pdfjs, page] = await Promise.all([loadPdfjs(), pdf.getPage(pageNumber)]);
      const canvas = canvasRef.current;
      const textDiv = textRef.current;
      if (cancelled || !canvas || !textDiv) return;

      const viewport = page.getViewport({ scale });
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      renderTask = page.render({
        canvas,
        viewport,
        transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
      });
      await renderTask.promise;
      if (cancelled) return;

      textDiv.replaceChildren();
      textLayer = new pdfjs.TextLayer({
        textContentSource: page.streamTextContent(),
        container: textDiv,
        viewport,
      });
      await textLayer.render();
    })().catch((err) => {
      if (!cancelled && err?.name !== "RenderingCancelledException") {
        console.warn(`Failed to render page ${pageNumber}`, err);
      }
    });

    return () => {
      cancelled = true;
      renderTask?.cancel();
      textLayer?.cancel();
    };
  }, [pdf, pageNumber, scale, draw]);

  const width = size.width * scale;
  const height = size.height * scale;
  // pdf.js sizes the text layer from --total-scale-factor.
  const style = { width, height, marginBottom: PAGE_GAP, "--total-scale-factor": scale } as CSSProperties;

  return (
    <div className="pdf-page" style={style} data-page-number={pageNumber}>
      {draw && (
        <>
          <canvas ref={canvasRef} style={{ width, height }} />
          <div ref={textRef} className="textLayer" />
        </>
      )}
    </div>
  );
});
