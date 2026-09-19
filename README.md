# Dynamic Data Entry Platform

A generic dynamic data-entry platform where administrators create and publish
custom forms, data-entry operators fill them in, and submitted records can be
managed, searched, filtered, and exported (Excel, CSV, PDF, SQL).

> **Status: Phase 4 — Submission & Record Management.** The
> repository contains a full-stack foundation with JWT authentication,
> role-based access control (`admin` / `operator` / `viewer`), an initial-admin
> CLI, an admin-only user management UI, an admin-only **dynamic form
> builder** (name, description, ordered fields, draft → published → archived
> lifecycle, per-type settings validation, drag-and-drop ordering, live
> preview), **data capture** (any authenticated user can open a published form
> and submit data, validated dynamically server-side against the field
> definitions), and now **record management**: paginated record listing,
> record details, record editing, and record deletion for **any** form, driven
> entirely by the dynamic form definition. Admin and operator can view, edit,
> and delete records; viewer is read-only; anonymous users have no record
> access. Archived forms keep their historical records viewable/editable/
> deletable while new submissions remain blocked. Submissions are stored in a
> generic `submissions` table as JSONB; a RESTRICT foreign key prevents
> deleting a form that has submissions. Search / filtering / exports are not
> implemented yet.

## Architecture

```
dynamic-data-entry-platform/
├── frontend/            React + TypeScript + Vite + Tailwind CSS SPA
│   └── src/
│       ├── lib/         API client and auth state (JWT token, current user)
│       ├── components/  Route guards and app shell
│       └── pages/       Login, Dashboard, and admin User Management
├── backend/             FastAPI + SQLAlchemy + Alembic + Pydantic API
│   ├── app/
│   │   ├── api/         Routers: auth, users, forms, submissions
│   │   │   └── deps.py  Auth/role dependencies (the real security boundary)
│   │   ├── core/        Settings, database, security, submission_validation
│   │   ├── models/      Declarative base, User, Form, FormField, Submission
│   │   └── schemas/     Pydantic request/response models
│   ├── scripts/         create_admin.py (initial administrator CLI)
│   ├── tests/           pytest suite for auth, authorization, user & form mgmt
│   └── alembic.ini      Alembic configuration
├── docs/                Project documentation
└── .env.example         Documentation of all required environment variables
```

The frontend development server proxies `/api/*` requests to the FastAPI
backend, so all API calls are relative and CORS-safe during local development.

## Prerequisites

- **Node.js** 20+ and **npm**
- **Python** 3.11+
- **PostgreSQL** 14+ running locally
- **Git**

## Configure PostgreSQL

1. Start the PostgreSQL service (`postgresql-x64-*`).
2. Create a dedicated database and user (adjust ownership/password to taste):

   ```sql
   CREATE ROLE ddep_user WITH LOGIN PASSWORD 'a_strong_password';
   CREATE DATABASE dynamic_data_entry OWNER ddep_user;
   ```

3. The backend expects the connection string
   `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`.

## Configure environment variables

| File | Purpose |
| --- | --- |
| `backend/.env` | Backend configuration (copy from `backend/.env.example`) |
| `frontend/.env.development` | Optional Vite proxy target (copy from `frontend/.env.example`) |

Required backend variables:

- `DATABASE_URL` — `postgresql+psycopg://...`
- `JWT_SECRET_KEY` — random secret for signing access tokens; generate with
  `python -c "import secrets; print(secrets.token_urlsafe(64))"`

Optional: `ENVIRONMENT`, `DEBUG`, `CORS_ORIGINS`, `JWT_ALGORITHM`
(default `HS256`), `ACCESS_TOKEN_EXPIRE_MINUTES` (default `30`).

Real secrets are never committed; `.env*` files are git-ignored.

## Roles

| Role | Can do |
| --- | --- |
| `admin` | Everything: dashboard, user management (create/update roles/status), form builder, submissions, record management (view / edit / delete) |
| `operator` | Authenticated access to the dashboard and submissions plus record management (view / edit / delete) |
| `viewer` | Authenticated, read-only access: dashboard, submissions, and record viewing (no edit / delete) |

## Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
# create backend/.env from backend/.env.example with a real DATABASE_URL and JWT_SECRET_KEY
uvicorn app.main:app --reload   # http://localhost:8000
```

Interactive API docs: http://localhost:8000/docs

## Run Alembic migrations

```bash
cd backend
.venv\Scripts\activate
alembic revision --autogenerate -m "create users table"   # when changing models
alembic upgrade head                                        # apply migrations
```

## Create the first administrator

```bash
cd backend
.venv\Scripts\activate
python scripts/create_admin.py                              # interactive prompts
python scripts/create_admin.py --username admin --email admin@example.com --full-name "Platform Administrator"
```

The script prompts for a password (masked) unless `--password` is passed, and
it refuses to run twice for the same username/email, so it never creates
duplicate administrators. Credentials are never hard-coded.

## Run the frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

## API surface

### Phase 1 — Auth & user management

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/login` | Public | Return a JWT access token for username/email + password |
| `GET` | `/api/auth/me` | Any authenticated user | Return the current user |
| `GET` | `/api/health` | Public | Health check (also reports DB status) |
| `GET` | `/api/users` | Admin | List users |
| `POST` | `/api/users` | Admin | Create a user |
| `GET` | `/api/users/{id}` | Admin | Get one user |
| `PATCH` | `/api/users/{id}` | Admin | Update role / status / profile / password |

