# slice-35 — Admin role and admin page

**Sprint:** 8 — DBMS features and admin
**Module:** auth, admin (new), frontend, infra (migrations)
**Depends on:** slice-32 (logging), slice-33 (procedures), slice-34 (functions)

## What to build

Add role-based access control. Every account has a role, either `user` or `admin`. Admins get an Admin page with three parts:
- every user, with their activity counts;
- system-wide totals;
- the deletion log written by the `before_document_delete` trigger.

The admin view is read-only. Admins see account details and counts, never anyone's documents, search text or password hash.

## Changes

### 1. Roles in the schema (migration `010_user_roles.sql`)
- Add `users.role VARCHAR(20) NOT NULL DEFAULT 'user'` with `CHECK (role IN ('user', 'admin'))`. Existing accounts become `user`.
- Add `deletion_audit.user_id INT NULL` and `deletion_audit.title VARCHAR(255) NULL`. Recreate `before_document_delete` so it also records `OLD.user_id` and `OLD.title`. Rows written before this migration keep NULL in both.

### 2. Making someone an admin
- Registration always creates a `user`. There is no way to become an admin from the app.
- New CLI script `backend/db/set_role.py --email … --role admin|user` sets a role. It uses a prepared statement and exits with 1 for an unknown email. Run it with `docker compose exec backend python backend/db/set_role.py …`, and document this in the README.

### 3. Checking the role (backend)
- Add a `require_admin` decorator to the auth module. On every admin request it reads the role from MySQL for `g.user_id`, so promoting or demoting someone takes effect on their next request without a new login. It returns 403 for non-admins (401 without a session, as today).
- Add `GET /api/auth/me`, returning `{ user_id, name, email, role }`, so the frontend knows whether to show the Admin link.

### 4. Admin API (new `backend/modules/admin/`, blueprint `/api/admin`)
| Route | Returns | Built with |
|---|---|---|
| `GET /api/admin/users` | Per user: `user_id, name, email, role, created_at, documents, chunks, searches, last_search_at` | Stored procedure `sp_admin_user_overview()`, using the functions `fn_user_document_count(user_id)`, `fn_user_search_count(user_id)` and `fn_chunk_count` (slice-34) |
| `GET /api/admin/stats` | Totals: users, admins, documents by status (processing / ready / error), chunks, searches (all time and today), deletions logged | Stored procedure `sp_admin_system_stats()` |
| `GET /api/admin/deletions` | The latest 50 `deletion_audit` rows: `audit_id, doc_id, title, user_id, deleted_at` | Plain query on the trigger's table |

- Each route logs its `[DB] PROCEDURE` / `FUNCTION` lines (slice-32), and timestamps go out in UTC with a `Z` (ADR from slice-25).
- Create the new routines in the same migration as the roles, or in their own, using the runner from slice-33.

### 5. Admin page (frontend)
- A new `/admin` page with three sections: **Users**, **System stats** and **Deletion log**. Dates are shown in the viewer's time zone.
- The header shows an **Admin** link only when `/api/auth/me` says `role = admin`.
- A non-admin who opens `/admin` sees an "Admins only" message, not the data.
- Add Next.js proxy routes for `/api/auth/me` and `/api/admin/*`.

### 6. Docs
- Update `relational-schema.md`: the `users.role` column and its CHECK constraint, the new `deletion_audit` columns and trigger body, the new procedures and functions, and the diagrams (ER and relational schema).
- Add the new routes to the ADD API table.
- Add an ADR for the role model: two roles, the role read from the database on each request, and a CLI-only way to promote.

## Acceptance criteria

- Existing and newly registered users have role `user`; inserting any role other than `user` or `admin` fails because of the CHECK constraint
- `set_role.py` promotes and demotes by email; an unknown email prints an error and exits with 1
- Every `/api/admin/*` route returns 401 without a session and 403 for a `user`
- Demoting an admin takes effect on their next request, without logging out
- `/api/admin/users` lists every user with correct document, chunk and search counts (checked against fixture data)
- `/api/admin/stats` totals equal direct `COUNT` queries on the same data
- Deleting a document adds a `deletion_audit` row with its `user_id` and `title`, which appears in `/api/admin/deletions`
- No admin response contains a password hash, search text or document text
- The Admin link appears only for admins, and `/admin` shows the three sections to an admin and "Admins only" to anyone else
- Each admin route prints its `[DB]` log lines
- All existing tests still pass

## Out of scope

- Changing roles from the web page (CLI only)
- Deleting, suspending or impersonating users
- Admins viewing other users' documents, chunks or search history
- Roles other than `user` and `admin`, or per-permission rules

## Assigned To

Unassigned

## Human review required?

Yes. It changes the auth module (role check, `/api/auth/me`), adds a schema migration on `users` and `deletion_audit`, and changes the trigger.
