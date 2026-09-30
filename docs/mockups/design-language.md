# PRISM — Design Language Document
**Personal Relational Intelligent Search Machine**  
*System Design Specification & Visual Standards for PRISM v1*

---

## 1. Design Philosophy & Vision

PRISM is an academic-grade, vector-powered search machine designed for students navigating complex technical literature (DBMS, distributed systems, algorithms) under intense academic pressure. 

### Core Tenets

1. **Optical Clarity (The "Prism" Metaphor)**
   Just as an optical prism takes white light and decomposes it into sharp, structured spectral frequencies, PRISM takes unstructured document PDFs and indexes them into crystalline semantic vectors and relational graph connections. The interface should feel structured, sharp, and illuminating.

2. **Zero Distraction, High Signal-to-Noise Ratio**
   No decorative fluff, no extraneous animations that slow down comprehension. Data density is calibrated for technical readers: clear typographic hierarchy, explicit database states, transparent caching indicators, and instant feedback.

3. **Database Visibility as a Feature**
   PRISM is built for a DBMS course project. Database mechanics (pgvector similarity cosine distance, Redis cache hits, MySQL FULLTEXT fallback triggers, Neo4j topic relationships) are surfaced with dignity. Badges clearly explain *why* and *how* results were retrieved.

4. **Deterministic and Reassuring States**
   Every asynchronous action (PDF chunking, vector embedding, query execution, deletion) has an unambiguous, accessible state: Default, Hover/Focus, Active, Loading/Processing, Empty, and Error.

---

## 2. Brand Identity & Logo System

### The Mark
The PRISM mark is an equilateral geometric prism refracting an incoming beam into a multi-colored gradient spectrum (cyan, indigo, violet).

```text
       /\
      /  \
     /    \  =======> Cyan / Indigo / Violet Spectrum
    /______\
```

- **Wordmark:** `PRISM` in uppercase tracking (`letter-spacing: 0.08em; font-weight: 700;`).
- **Tagline:** *Personal Relational Intelligent Search Machine* (`font-size: 0.75rem; text-transform: uppercase; color: var(--color-text-muted);`).

---

## 3. Color System & Design Tokens

PRISM employs an **Academic Dark Slate** core palette accented by **Refractive Spectrum Tones**. This provides optimal contrast for dense snippet reading and aligns with modern developer tools (Vercel, Supabase, Linear).

### 3.1 Foundations & Neutral Scale

```css
:root {
  /* Surfaces & Backgrounds */
  --color-bg-base:        #090D16; /* Deepest void canvas */
  --color-bg-subtle:      #0F172A; /* Page content background */
  --color-bg-surface:     #1E293B; /* Card & container surface */
  --color-bg-elevated:    #24334A; /* Hovered cards, modals, popovers */
  --color-bg-input:       #0F172A; /* Form input background */
  --color-bg-glass:       rgba(15, 23, 42, 0.75); /* Frosted header */

  /* Borders & Dividers */
  --color-border-subtle:  #1E293B; /* Hairline card borders */
  --color-border-default: #334155; /* Interactive element borders */
  --color-border-strong:  #475569; /* Focused or active borders */
  --color-border-focus:   #3B82F6; /* Primary focus ring */

  /* Text & Content */
  --color-text-primary:   #F8FAFC; /* Primary headings, body copy */
  --color-text-secondary: #CBD5E1; /* Secondary labels, snippets */
  --color-text-muted:     #64748B; /* Metadata, timestamps, helper text */
  --color-text-inverse:   #090D16; /* On primary accent buttons */
}
```

### 3.2 Semantic & Engine Status Accents

Each state directly communicates backend status (pgvector, Redis, MySQL FULLTEXT, Neo4j):

| Semantic Role | Token Name | Color Hex | Background Tint | Meaning & Usage |
|---|---|---|---|---|
| **Primary Brand / Action** | `--color-primary` | `#3B82F6` (Electric Blue) | `rgba(59, 130, 246, 0.12)` | Primary CTA buttons, active tabs, focus rings |
| **Ready / Success** | `--color-success` | `#10B981` (Emerald) | `rgba(16, 185, 129, 0.12)` | Document status `ready`, high similarity scores (>85%) |
| **Processing / Warning** | `--color-warning` | `#F59E0B` (Amber) | `rgba(245, 158, 11, 0.12)` | Document `processing` (chunking/embedding in progress) |
| **Error / Destructive** | `--color-danger` | `#EF4444` (Crimson) | `rgba(239, 68, 68, 0.12)` | Document `error`, deletion modals, invalid inputs |
| **Cache Hit** | `--color-cache` | `#8B5CF6` (Violet) | `rgba(139, 92, 246, 0.15)` | `Cached` badge (Redis query hit, 0ms pgvector bypass) |
| **Fallback Query** | `--color-fallback`| `#F97316` (Tangerine) | `rgba(249, 115, 22, 0.15)` | `FULLTEXT` badge (cosine dist > 0.75 keyword fallback) |
| **Topic Tag** | `--color-topic` | `#06B6D4` (Cyan) | `rgba(6, 182, 212, 0.12)` | Neo4j topic node pills, related graph connections |