### Phase 2 — Form builder (all admin-only)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/forms` | Create a draft form |
| `GET` | `/api/forms` | List forms (filter by `status` / `created_by`) |
| `GET` | `/api/forms/{form_id}` | Get a form with its fields |
| `PATCH` | `/api/forms/{form_id}` | Rename / change description (draft only) |
| `DELETE` | `/api/forms/{form_id}` | Delete a draft form |
| `POST` | `/api/forms/{form_id}/publish` | Publish (requires ≥ 1 field, draft only) |
| `POST` | `/api/forms/{form_id}/archive` | Archive (draft or published) |
| `POST` | `/api/forms/{form_id}/fields` | Add a field (draft only) |
| `PATCH` | `/api/forms/{form_id}/fields/{field_id}` | Update a field (draft only) |
| `DELETE` | `/api/forms/{form_id}/fields/{field_id}` | Delete a field (draft only) |
| `POST` | `/api/forms/{form_id}/fields/reorder` | Reorder fields (draft only) |

### Phase 3 — Submissions (any authenticated role)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/forms/{form_id}/definition` | Any authenticated user | Published/archived form definition for building the entry form or record views |
| `POST` | `/api/forms/{form_id}/submissions` | Any authenticated user | Submit data for a published form; validates dynamically against field definitions (401 anonymous, 404 unknown form, 400 draft/archived, 422 invalid data) |

### Phase 4 — Record management

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/forms/{form_id}/submissions` | Any authenticated role | Paginated record list (`limit` 1-100, default 20, `offset`) with `items` / `total` / `limit` / `offset` |
| `GET` | `/api/forms/{form_id}/submissions/{submission_id}` | Any authenticated role | Record detail (404 for unknown form, unknown submission, or cross-form access) |
| `PATCH` | `/api/forms/{form_id}/submissions/{submission_id}` | Admin / operator (viewer 403) | Edit a record; reuses the dynamic server-side validation engine (422 invalid) |
| `DELETE` | `/api/forms/{form_id}/submissions/{submission_id}` | Admin / operator (viewer 403) | Delete a single record; 204 on success |
| `GET` | `/api/records/forms` | Any authenticated role | Read-only list of published/archived forms for record browsing (no builder access) |

## Run the tests

```bash
cd backend
.venv\Scripts\activate
python -m pytest                # auth, authorization, user, form-builder, and submission tests
```

## Current project status

- Phase 0 complete: full-stack foundation, PostgreSQL + Alembic wiring, CORS,
  health endpoint, frontend/backend connectivity check.
- Phase 1 complete: `User` model + migration, Argon2 password hashing, JWT
  login, `/api/auth/me`, role-based authorization, admin user management,
  initial-admin CLI, frontend login/protected routes/dashboard, and admin user
  management UI.
- Phase 2 complete: generic `Form` / `FormField` models + migration, forms &
  fields API with draft → published → archived lifecycle, per-type settings
  validation, and a React builder UI (`/forms`, `/forms/new`,
  `/forms/:id/edit`) with a field palette, drag-and-drop ordering, field
  editor (auto-suggested keys), and a live preview.
- Phase 3 complete: generic `Submission` model + migration (JSONB `data`,
  RESTRICT form/user foreign keys), a dynamic server-side validation engine
  covering all 11 field types, `POST /api/forms/{form_id}/submissions` (any
  authenticated role; published forms only), `GET
  /api/forms/{form_id}/definition`, and a React submission page
  (`/forms/:id/submit`) that reuses the field renderer in controlled mode,
  performs client-side validation, and maps server validation errors onto
  individual fields.
- Phase 4 complete: generic record management over the existing
  `submissions` table — paginated `GET /api/forms/{id}/submissions`, record
  detail, `PATCH` (full `data` replacement reusing the Phase 3 validation
  engine) and `DELETE`; admin/operator may mutate, viewer is read-only,
  anonymous gets 401, cross-form access returns 404. Archived forms retain
  their records (view/edit/delete) while still rejecting new submissions;
  `GET /api/forms/{id}/definition` now also serves archived forms for record
  views. React UI: `/records` (available forms), `/forms/:id/records`
  (dynamic columns from the form definition, server-side pagination, delete
  confirmation), `/forms/:id/records/:id` (detail), and
  `/forms/:id/records/:id/edit` (reuses the field renderer). No search or
  filtering yet.
- Pending phases: record search / filter, exports.