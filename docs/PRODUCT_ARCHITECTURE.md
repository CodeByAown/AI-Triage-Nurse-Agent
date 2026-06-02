# Neural Hub — AI Triage Nurse: Product & Technical Architecture

> Design document for review. **No database migrations or feature builds happen until this is approved.**
> Status legend: ✅ exists today · 🟡 partial today · 🔲 to be built

---

## 1. Personas & Product Overview

| Persona | Who | Primary goal |
|---|---|---|
| **Patient** | A person seeking guidance on symptoms | Get triaged, track health over time, have Maya "remember" them |
| **Provider / Nurse** | Clinical staff in an organization | Review patient triage, act on urgency |
| **Admin** | Clinic/org owner | Manage staff, patients, see analytics, audit |
| **Maya** | The AI triage nurse agent | Conduct context-aware assessments, escalate emergencies |

Neural Hub is **multi-tenant**: every clinical record belongs to an `organization`. Patients may also exist **self-served** (no org) — see §4.

---

## 2. Complete Product Flow

```
                         ┌─────────────────────────────┐
                         │        Landing (/)          │
                         └───────────────┬─────────────┘
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
   ┌──────────────────┐      ┌────────────────────┐     ┌────────────────────┐
   │ Patient sign-up  │      │  Clinic sign-up    │     │ Anonymous triage   │
   │  /auth/register  │      │   /auth/signup     │     │  /triage/start     │
   │  role=patient ✅ │      │   role=admin ✅    │     │  no account ✅     │
   └────────┬─────────┘      └─────────┬──────────┘     └─────────┬──────────┘
            ▼                          ▼                          ▼
   ┌──────────────────┐      ┌────────────────────┐     ┌────────────────────┐
   │ Patient Portal 🔲│      │  Admin Dashboard ✅│     │ One-off report ✅  │
   │ profile/history/ │      │  staff, patients,  │     │ (not retained to   │
   │ documents/Maya   │      │  analytics, audit  │     │  a patient login)  │
   └────────┬─────────┘      └─────────┬──────────┘     └────────────────────┘
            ▼                          ▼
   ┌──────────────────┐      ┌────────────────────┐
   │  Maya assessment │◄─────┤ Admin creates      │
   │  (context-aware) │      │ patients/providers │
   └──────────────────┘      └────────────────────┘
```

---

## 3. Patient Journey (target design)

```
Register (name,email,password)                          ✅ built
   └─► Patient User created (role=patient)              ✅
        └─► Patient clinical record auto-created        🔲 needs patients.user_id
             └─► Onboarding: complete profile           🔲 portal
                  • demographics (DOB, sex, pregnancy)
                  • contact (phone, address, emergency contact 🔲)
                  • chronic conditions, medications, allergies
                  • upload documents (labs, prescriptions, scans) 🔲
                   └─► Start assessment with Maya         ✅ engine; 🔲 portal entry
                        └─► Maya pre-loads patient context ✅ when patient_info set
                             (history-aware prompts already live)
                             └─► Assessment + report stored ✅
                                  └─► Future visits reuse history 🟡→🔲 (see §7)
```

**Data collected — required vs optional**

| Field | When | Required? |
|---|---|---|
| first/last name, email, password | registration | **Required** |
| DOB, biological sex | profile | Optional (improves triage) |
| pregnancy status | profile | Optional (gates pregnancy-risk logic) |
| chronic conditions, medications, allergies | profile | Optional but **strongly prompted** (drives safety) |
| emergency contact | profile | Optional 🔲 (new field) |
| documents (labs/scripts/scans) | anytime | Optional 🔲 |
| chief complaint + symptoms | per assessment | Captured in chat |

**Email/phone verification:** ❌ none today. **Recommendation:** add email verification (token link) before a patient can store PHI; phone optional.

---

## 4. Admin / Clinic Journey

```
Clinic sign-up (/auth/signup + org name) ─► Organization + Admin user ✅
   ├─► Admin Dashboard: analytics, recent activity ✅
   ├─► Create providers/nurses (POST /admin/users) ✅
   ├─► Create + manage patient records (patients API) ✅
   ├─► Review assessments & reports (org-scoped) ✅
   ├─► Manage roles / deactivate users ✅
   └─► Audit logs ✅
```

RBAC is enforced server-side via `require_role()` (super_admin > admin > provider > patient > viewer). Org isolation is enforced by `organization_id` filters on every query. **Gap:** patient self-records aren't org-linked yet (they have no org); the portal will scope by `user_id` instead.

---

## 5. Maya AI Flow

**Current (✅ built, verified earlier):** LangGraph state machine
`intake → symptom_collection → history_collection → adaptive_question (loop) → risk_assessment → report_generation`, with a deterministic regex **emergency pre-check** that can escalate at any turn. State persists in `assessments.graph_state` (JSONB) + `conversations`. History is injected into the system prompt **when `patient_info` is populated**.