---

## 4. Typography Scale & Hierarchies

PRISM uses a modern system font stack configured for crisp rendering across macOS, Windows, and Linux. Monospaced elements use tabular figures for clean numeric alignment in rankings, scores, and chunk counts.

```css
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;

  /* Font Sizes */
  --text-xs:   0.75rem;   /* 12px — Badges, metadata, timestamps */
  --text-sm:   0.875rem;  /* 14px — Table content, helper text, nav links */
  --text-base: 1rem;      /* 16px — Standard body copy, inputs, snippets */
  --text-lg:   1.125rem;  /* 18px — Card headers, subheadings */
  --text-xl:   1.25rem;   /* 20px — Section titles */
  --text-2xl:  1.5rem;    /* 24px — Page titles, hero headers */
  --text-3xl:  1.875rem;  /* 30px — Prominent search prompt, auth titles */

  /* Line Heights */
  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;

  /* Weights */
  --font-regular: 400;
  --font-medium:  500;
  --font-semibold: 600;
  --font-bold:    700;
}
```

### Typographic Roles

- **Page Title (`H1`):** `font-size: var(--text-2xl); font-weight: 700; color: var(--color-text-primary);`
- **Section Heading (`H2`):** `font-size: var(--text-xl); font-weight: 600; color: var(--color-text-primary);`
- **Card Title (`H3`):** `font-size: var(--text-lg); font-weight: 600; color: var(--color-text-primary);`
- **Matched Snippet Text:** `font-size: var(--text-base); line-height: 1.6; color: var(--color-text-secondary);`
- **Snippet Highlight (`<mark>`):** `background: rgba(245, 158, 11, 0.25); color: #FDE68A; font-weight: 600; border-radius: 2px; padding: 0 3px;`
- **Metrics & Scores:** `font-family: var(--font-mono); font-variant-numeric: tabular-nums;`

---

## 5. Spacing, Elevation & Layout Grid

### 5.1 Spacing Scale (8-Point Grid)

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* Border Radii */
  --radius-sm: 4px;   /* Badges, tags, small controls */
  --radius-md: 8px;   /* Inputs, buttons, table containers */
  --radius-lg: 12px;  /* Cards, upload zone */
  --radius-xl: 16px;  /* Modals, prominent search containers */
  --radius-full: 9999px; /* Pill badges */

  /* Shadows & Elevation */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -2px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.6);
  --shadow-glow-primary: 0 0 20px rgba(59, 130, 246, 0.25);
}
```

### 5.2 Layout Boundaries

- **Max Layout Width:** `1200px` (centered with `margin: 0 auto; padding: 0 var(--space-6);`).
- **Global App Shell Header:** Sticky top nav, `64px` height, `backdrop-filter: blur(12px); border-bottom: 1px solid var(--color-border-subtle);`.
- **Target Viewport:** Desktop optimized (min-width `1024px`), resilient to `768px` tablet viewports without breakdown.

---

## 6. Shared Component Specifications

### 6.1 Button Hierarchy

1. **Primary Button:** High visual weight for core triggers (`Log In`, `Search`, `Upload PDF`).
   - Solid electric blue background (`var(--color-primary)`), white text, `font-weight: 600`, subtle outer glow on hover.
2. **Secondary Button:** Surface button for standard actions (`Cancel`, `View Details`, `Back`).
   - Surface background (`var(--color-bg-surface)`), subtle border (`var(--color-border-default)`), hover transition to `var(--color-bg-elevated)`.
3. **Danger Button:** Explicit destructive triggers (`Delete Document`).
   - Crimson tint background (`rgba(239, 68, 68, 0.15)`), red text, red border (`#EF4444`).
4. **Ghost / Icon Button:** Minimal inline actions (`Trash` icon, close buttons).
   - Transparent background, muted text, fills background on hover.

