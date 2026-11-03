# Sprint-08-dbms-admin

> A sprint is a feature-level chunk of the Architecture — sized to however much you'll realistically tackle in one work block (a few hours, an all-nighter, a weekend). Not tied to a calendar week.

## Goal

Show PRISM's core DBMS features working inside the app, with a visible log line each time one runs: the existing trigger, new stored procedures and new stored functions. Add an admin role that can see every user and the system as a whole.

## Slices in this sprint

- [x]  `slice-32-db-activity-logging` — Database activity logs in the backend terminal (trigger, view, and later procedures and functions) — **Unassigned**
- [ ]  `slice-33-stored-procedures` — Stored procedures for the search-history and unsearched-documents queries — **Unassigned**
- [ ]  `slice-34-stored-functions` — Stored functions for chunk counts and similarity — **Unassigned**
- [ ]  `slice-35-admin-role` — Admin role, admin API and admin page — **Unassigned**

## Suggested order

1. **slice-32**: the logging helper the other three use.
2. **slice-33**: also teaches the migration runner to create several routines in one file.
3. **slice-34**: builds on that runner.
4. **slice-35**: uses procedures and functions from slices 33 and 34.

## Depends on

Sprint 7.

## Notes for next time

*(Leave blank unless something actually broke, a slice was mis-sized, or the agent went off-script.)*