**Gap today:** `patient_info` is only populated from the single Patient record passed in; it does **not** yet pull the patient's *previous assessments, prior conversations, or uploaded documents*. So Maya is context-aware **within** a session and from static profile fields, but not yet **longitudinally** across visits. §7 fixes this.

**Improved flow (target):**
```
session start
  └─► Build "Patient Clinical Context" pack:
        • profile (age/sex/pregnancy/conditions/meds/allergies)     ✅
        • last N assessment summaries + triage levels               🔲
        • relevant past conversation snippets (semantic recall)     🔲
        • extracted findings from uploaded documents               🔲
        • symptom timeline / progression deltas                    🔲
  └─► inject pack into system prompt (token-budgeted)
  └─► adaptive questioning, emergency + red-flag detection          ✅/🟡
  └─► structured report: summary, risk scores, next step, warnings  ✅
  └─► persist + update longitudinal memory index                    🔲
```

---

## 6. Database Design

**Existing tables (✅):** `organizations, users, patients, providers, assessments, conversations, symptoms, risk_factors, risk_scores, triage_reports, audit_logs, notifications`. Schema is well-normalized with FK cascades and JSONB clinical lists.

**Proposed additions (🔲 — for review, not yet migrated):**

```
patients
  + user_id        UUID NULL FK → users.id   (links a login to a clinical record)
  + emergency_contact_name   VARCHAR NULL
  + emergency_contact_phone  VARCHAR NULL
  (organization_id becomes NULLABLE to allow self-served patients)

documents                         (NEW)
  id, patient_id FK, uploaded_by_user_id FK
  kind ENUM(lab_report, prescription, imaging, referral, photo, other)
  file_url (S3/R2), file_name, mime_type, size_bytes
  ocr_text TEXT NULL               -- extracted text
  ai_summary TEXT NULL             -- Maya's structured findings
  extracted JSONB NULL             -- {labs:[{name,value,unit,flag}], meds:[…], findings:[…]}
  status ENUM(uploaded, processing, analyzed, failed)
  created_at, processed_at

patient_memory                    (NEW — longitudinal recall index)
  id, patient_id FK
  source_type ENUM(assessment, conversation, document, manual)
  source_id UUID
  content TEXT                     -- the recallable fact/summary
  embedding VECTOR(1536) NULL      -- pgvector for semantic retrieval (optional v2)
  importance SMALLINT              -- 1..5 ranking for context budgeting
  created_at
```

All additions are **additive & nullable** → zero risk to existing rows. `pgvector` is optional (v1 can use recency + importance ranking; v2 adds embeddings).

---

## 7. Patient Memory Architecture

**Goal:** when a patient returns after 1 day / week / month / 6 months, Maya already knows them.

```
WRITE PATH (after each assessment / upload)
  assessment completes ──► write patient_memory rows:
     • "Assessment 2026-05-12: L2 Urgent, chest tightness, ruled-in HTN risk"
     • key new symptoms, new meds, new diagnoses
  document analyzed  ──► write patient_memory rows from extracted findings
     • "Lab 2026-04-30: HbA1c 8.1% (high)"

READ PATH (on new session start)
  1. Load structured profile (conditions/meds/allergies)              [always]
  2. Load last N assessment summaries (recency-ranked)                [always]
  3. Retrieve top-K relevant memories:
        v1: filter by patient_id, rank by importance + recency
        v2: + semantic similarity (pgvector) to the chief complaint
  4. Token-budget the pack (e.g. ≤1,500 tokens) → newest/most-important win
  5. Inject as "PATIENT CLINICAL CONTEXT" block into Maya's system prompt
  6. Maya references it explicitly ("Given your HbA1c of 8.1% last month…")
```

**Symptom progression:** computed by diffing the new assessment's symptoms against the most recent prior assessment for the same complaint → Maya is told "worsening / improving / new."

---

## 8. Document & Medical Report Analysis Architecture

```
UPLOAD                STORE                 PROCESS (async worker)            USE
patient picks file ─► validate type/size ─► 1. virus/type check
  (PDF, JPG, PNG)      put to S3/R2          2. OCR (PDFs/images → text)
                       create documents row     • text PDFs: direct extract
                       status=uploaded          • scanned/img: OCR (Tesseract
                                                   or a vision model)
                                            3. AI analysis (vision/LLM):
                                                 • labs → structured values+flags
                                                 • prescriptions → meds+doses
                                                 • imaging reports → impressions
                                                 • photos → described findings
                                            4. write extracted JSONB + ai_summary
                                            5. write patient_memory rows
                                               status=analyzed
                                                        └─► available to Maya in
                                                            future sessions (§7)
```

**Security:** files in private bucket; signed time-limited URLs; PHI never in logs; `documents` rows org/patient-scoped with the same capability/role checks as triage. **Storage keys already exist** in `config.py` (S3/R2). **Processing** runs out-of-band (a background task / queue) so uploads return instantly.

