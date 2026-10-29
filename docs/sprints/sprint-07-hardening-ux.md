# Sprint-07-hardening-ux

> A sprint is a feature-level chunk of the Architecture — sized to however much you'll realistically tackle in one work block (a few hours, an all-nighter, a weekend). Not tied to a calendar week.

## Goal

Make PRISM dependable for everyday studying. Every store agrees with MySQL. The analytics report what really happened. Searches feel instant. A search result opens the PDF at the passage it found.

## Slices in this sprint

- [x]  `slice-24-cross-store-consistency` — Cross-store consistency fixes — **Unassigned**
- [ ]  `slice-25-analytics-accuracy` — Analytics accuracy: time zones, restored searches, search counts, one score scale — **Unassigned**
- [ ]  `slice-26-pdf-viewer` — pdf.js viewer with full screen and open in new tab — **Unassigned**
- [ ]  `slice-27-jump-to-passage` — Open a search result at its page, with the passage highlighted — **Unassigned**
- [ ]  `slice-28-dashboard-status-retry` — Live processing status, retry failed documents — **Unassigned**
- [x]  `slice-29-search-cache-speed` — Reuse Redis and Postgres connections so cached searches are fast — **Unassigned**
- [x]  `slice-30-prism-favicon` — PRISM favicon instead of the Next.js default — **Unassigned**

Also shipped during this sprint, outside the slice plan: the hotfix in PR #39 (prepared statements for free-text MySQL queries, ADR-017).

## Suggested order

1. **slice-29**: fixes the slow cache, the most visible problem, and makes every later test run faster.
2. **slice-25**: makes the analytics correct before more data piles up.
3. **slice-30**: small and independent.
4. **slice-26**, then **slice-27**: slice-27 needs the pdf.js viewer from slice-26.
5. **slice-28**: independent; can run in parallel with any of the above.

## Depends on

Sprint 6. The app runs end to end against the managed data services (ADR-015).

## Open questions (decide before scheduling)

1. **Weak search results.** Search always returns the 10 nearest passages, however weak. The 10th result for "before insert trigger with delimiter" had cosine distance 0.64. Neighbouring passages from one PDF also repeat the same sentences, because chunks overlap. Possible fixes: drop results beyond a cutoff, and/or group results by document. AGENTS.md fixes the 0.75 fallback threshold for v1, so either change needs an ADR.
2. **Slide footers in passages.** Repeated slide text such as "Database Management Systems 58" ends up in passages, snippets and embeddings. Once slice-27 tracks pages, repeated header and footer lines could be stripped per page. That changes chunk text, so existing documents would need re-processing.
3. **Service regions.** Every query from India to Redis and Postgres costs a 230–550 ms round trip, even on a reused connection (see slice-29). Moving them to a nearer region would cut that further. This is an infra choice, possible only if the free tiers allow it.

## Notes for next time

*(Leave blank unless something actually broke, a slice was mis-sized, or the agent went off-script.)*
