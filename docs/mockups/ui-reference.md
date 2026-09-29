# PRISM — UI Reference (for Mockups & Design Language)

> This doc tells the designer **what pages we need and what goes on each one**. It does NOT prescribe visual style — that's the designer's call.

---

## Page Inventory

| # | Page | Route | Complexity |
|---|------|-------|------------|
| 1 | Login | `/login` | Simple |
| 2 | Register | `/register` | Simple |
| 3 | Dashboard (Upload & List) | `/dashboard` | Medium |
| 4 | Search | `/search` | Complex |
| 5 | Document Detail | `/documents/:doc_id` | Medium |
| 6 | Analytics — History | `/analytics/history` | Simple |
| 7 | Analytics — Unsearched | `/analytics/unsearched` | Simple |
| 8 | Analytics — Top Documents | `/analytics/top-documents` | Simple |

**Total: 8 views**

---

## Auth Pages

### 1. Login Page
The entry point for returning users.

**Elements:**
- Email input field
- Password input field
- "Log in" button
- Link to "Create an account" (Register page)
- Generic error message area (e.g., "Invalid credentials")

**States:**
- Default (empty)
- Loading (waiting for auth response)
- Error (failed login)

### 2. Register Page
For new users to create an account.

**Elements:**
- Name input field
- Email input field
- Password input field
- "Sign up" button
- Link to "Log in" (Login page)

**States:**
- Default
- Loading
- Error (e.g., "Email already in use")

---

## Core Application

### 3. Dashboard (Home / Document List)
The landing page after login. Shows the user's uploaded documents and allows uploading new ones.

**Elements:**
- **Global Navigation Bar:** Links to Dashboard, Search, Analytics, and Logout.
- **Upload Zone:** 
  - Drag-and-drop area for PDF files (Max 20MB limit text).
  - Text input for comma-separated Topic tags (e.g., "SQL, Normalization").
  - Upload progress indicator.
- **Document List:** Table or grid showing:
  - Document Title
  - Upload Date
  - Chunk Count (if available)
  - Status badge (`processing`, `ready`, `error`)
  - Delete action (Trash icon/button)
- **Delete Confirmation Modal:** "Are you sure you want to delete this document?"

**States:**
- Loaded (list populated)
- Empty ("Upload your first document")
- Uploading (file transfer in progress)

### 4. Search Page
The core interaction page. Users search their documents using natural language.

**Elements:**
- **Search Bar:** Large, prominent text input + Submit button.
- **Results List:** 
  - Card-based layout for each result showing:
    - Document Title (clickable, links to Document Detail)
    - Matched text snippet (with highlights if possible)
    - Similarity score (e.g., "89% match")
    - Badges: `Cached` (if from Redis), `FULLTEXT` (if fallback was used).
- **Empty State:** Friendly message if no results found.

**States:**
- Default (ready to search, maybe show previous query if `?q=` in URL)
- Loading (spinner/skeleton while searching)
- Results loaded (ordered by score)
- Empty (zero results)

### 5. Document Detail Page
Shows metadata for a specific document, its topic graph relationships, and an inline PDF viewer for reading the document directly.

**Elements:**
- **Header:** Document Title, Upload Date, File Size, Page Count, Status.
- **Topics:** List of topic tags (pill/badge UI).
- **Inline PDF Viewer:** A large embedded view (e.g., iframe or standard PDF renderer) showing the original document.
- **Related Documents Section:** (Could be in a sidebar next to the PDF viewer or below)
  - Up to 5 related documents (cards or list).
  - Shows shared topic count.
  - Links to those documents' detail pages.
- **Action:** Back to Dashboard button.

**States:**
- Loaded
- Empty (no related documents)
- Error (404 - Document not found or doesn't belong to user)

---

## Analytics

The analytics section shares a secondary navigation menu (tabs or sidebar) to switch between the three views.

### 6. Analytics — Search History
Shows the user's most frequent queries.

**Elements:**
- **Data Table:** 
  - Query Text
  - Search Count (how many times searched)
  - Rank (#1, #2, etc.)
  - Last Searched Date
- **Empty State:** "You haven't searched for anything yet."

### 7. Analytics — Unsearched Documents
Highlights documents the user uploaded but have never surfaced in results.

**Elements:**
- **Nudge Message:** "These documents have never come up in a search — try searching for their topics."
- **List/Table:** Document Title, Upload Date.
- **Empty State:** "Great job! All your documents have appeared in searches."

### 8. Analytics — Top Documents
Shows the most useful/surfaced documents.

**Elements:**
- **List/Table:** 
  - Document Title
  - Appearance Count (how many times it showed up in search results)
  - Average Similarity Score
- **Empty State:** "Perform some searches to see your top documents."

---

## Design Constraints

| Constraint | Requirement |
|------------|-------------|
| **Responsive** | Must work on desktop and reasonable tablet widths (mobile is explicitly out of scope per PRD, but don't break entirely). |
| **Component Reuse** | Use consistent styling for Cards, Tables, Badges, and Empty States across Dashboard, Search, and Analytics. |
| **Feedback** | Destructive actions (Deletion) MUST have a confirmation step. Form submissions must show loading states. |
| **Navigation** | Once authenticated, the global nav should remain consistent across all views (Dashboard, Search, Analytics). |