**Model note:** image analysis (X-ray/skin photo) should carry an explicit "not a diagnosis — informational, provider must confirm" disclaimer and never produce definitive diagnoses.

---

## 9. Performance Audit (measured, this session)

Environment: backend on localhost talking to **remote Supabase**; frontend on the **dev** server (production is materially faster).

**API latency (warm), before fixes:**

| Endpoint | Time | Queries | Note |
|---|---|---|---|
| `/health` | 104 ms | 0 | network/app baseline |
| `/auth/me` | 1,242 ms | 1 | **~1.2s for ONE query** → remote DB RTT |
| `/patients` | 4,100 ms | 2 | count + select |
| `/triage/assessments` | 6,793 ms | 2+ | |
| `/analytics/dashboard` | **10,087 ms** | ~8 sequential | worst offender |
| `/auth/login` | 2,375 ms | 1 + bcrypt | cold pool + SSL |

**Root cause:** **each query is a ~1–1.25s round-trip to remote Supabase.** Endpoints that fire many sequential queries multiply that. Secondary: `pool_pre_ping=True` adds one extra round-trip (~1s) before every request.

**Fix applied (measured):** consolidated the 5 dashboard COUNT queries into **one** conditional-aggregation query → `/analytics/dashboard` **10,087 ms → ~3,180 ms (~3.2× faster)**.

**Recommended next (not yet done — some need your infra access):**
1. **Use the Supabase connection pooler** (port 6543, transaction mode) and/or move the DB to a region near the backend — the single biggest lever (~1s→~50ms per query).
2. Reconsider `pool_pre_ping` (drop it with a `pool_recycle`) — saves ~1 round-trip/request.
3. Further-collapse `/patients` & `/triage/assessments` (combine count+page, add indexes already present on FKs).
4. Frontend prod build + code-split heavy deps (recharts, framer-motion) — dev transfer was ~3 MB (unminified); prod will be a fraction.
5. Cache analytics (short TTL) since it's read-heavy.

---

## 10. UI/UX Audit

| Area | Finding | Recommendation |
|---|---|---|
| **Homepage** | Feature/workflow card sections animate via `whileInView` and render **empty** until scrolled — looks half-built | Make content visible by default (animate from visible) or trigger reliably |
| **Homepage** | Long empty vertical gaps between sections | Tighten spacing; add visual content (product screenshot, triage demo) |
| **Navbar** | Wide wordmark is fine on desktop; mobile uses the compact mark ✅ | Keep; consider an SVG wordmark (see §11) |
| **Auth pages** | Clean, on-brand, responsive ✅ | Minor: add email-verification step |
| **Admin dashboard** | Functional, on-brand ✅; no "create user" UI despite the API existing | Add a create-staff modal |
| **Patient portal** | **Does not exist** 🔲 | Build per §3 (gated on §6 schema) |
| **AI chat** | Solid; emergency banner good ✅ | Add streaming responses; render self-care/warning-signs as distinct cards |
| **Mobile** | Sidebar drawer + responsive logo verified ✅ | Continue testing each new page |

---

## 11. Logo Assessment (honest)

The asset is **`/public/neuralhub-logo.png`, 4500×273 (16.48:1), transparent, two-tone** (forest "NEURAL", **light-sage "HUB"**, terracotta dot). It now renders correctly, proportionally, responsively, and only on light surfaces. Genuine limitations of the **asset itself**:

1. **Color/contrast:** the light-sage "HUB" measures ~2.3:1 against the cream background — readable but **below WCAG AA** for small text. This is the most likely reason it can read as "not crisp."
2. **Format:** it's a **raster PNG**; at large sizes it can soften and it can't be recolored for a future dark mode.
3. **Aspect ratio:** 16.48:1 is very wide → it can never be tall/bold in a compact navbar.

**Proper solution (recommended):** supply an **SVG wordmark** (sharp at any size, recolorable, tiny file) and, ideally, a version where "HUB" is a darker sage for AA contrast on light UIs. I have **not** altered your brand colors unilaterally. If you'd like, I can (a) generate a contrast-boosted PNG variant from the existing file, or (b) wire in an SVG you provide. Tell me which and I'll implement it.

---

## 12. Implementation Roadmap (gated on your approval)

1. **Approve schema (§6)** → additive, nullable migration (`patients.user_id`, `documents`, `patient_memory`, emergency contacts). Reviewed before running on Supabase.
2. **Patient portal (§3, §5)** → profile, medical info, assessments, conversations.
3. **Longitudinal memory (§7)** → write/read paths, context pack injection.
4. **Document analysis (§8)** → upload, storage, OCR, AI extraction, memory write.
5. **Maya deepening** → progression deltas, richer red-flag rules, streaming.
6. **Performance** → pooler/region, prod build, caching.
7. **Hardening** → email verification, token revocation, password reset, full QA pass.

Nothing in steps 1–7 runs until you've reviewed this document.
```
