# Neural Hub — AI Triage Nurse · Run Guide

This document explains how to set up, run, and verify the full Neural Hub AI Triage Nurse system locally.

---

## 1. Project Overview

**Neural Hub** is a production-grade AI Triage Nurse platform. A patient describes their
symptoms in a chat interface, an AI nurse ("Maya") asks adaptive follow-up questions,
detects emergency red flags in real time, assigns a 5-level triage urgency, and generates
a structured clinical report — then routes the patient to the right level of care.

**Tech stack**

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, Framer Motion |
| Backend | FastAPI (Python 3.12+), LangGraph + LangChain |
| AI | OpenAI `gpt-4o` (primary), Anthropic Claude (optional fallback) |
| Database | Supabase (PostgreSQL 17) |
| ORM / Migrations | SQLAlchemy 2.0 (async) + Alembic |
| Auth | JWT access + refresh tokens, role-based access control |

---

## 2. Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.12 or 3.13 |
| Node.js | 20+ (tested on 20.14) |
| npm | 10+ |
| Supabase | A project is **already configured** (connection string is in `.env`) |
| OpenAI API key | Required for the AI triage conversation |

> The Supabase database is already provisioned and migrated. You do **not** need to
> create a Supabase account or set up schema yourself for local runs.

---

## 3. Setup Instructions

All commands are run from the project root: `C:\Ai Agents\AI Triage Nurse Agent`

### Backend

```bash
cd backend

# (optional) create + activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate      # macOS / Linux

# install dependencies
pip install -r requirements.txt
# (lightweight local set without Docker/Celery/PDF deps:)
# pip install -r requirements-local.txt

# apply database migrations (safe to run — no-op if already at head)
alembic upgrade head

# start the API
uvicorn app.main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**

### Frontend

Open a **second terminal**:

```bash
cd frontend

# install dependencies (only the first time, or if node_modules is missing)
npm install

# start the dev server
npm run dev
```

Frontend runs at **http://localhost:3000**

---

## 4. Environment Variables

### Backend — root `.env` (already filled in)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Supabase async connection: `postgresql+asyncpg://postgres:***@db.yzmnumbtrxumnyptcoig.supabase.co:5432/postgres` |
| `DATABASE_URL_SYNC` | Supabase sync connection (used by Alembic): `postgresql://postgres:***@db.yzmnumbtrxumnyptcoig.supabase.co:5432/postgres` |
| `SECRET_KEY` | JWT signing secret (already generated) |
| `OPENAI_API_KEY` | **Required** — your OpenAI key for the AI triage conversation |
| `OPENAI_MODEL` | `gpt-4o` |
| `ANTHROPIC_API_KEY` | Optional fallback — leave blank to use OpenAI |
| `ALLOWED_ORIGINS` | CORS — already includes `http://localhost:3000` |

### Frontend — `frontend/.env.local`

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |
| `NEXT_PUBLIC_APP_NAME` | `Neural Hub` |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` |

> If `frontend/.env.local` is missing, the code defaults the API URL to
> `http://localhost:8000`, so local runs still work.

---

## 5. How to Run the Project

| Service | Command | URL |
|---------|---------|-----|
| Backend | `cd backend && uvicorn app.main:app --reload --port 8000` | http://localhost:8000 |
| Frontend | `cd frontend && npm run dev` | http://localhost:3000 |
| API docs | — | http://localhost:8000/docs |
| Health check | — | http://localhost:8000/health |

### End-to-end flow in the browser

1. Open **http://localhost:3000** → landing page
2. **/auth/signup** → create an organization account
3. **/auth/signin** → log in
4. **/triage/start** → start an AI triage session (or use it anonymously)
5. Chat with Maya — type symptoms, receive adaptive AI questions
6. When the assessment completes, the **triage report** page loads
7. Data (users, patients, assessments, reports, audit logs) is saved in Supabase

---

## 6. Troubleshooting

**Frontend won't start — Turbopack / `typedRoutes` error**
The dev script uses plain `next dev` (not `--turbo`) because `experimental.typedRoutes`
is incompatible with Turbopack. If you re-add `--turbo`, the dev server will exit.

**`pydantic ValidationError: secret_key / database_url field required`**
The backend reads `.env` from the project root. Run `uvicorn` from inside `backend/`
(the config looks for both `backend/.env` and `../.env`), or make sure the root `.env`
exists and is filled in.

**`InvalidTextRepresentationError: invalid input value for enum`**
The enums are configured to store their lowercase values. If you see this, ensure you are
on the current models and that migrations are at head (`alembic current` → `001 (head)`).

**AI message request times out**
The first OpenAI call can be slow (cold start). The chat UI handles this; if testing via
script, allow up to 60–90 seconds for the first message. Confirm `OPENAI_API_KEY` is set.

**CORS errors in the browser console**
Ensure `ALLOWED_ORIGINS` in `.env` includes `http://localhost:3000` and restart the backend.

**Port already in use (8000 or 3000)**
Stop the process holding the port:
```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

**Verify the database connection**
```bash
cd backend
alembic current     # should print: 001 (head)
```

---

## 7. Supabase Notes

- The Supabase PostgreSQL database is **already configured and migrated**.
- **Do NOT** re-create or manually run the schema — `alembic upgrade head` is idempotent
  and is the only thing that should touch the schema.
- All 11 application tables already exist: `organizations`, `users`, `providers`,
  `patients`, `assessments`, `conversations`, `symptoms`, `risk_factors`,
  `triage_reports`, `risk_scores`, `audit_logs`, `notifications`.
- Supabase requires SSL; the backend handles this automatically
  (`connect_args={"ssl": "require"}`) when the host is a `supabase.co` address.
- To inspect data, use the Supabase dashboard → Table Editor, or the SQL editor.

---

*Neural Hub AI Triage Nurse — this platform assists triage and does not replace a licensed
healthcare professional. In an emergency, call 911.*
