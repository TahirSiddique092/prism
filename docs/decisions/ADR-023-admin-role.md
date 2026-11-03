# ADR-023 — Admin role

## Context

The project guide asked for role-based access: an admin who can see the users and more. Until now every account was the same, and the JWT carried only `user_id` and `email`.

## Decision

- **Two roles in one column.** `users.role` is `'user'` (the default) or `'admin'`, enforced by `CHECK (role IN ('user', 'admin'))`. There is no roles table or per-permission rules, because there are only two roles and one difference between them.
- **The role is read from MySQL on every admin request.** `require_admin` authenticates the JWT, then runs `SELECT role FROM users WHERE user_id = %s`, and returns 403 unless the role is `admin`. The role is not put in the JWT, so promoting or demoting someone takes effect on their next request, not after their 24-hour token expires. It costs one indexed lookup per admin request, and admin requests are rare.
- **Promotion is CLI-only.** Registration always creates a `user`, and nothing in the web app changes a role. `backend/db/set_role.py --email … --role admin|user` does it, with prepared statements. Anyone who can run that script already has the database credentials.
- **The admin view is read-only, and it shows counts.** `/api/admin/users` and `/api/admin/stats` run the stored procedures `sp_admin_user_overview` and `sp_admin_system_stats` (migration 010). `/api/admin/deletions` reads `deletion_audit`. No admin response has a password hash, search text or document text.
- **The deletion log records owner and title.** Migration 010 adds `deletion_audit.user_id` and `title` and recreates `before_document_delete` to fill them. Like `doc_id`, these aren't foreign keys, because the document is gone. Rows from before the migration keep NULL.
- **The frontend only hides the link.** The header shows Admin when `/api/auth/me` returns `role = admin`, and `/admin` shows "Admins only" on a 403. The backend check is what protects the data.

## Consequences

- An admin who is demoted loses access on their next request. Logging them out isn't needed.
- Adding a third role would mean changing the CHECK constraint and `require_admin`. A permissions table would be the next step if that ever happens.
