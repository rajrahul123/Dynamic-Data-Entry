# Documentation

Phase-by-phase working notes for the Dynamic Data Entry Platform.

## Phases

- [x] 0 — Project Foundation (full-stack skeleton, PostgreSQL + Alembic wiring)
- [x] 1 — Authentication & User Management (roles, JWT, admin CLI, user UI)
- [x] 2 — Form builder (generic forms/fields API + React builder UI)
- [x] 3 — Dynamic form renderer & submission foundation (generic Submission
  model, dynamic validation, `/forms/:id/submit`)
- [x] 4 — Submission & record management (record list/detail/edit/delete,
  role-based access, archived-record lifecycle)
- [x] 5 — Search, filtering & record querying (server-side dynamic filters for
  all 11 field types, case-insensitive free-text search, deterministic
  sorting, filtered pagination; tested on SQLite and real PostgreSQL)
- [ ] 6 — Exports (Excel, CSV, PDF, SQL)