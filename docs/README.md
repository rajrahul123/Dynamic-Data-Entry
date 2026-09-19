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
- [x] 6 — Exports (Excel `.xlsx`, CSV, PDF, SQL)

## Phase 6 — Exports (Excel, CSV, PDF, SQL) — complete

Generic, data-driven record exports for **any** form, no form-specific code.

- **Endpoint:** `GET /api/forms/{form_id}/submissions/export?format=csv|xlsx|pdf|sql`
  plus the Phase 5 `search` / `filters` / `sort_by` / `sort_order` params.
  Open to any authenticated role; anonymous → 401; draft → 400; published /
  archived → 200. Unsupported `format` → 400. Invalid query params → 400.
- **Query reuse:** `export_service._fetch_records` calls the Phase 5
  `build_record_query` verbatim, so exports and the records list share one
  filtering/sorting implementation (`record_query.py`). `limit` / `offset`
  never apply.
- **Limit:** `MAX_EXPORT_RECORDS = 10000`; over-limit → 400 with guidance,
  never silent truncation. Read via the module attribute so tests can patch it.
- **Columns:** `ID`, `Submitted By`, `Submitted At`, then form fields by
  `sort_order` using `label` headers. Missing → blank. select/radio →
  option label (value *or* label). checkbox → `Yes`/`No`. Unknown stored keys
  never become columns; SQL is the only format emitting raw `data` JSON.
- **Formats:**
  - CSV — UTF-8 with BOM, `csv` module escaping, `\r\n` line terminators.
  - XLSX — openpyxl, single `Records` worksheet, frozen/styled header,
    native numbers and dates (checkbox/select as display text).
  - PDF — reportlab (landscape letter), XML-escaped `Paragraph` cells with CJK
    wrapping, `repeatRows=1`, zebra rows, title + export meta. Extremely long
    single cells are capped at 400 chars (`...`) so a pathological value can
    never produce a reportlab LayoutError; full values remain in CSV/XLSX/SQL.
  - SQL — `SET standard_conforming_strings = on; BEGIN; INSERT INTO
    submissions (...) VALUES (...), (...); COMMIT;` with `::jsonb` cast,
    single-quote-safe escaping, `ensure_ascii=False` JSON. Explicitly marked
    inspection/migration only; never exports credentials/secrets.
- **Filename:** slugified form name + `-records.<ext>` in a safe
  `Content-Disposition` attachment header.
- **Frontend:** `api.ts` gains `buildSubmissionQueryParams` (shared with
  `listSubmissions`), `ExportFormat`, `exportSubmissions` (blob download via
  Content-Disposition), and `ExportMenu.tsx` + `RecordsPage` wiring (applies
  the current query, notices/errors reuse the page slots).
- **Tests:** `backend/tests/test_export.py` — 37 tests covering authorization,
  format validation, query semantics (search/filter/sort), pagination
  isolation, dynamic columns, CSV escaping/Unicode, Excel validity/values, PDF
  validity + long-text safety, SQL structure/injection/auth hygiene, and the
  hard limit via monkeypatch. Full suite: **256 passing** (SQLite).
- **PostgreSQL verification:** 43 live checks against PostgreSQL 18 over the
  HTTP API (form build/publish/submit, all four formats, content types, BOM,
  label resolution, escaping, PDF stream dissection, SQL injection data,
  filter equals, sort asc, case-insensitive search, over-limit 400, draft 400,
  anonymous 401), with FK-ordered cleanup of only the temporary data.