# Dynamic Data Entry Platform

A generic dynamic data-entry platform where administrators create and publish
custom forms, data-entry operators fill them in, and submitted records can be
managed, searched, filtered, and exported (Excel, CSV, PDF, SQL).

> **Status: Phase 1 — Authentication & User Management.** The repository
> contains a full-stack foundation with JWT authentication, role-based access
> control (`admin` / `operator` / `viewer`), an initial-admin CLI, and an
> admin-only user management UI. No forms, data entry, records, or export
> features exist yet.

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
│   │   ├── api/         Routers: auth, users, health
│   │   │   └── deps.py  Auth/role dependencies (the real security boundary)
│   │   ├── core/        Settings, database, security (hashing + JWT)
│   │   ├── models/      Declarative base and User ORM model
│   │   └── schemas/     Pydantic request/response models
│   ├── scripts/         create_admin.py (initial administrator CLI)
│   ├── tests/           pytest suite for auth, authorization, user mgmt
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
| `admin` | Everything: dashboard, user management (create/update roles/status) |
| `operator` | Authenticated access to the dashboard |
| `viewer` | Authenticated, read-only access to the dashboard |

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

## API surface (Phase 1)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/login` | Public | Return a JWT access token for username/email + password |
| `GET` | `/api/auth/me` | Any authenticated user | Return the current user |
| `GET` | `/api/health` | Public | Health check (also reports DB status) |
| `GET` | `/api/users` | Admin | List users |
| `POST` | `/api/users` | Admin | Create a user |
| `GET` | `/api/users/{id}` | Admin | Get one user |
| `PATCH` | `/api/users/{id}` | Admin | Update role / status / profile / password |

## Run the tests

```bash
cd backend
.venv\Scripts\activate
python -m pytest                # auth, authorization, and user-management tests
```

## Current project status

- Phase 0 complete: full-stack foundation, PostgreSQL + Alembic wiring, CORS,
  health endpoint, frontend/backend connectivity check.
- Phase 1 complete: `User` model + migration, Argon2 password hashing, JWT
  login, `/api/auth/me`, role-based authorization, admin user management,
  initial-admin CLI, frontend login/protected routes/dashboard, and admin user
  management UI.
- Pending phases: form builder, dynamic forms, data entry, record
  management/search/filter, exports.