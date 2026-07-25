# AGENTS.md

## Cursor Cloud specific instructions

This monorepo is a multi-tenant SaaS for vocational-school student lifecycle management. The core web product is the FastAPI **backend** plus the Vue3 PC admin **frontend**, backed by **MySQL**. Other apps (`student-portal`, `miniapp`) are optional; `mobile/` and `shared/` are libraries, not runnable apps.

The update script installs Python/Node deps only. Everything below (MySQL, DB schema/seed, running services) is not in the update script and must be started per session.

### Services

| Service | Dir | Dev command | Port |
|---|---|---|---|
| backend (FastAPI) | `backend/` | `.venv/bin/python -m uvicorn app.main:app --reload --port 8000` | 8000 |
| frontend (Vue3 PC admin) | `frontend/` | `npm run dev` (Vite; proxies `/api` → `127.0.0.1:8000`) | 5173 |
| MySQL 8 | — | `sudo service mysql start` | 3306 |

Standard lint/test/build commands live in `frontend/package.json` (`npm run lint` / `npm run build`) and `backend/README.md` / `.github/workflows/ci.yml`. Don't duplicate them here.

### MySQL is required (non-obvious setup)

- The backend is **MySQL-only**; the pytest harness (`backend/tests/conftest.py`) refuses to fall back to SQLite and `raise`s if `TEST_DATABASE_URL` is unset.
- MySQL is installed as a system package but is **not auto-started** on VM boot. Run `sudo service mysql start` at the start of each session.
- Local dev config lives in `backend/.env` (gitignored, not in the repo). It must define `DB_ENABLED=true`, `DATABASE_URL` (dev DB) and `TEST_DATABASE_URL` (test DB). Expected local setup: user `saas_user` / password `saas_pass`, databases `student_lifecycle_dev` and `student_lifecycle_test`. If `backend/.env` is missing, recreate it and the DBs before running the backend or tests.

### Build the dev schema with the init script, NOT alembic

- Create the dev schema + demo data with:
  `cd backend && .venv/bin/python scripts/init_mysql_db.py && .venv/bin/python scripts/seed_mysql_demo_data.py`
  (`init_mysql_db.py` runs `metadata.create_all()` — the full current schema in one shot; both scripts read `backend/.env`.)
- Do **not** run `alembic upgrade head` against an empty local DB: migration `0001_init_core_tables` already does `metadata.create_all()` (full model metadata), so a later explicit `create_table` migration (`0103_system_implementation`) fails with `1050 Table ... already exists`. Alembic is used for production deploys, not for fresh local bootstrap. Tests build their schema via `create_all` too, not alembic.

### Login / demo accounts

- The PC login page (`/`) posts to the real `POST /api/v1/auth/login`.
- After seeding, tenant `demo-school` (read-only) has `admin` / `teacher` / `student`, and sandbox tenant has `admin2` / `teacher2` / `student2`; password for all is `123456`. `demo-school` blocks write operations (403) by design — use the sandbox accounts to exercise writes.
