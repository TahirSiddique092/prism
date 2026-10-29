# slice-26 — PDF viewer: full screen and open in new tab

**Sprint:** 7 — Hardening and UX
**Module:** frontend

## What to build

Replace the embedded `<iframe>` preview on the document page with a pdf.js viewer that is larger, can go full screen, and can open the PDF in a new tab.

## Changes

### 1. pdf.js viewer
**Problem:** The preview is an `<iframe>` with a fixed height of 640 px, in two-thirds of the page (750 px wide on a 1440 px screen). It can't be enlarged or opened separately. It also uses the browser's built-in PDF viewer, which the page can't control, and slice-27 needs to move it to a page and highlight text.

**Change:**
- Add `pdfjs-dist` and a client component `frontend/src/components/PdfViewer.tsx`. It renders the PDF from the pre-signed URL into canvases with a text layer, so text stays selectable, and scrolls continuously through the pages.
- Toolbar: previous/next page, a page box showing "N / M" that accepts a typed page number, zoom in/out, and fit to width. PageUp/PageDown also move between pages.
- Load the pdf.js worker from the bundled `pdfjs-dist` file, not from a CDN.
- No infra change is needed: the storage bucket already returns `Access-Control-Allow-Origin: *` and supports range requests (checked 29 Oct 2026), so pdf.js can read the pre-signed URL directly.

### 2. Full screen and open in new tab
- **Full screen:** toggles the Fullscreen API on the viewer container, toolbar included. Esc or the button exits.
- **Open in new tab:** fetches a fresh URL from `/api/documents/:id/url` and opens it in a new tab with `noopener`. Pre-signed URLs expire after an hour, so it does not reuse the URL fetched when the page loaded.
- If the PDF fails to load, the error state shows "Open in new tab" as a fallback.

### 3. Layout
- The viewer uses the full content width. Its height is the window height minus the header, with a sensible minimum.
- Related Documents moves below the viewer.
- Change the card label "Served from MinIO" to "Served from object storage". Storage has been Neon Object Storage since ADR-015.

## Acceptance criteria

- The document page renders the PDF with pdf.js, and text in it can be selected and copied
- At 1440×900 the viewer is at least 1100 px wide and 700 px tall
- Full screen puts the viewer and its toolbar in full screen, and both Esc and the button exit it
- Open in new tab opens the PDF in a new tab using a freshly fetched URL
- Previous/next, a typed page number and PageUp/PageDown all move to the right page, and the box shows "N / M"
- The loading and error states still work, and the error state offers Open in new tab
- No request goes to a third-party CDN for pdf.js
- Frontend tests cover the toolbar actions, with pdf.js mocked

## Out of scope

- Opening at a specific passage or highlighting text (slice-27)
- Annotations, a thumbnail sidebar, or text search inside the PDF
- Any backend change

## Assigned To

Unassigned

## Human review required?

No.