### 6.2 Status Badges & Pills

All badges have uppercase tracking, micro text (`11px` / `0.7rem`), bold weight, and a colored status indicator dot:

- **`ready`:** Green indicator dot + green border + green translucent background.
- **`processing`:** Pulsing amber dot + amber border + amber translucent background.
- **`error`:** Red dot + red border + red translucent background.
- **`cached`:** Violet lightning icon/dot + `Cached (Redis)` label.
- **`fulltext`:** Orange magnifying glass/dot + `FULLTEXT Fallback` label.
- **`score`:** Tabular percentage (e.g. `92% Match`) with gradient bar representation.

### 6.3 Form Inputs & Drag-and-Drop Zone

- **Text & Password Inputs:** Deep background (`#0F172A`), high contrast border, clear labels, helper text, and error states that show an inline red banner without revealing specific vulnerability details.
- **Upload Zone:** Dashed border (`2px dashed var(--color-border-strong)`), prominent cloud upload icon, dragover highlight state (`border-color: var(--color-primary); background: rgba(59, 130, 246, 0.05);`), PDF file format restriction label (`PDF up to 20MB`), and dedicated topic input field.

### 6.4 Search Result Card

The core interaction atom of PRISM:
- **Card Container:** Surface slate with hairline border, interactive hover elevation (`transform: translateY(-1px)`).
- **Header:** Document Title (links directly to `/documents/:doc_id`), accompanied by similarity score pill and metadata badge (`Cached` / `FULLTEXT`).
- **Snippet Box:** Indented quote container with matched chunk text. Matched query terms are highlighted with `<mark>` tags.
- **Footer:** Chunk location info (e.g. `Chunk #4 of 28`), upload timestamp, and quick link `View Full Document →`.

### 6.5 Neo4j Topic Graph Connections & Related Documents

- Pill tags styled in cyan (`#06B6D4`) representing `(Document)-[:ABOUT]->(Topic)` nodes.
- Related document cards displaying `shared_topics` count with an explicit graph icon (`3 shared topics: Normalization, B-Trees, Indexing`).

### 6.6 Confirmation Modal

- Native modern `<dialog>` element rendered via `.showModal()`.
- Blurred backdrop (`backdrop-filter: blur(6px); background: rgba(0, 0, 0, 0.7);`).
- Explicit warning icon, clear destructive message, and side-by-side `Cancel` and `Delete` buttons.

---

## 7. State Matrix Contract

Every page mockup implements the formal state matrix defined in the implementation specification:

| View | States Supported | Visual & Interactive Representation |
|---|---|---|
| **Login / Register** | `Default`, `Loading`, `Error` | Form inputs disable on submit; spinner appears inside primary button; error banner renders below heading. |
| **Dashboard** | `Loaded`, `Empty`, `Uploading`, `Error Badge` | Populated document table vs. friendly empty dropzone; upload progress bar; delete confirmation modal. |
| **Search** | `Default`, `Loading Skeleton`, `Results Loaded`, `Empty Zero-Results` | Prominent search bar; animated skeleton cards during embedding/retrieval; friendly zero-results fallback suggestion. |
| **Document Detail** | `Loaded`, `Empty Related Docs`, `404 Error` | Metadata panel, inline PDF viewer mockup with page navigation, topic pills, related documents list vs. friendly empty note. |
| **Analytics (All 3)** | `Loaded`, `Empty`, `Loading` | Ranked queries table, unsearched docs with encouragement nudge, top docs with appearance counter & avg score. |

---

## 8. Directory & File Reference

All mockups are located under `docs/mockups/`:

- `design-language.md` — *This specification document.*
- `prism-design-system.css` — *Unified CSS design token and component library.*
- `index.html` — *Design System Showcase & Mockup Gallery Hub.*
- `01-login.html` — *Authentication: User Sign In.*
- `02-register.html` — *Authentication: User Registration.*
- `03-dashboard.html` — *Core App: Document Management, Upload & Delete.*
- `04-search.html` — *Core App: Semantic Search & Snippet Matching.*
- `05-document-detail.html` — *Core App: Metadata, Inline PDF Viewer & Topic Graph.*
- `06-analytics-history.html` — *Analytics: Search Query Frequency & Rank.*
- `07-analytics-unsearched.html` — *Analytics: Unsurfaced Uploads & Topic Nudge.*
- `08-analytics-top.html` — *Analytics: Most Frequently Matched Documents.*
