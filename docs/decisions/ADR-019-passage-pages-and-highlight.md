# ADR-019 — Finding a search result's page and highlighting it

## Context

Slice-27 opens a search result at the page where its passage is and highlights it. The worker used to join the text of every page before splitting it into sentences, so chunks had no page. The viewer (pdf.js) also extracts text differently from the backend (PyMuPDF): spacing, line breaks, bullets and ligatures differ, so the chunk text can't be found in the page by exact comparison.

## Decision

- **Pages are recorded when a document is processed.** The worker remembers where each page starts in the joined text. Punkt returns sentences as pieces of that text in order, so each sentence is located with a forward search, and each chunk gets the page of its first and last character. Chunks cut as word windows from one oversized sentence (common on slides without full stops) use the positions of their own first and last words. `chunk_pages()` reuses the existing chunker, so chunk text and boundaries are unchanged; a test compares it with the previous implementation on 200 generated inputs.
- **Old chunks are backfilled, not re-processed.** `backfill_chunk_pages.py` re-splits each PDF and writes pages only if the result is identical to the stored chunks. Re-processing would have created new chunk IDs and broken `search_results` history.
- **Highlighting matches letters and digits only.** Both texts are reduced to lower-case letters and digits (NFKC). The passage's start is located by its first 48 characters, retrying a little further in if the very start differs. Its end is located the same way from its last 48 characters. A passage that starts at the bottom of a page is matched against the page's last few characters; one that ends at the top is matched against its first few. Pages between the first and last are highlighted entirely. The whole pdf.js text item (usually one line) containing matched text is marked.

## Consequences

- On the test PDFs, all 15 results opened from three searches were highlighted on the right pages.
- Highlighting works line by line, not word by word, so a line that is only partly in the passage is marked whole.
- A chunk's first page can be the bottom of a slide with only a footer line of the passage; the viewer then scrolls to that line, with the rest of the passage on the next page.
- Results whose page is unknown (not backfilled yet) open at page 1 without a highlight.
