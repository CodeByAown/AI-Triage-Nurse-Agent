# Neural Hub AI Triage Nurse

AI-powered patient triage and clinical decision support platform.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Framer Motion |
| Backend | FastAPI (Python 3.12), LangGraph, LangChain |
| AI | Claude claude-sonnet-4-6 (Anthropic) |
| Database | PostgreSQL 16 + Redis 7 |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Auth | JWT (access + refresh tokens) |
| Queue | Celery + Redis |
| Deploy | Docker + Docker Compose → Railway |

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Anthropic API key

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — fill ANTHROPIC_API_KEY, SECRET_KEY, POSTGRES_PASSWORD at minimum
```

### 2. Start all services

```bash
docker-compose up --build
```

Services start at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### 3. Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Create first admin user

Register at http://localhost:3000/auth/signup with an organization name.

---

## Project Structure

```
neural-hub-triage/
├── frontend/                 # Next.js 15 app
│   └── src/
│       ├── app/             # Pages (App Router)
│       ├── components/      # Reusable components
│       ├── lib/             # API client, utilities
│       └── types/           # TypeScript types
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── agents/          # LangGraph triage engine
│   │   │   ├── graph.py     # State machine definition
│   │   │   ├── nodes.py     # Agent node implementations
│   │   │   ├── state.py     # TypedDict state schema
│   │   │   ├── prompts.py   # All system prompts
│   │   │   ├── risk_engine.py # Emergency pattern detection
│   │   │   └── session_manager.py # Session persistence
│   │   ├── api/v1/          # REST API routes
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── core/            # Config, security, logging
│   ├── alembic/             # DB migrations
│   └── tests/               # Unit + integration tests
├── .github/workflows/        # CI/CD
├── docker-compose.yml
└── .env.example
```

---

## Triage Levels

| Level | Name | Action | Examples |
|-------|------|--------|---------|
| L1 | Emergency | Call 911 / ED Now | Chest pain, stroke, severe bleeding |
| L2 | Urgent | Same-day visit | High fever, severe infection |
| L3 | Moderate | 24–72 hours | Moderate symptoms, UTI |
| L4 | Low Risk | Routine appointment | Minor illness |
| L5 | Self-Care | Home care | Cold, mild GI symptoms |

---

## AI Architecture

The triage engine uses **LangGraph** (MIT) to orchestrate a multi-node state machine:

```
intake → symptom_collection → adaptive_question (loop) → risk_assessment → report_generation
                                      ↓ (emergency detected at any node)
                               escalation → END
```

**Risk Detection** runs in two layers:
1. **Pattern matching** (instant) — regex against known emergency keywords
2. **LLM assessment** — Claude analyzes full conversation context

**Model:** Claude claude-sonnet-4-6
- Lowest hallucination rate in medical benchmarks
- HIPAA-eligible with Anthropic BAA
- Best safety profile for clinical applications

---

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` — Create account
- `POST /api/v1/auth/login` — Sign in
- `POST /api/v1/auth/refresh` — Refresh tokens
- `GET /api/v1/auth/me` — Current user

### Triage
- `POST /api/v1/triage/anonymous/start` — Start anonymous session
- `POST /api/v1/triage/anonymous/message` — Send message (no auth)
- `POST /api/v1/triage/sessions` — Start authenticated session
- `POST /api/v1/triage/message` — Send authenticated message
- `GET /api/v1/triage/reports/{assessment_id}` — Get triage report

### Analytics
- `GET /api/v1/analytics/dashboard` — Dashboard metrics
- `GET /api/v1/analytics/risk-breakdown` — Risk category analysis

### Admin
- `GET /api/v1/admin/users` — List users
- `PATCH /api/v1/admin/users/{id}/role` — Update role
- `GET /api/v1/admin/audit-logs` — Audit trail

---

## Production Deployment

### Railway (Recommended)

1. Create a Railway project
2. Add PostgreSQL and Redis plugins
3. Deploy backend and frontend services
4. Set environment variables from `.env.example`
5. Run `railway run alembic upgrade head`

### Docker Production

```bash
cp .env.example .env
# Fill all production values
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## Medical Disclaimer

> This platform is an AI-assisted triage tool and does **not** provide medical diagnoses. It is for informational and triage guidance purposes only. All clinical decisions must be made by licensed healthcare professionals. For emergencies, call 911 immediately.

---

## License

Proprietary — Neural Hub. All rights reserved.
