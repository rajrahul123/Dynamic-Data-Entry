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
- [x] 7 — Public registration (self sign-up always creates Viewer-only accounts)
- [x] 8 — Form-style PDF exports (individual + bulk, one record per page)

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

## Phase 7 — Public registration — complete

`POST /api/auth/register` creates an account that is **always** assigned the
Viewer role. The `role` field (or any other privileged field) sent by the
request is ignored: only the admin-only `POST /api/users` endpoint can create
admin/operator accounts. Public users can therefore never self-promote, and
registration can never accidentally mint elevated accounts.

## Phase 8 — Form-style PDF exports (individual + bulk) — complete

Form-style PDFs print each record like a paper form: a portrait page with a
title (`Record #<id> — <form name>`), a meta line (form, submitter,
submitted-at), and a label/value table driven by the **live** form definition
(fields ordered by `sort_order`, a `Field`/`Value` header row, zebra rows).
Value formatting is the exact same `_display_value` used by every export
(select/radio → option label, checkbox → Yes/No, missing → blank); the
table-PDF long-value cap applies; all text is XML-escaped. There is **no
executable template system** — layout comes only from the form definition.

- **Individual:** `GET /api/forms/{form_id}/submissions/{submission_id}/export?format=pdf`
  — only `format=pdf` is accepted (anything else → 400). Access mirrors record
  detail: any authenticated role, anonymous → 401, draft form → 400,
  cross-form id → 404 (treated exactly like a missing id). Archived forms
  still export their historical records.
- **Bulk:** `GET /api/forms/{form_id}/submissions/export?format=pdf-form` —
  reuses the Phase 5 query engine verbatim (`search` / `filters` /
  `sort_by` / `sort_order`), `limit`/`offset` ignored, exactly one submission
  per page via an explicit `PageBreak` (empty result → one blank page), and
  `MAX_EXPORT_RECORDS` enforced (over-limit → 400, never truncation).
- **Shared layout:** one `_form_page_story(form, submission)` builds a page and
  both renderers call it, so the individual and bulk layouts cannot diverge.
- **Unicode fonts:** `export_service._unicode_font` searches
  `C:/Windows/Fonts` (and `/usr/share/fonts/...`) for Devanagari (`nirmala.ttc`,
  Noto, DejaVu) and CJK (`msyh.ttc`, Noto CJK, PingFang, DejaVu) fonts and
  registers the first hit as a reportlab `TTFont`. Non-Latin runs in any label
  or value are wrapped in the matching font inside the `Paragraph` while
  ASCII/Latin-1 stays in Helvetica (so it remains directly extractable). No
  matching font → safe fallback to the base font without crashing (documented
  support ceiling).
- **Filenames:** `<slug>-records-form.pdf` (bulk) and `<slug>-record-<id>.pdf`
  (individual) in safe `Content-Disposition` attachment headers — deliberately
  distinct from the table PDF's `<slug>-records.pdf`.
- **Frontend:** `api.ts` gains `readExportResponse` (401 → sign out,
  Content-Disposition filename parsing), `exportSingleRecordPdf`, and the
  extended `ExportFormat` (`'pdf-form'`); the record detail page adds a Form
  PDF button; `ExportMenu` adds a Form PDF item using the existing
  download/notice/error plumbing.
- **Tests:** `backend/tests/test_export_phase8.py` — 31 tests over the public
  HTTP endpoints: individual content (labels, option labels, Yes/No, temporals,
  blank-not-`None`, long-value cap, Latin-1 accents via WinAnsi octal decoding,
  Devanagari/CJK ToUnicode CMap hex tokens gated with `skipif` on registered
  host fonts), individual access (anonymous 401, all roles 200, draft 400,
  archived 200, nonexistent/cross-form 404, unsupported format 400), and bulk
  (one record per page, single/empty edge cases, search/filter/sort,
  ignored limit-offset, distinct filenames, archived, over-limit 400 for
  `pdf-form` and other formats). Full suite: **304 passing** (SQLite).
- **PostgreSQL verification:** 28 live checks against the real PostgreSQL
  database (per `backend/.env`), exercising the HTTP API with a throwaway
  admin + forms + submissions and FK-safe cleanup (submissions → forms →
  user): individual/bulk content and page counts, Hindi/CJK tokens, accents,
  search/filter/sort semantics, all Phase 6 formats, archive lifecycle,
  cross-form isolation, and the over-limit 400. QA rows verified removed.