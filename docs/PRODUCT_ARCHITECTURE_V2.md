# Neural Hub — Maya-Centric Architecture (Version 2)

> **For approval before any migration or implementation.** Design only.
> Legend: ✅ exists · 🟡 partial · 🔲 to build

---

## 0. Core Principle — Maya Is the Product

We are **not** building `Patient → Dashboard → Chatbot`.
We are building `Patient → Maya`.

Every table, screen, upload, and metric exists for exactly one reason: **to make Maya know the patient better and assist them more intelligently over time.** Throughout this document each component is tagged with its Maya purpose: **[feeds Maya]** (a memory source) or **[surfaces Maya]** (an interaction surface).

```
                         ┌───────────────────────────────┐
                         │            MAYA                │
                         │   (longitudinal AI nurse)      │
                         │  • knows the patient           │
                         │  • remembers across time       │
                         │  • assesses, triages, advises  │
                         └───────────────┬───────────────┘
        ┌────────────── feeds Maya ──────┴──────── surfaces Maya ───────────┐
        ▼                ▼               ▼              ▼            ▼        ▼
 ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ ┌────────┐ ┌────────┐
 │  Medical   │  │Conversation│  │ Behavioral │  │ Clinical │ │ Voice  │ │ Text   │
 │  Memory    │  │  Memory    │  │  Memory    │  │ Timeline │ │  + STT │ │  chat  │
 └────────────┘  └────────────┘  └────────────┘  └──────────┘ └────────┘ └────────┘
        ▲                ▲               ▲              ▲
   profile/labs    past assessments  symptom patterns  events
   meds/allergies  recommendations   repeat complaints diagnoses
   documents       triage outcomes   compliance        labs/meds
```

The patient dashboard, admin tools, reports, and analytics are **supporting systems** — they read from and write to Maya's memory.

---

## 1. Maya Intelligence Architecture

Maya gains three new layers on top of today's LangGraph engine:

```
            ┌──────────────────────────────────────────────────────────┐
SESSION     │ 1. CONTEXT ASSEMBLY ENGINE  (runs before the first reply) │
START  ───► │    pulls every memory category → ranks → token-budgets →  │
            │    builds the "Patient Awareness Pack"                     │
            └───────────────────────┬──────────────────────────────────┘
                                    ▼
            ┌──────────────────────────────────────────────────────────┐
            │ 2. PERSONALIZED GREETING GENERATOR                        │
            │    turns the pack into a warm, specific opener            │
            │    ("Welcome back, John. Last month we looked at …")      │
            └───────────────────────┬──────────────────────────────────┘
                                    ▼
            ┌──────────────────────────────────────────────────────────┐
            │ 3. CONVERSATION ORCHESTRATOR  (today's LangGraph, evolved)│
            │    adaptive Q&A · emergency + red-flag detection ·        │
            │    references timeline naturally · new professional tone  │
            └───────────────────────┬──────────────────────────────────┘
                                    ▼
            ┌──────────────────────────────────────────────────────────┐
            │ 4. MEMORY WRITE-BACK  (after the assessment)              │
            │    new assessment summary · timeline event · updated      │
            │    clinical facts · recomputed behavioral insights        │
            └──────────────────────────────────────────────────────────┘
```

**Context Assembly Engine (the heart of "Maya knows you"):**
```
build_awareness_pack(patient_id, current_complaint) →
  1. Demographics              (name, age, sex, pregnancy)            [always]
  2. Active medical facts      (conditions, allergies, meds)          [always]
  3. Recent timeline events    (last ~10, weighted by recency+severity)
  4. Relevant past assessments (same/related complaint first)
  5. Behavioral insights       (repeat complaints, frequency, patterns)
  6. Salient document findings (abnormal labs, current scripts)
  7. (v2) semantic recall      (pgvector top-K vs. current_complaint)
  → rank by (importance × recency × relevance)
  → token-budget to ≤ ~1,800 tokens (newest/most-critical win)
  → emit { awareness_pack, greeting_seed }
```

This pack is injected once as a **"PATIENT CLINICAL CONTEXT"** system block and reused for the whole session, so Maya never cold-starts.

---

## 2. Memory Architecture (4 categories)

Today's single `patient_memory` idea is replaced by **four purpose-built stores** plus an optional semantic index.

### 2.1 Medical Memory — *what is clinically true about the patient* [feeds Maya]
```
clinical_facts
  id, patient_id
  category   ENUM(condition, allergy, medication, diagnosis,
                  family_history, surgical, pregnancy, immunization)
  label                      -- "Type 2 Diabetes", "Penicillin", "Lisinopril 10mg"
  detail JSONB               -- {dose, frequency, severity, reaction, …}
  status     ENUM(active, resolved, historical)
  onset_date, resolved_date
  source_type ENUM(self_report, document, assessment, clinician)
  source_id, confidence SMALLINT, created_at, updated_at
```
*Medication history* = `clinical_facts` rows of category=medication with status transitions (active → historical) — gives Maya the full med timeline, not just current meds.

### 2.2 Conversational Memory — *what we discussed before* [feeds Maya]
```
assessment_memory
  id, patient_id, assessment_id
  chief_complaint, triage_level
  key_symptoms JSONB, recommendations TEXT, outcome TEXT
  summary TEXT               -- 2–3 sentence recap Maya can quote
  embedding VECTOR(1536) NULL -- optional semantic recall
  created_at
```

### 2.3 Behavioral Memory — *patterns across visits* [feeds Maya]
```
patient_insights            -- recomputed after each assessment (cheap job)
  id, patient_id
  insight_type ENUM(frequent_symptoms, repeat_complaints,
                    assessment_frequency, followup_compliance,
                    symptom_pattern, risk_trend)
  value JSONB                -- e.g. {"chest_pain": 4, "window_days": 90}
  computed_at
```
Lets Maya say: *"This is the third time in two months you've reported chest tightness — let's look at this more carefully."*

### 2.4 Clinical Timeline — *the longitudinal story* [feeds Maya]
```
timeline_events
  id, patient_id, event_date
  event_type ENUM(diagnosis, assessment, medication_change, document,
                  lab_result, symptom, follow_up, escalation, vaccination)
  title, detail TEXT, severity SMALLINT
  source_type, source_id, created_at
```
Rendered to the patient as a visual timeline (§8) **and** summarized into Maya's context:
```
2026-01-01  Hypertension diagnosed
2026-02-15  Chest pain assessment → L2 Urgent
2026-03-02  Lisinopril 10mg started
2026-04-11  Lab: HbA1c 8.1% (high)
2026-05-20  Follow-up assessment → improving
```

### 2.5 Read & Write paths
```
WRITE (after each assessment / upload / profile edit):
  → upsert clinical_facts        (new conditions/meds/allergies)
  → insert assessment_memory     (summary of this visit)
  → insert timeline_events       (assessment, med change, lab, escalation)
  → recompute patient_insights   (patterns)
  → (v2) embed + index new memories

READ (session start, §1): Context Assembly Engine pulls from all four,
  ranks, token-budgets, injects.
```

---

## 3. Pre-Assessment Awareness (the "Welcome back, John" requirement)

```
patient opens Maya
   └─► Context Assembly Engine builds awareness pack (§1)
        └─► Greeting Generator produces a specific opener, e.g.:
            "Welcome back, John. Your last visit in April involved recurring
             chest discomfort and elevated blood pressure, and you started
             Lisinopril. Are today's symptoms related to that, or something new?"
        └─► patient answers → Maya continues with full context, never re-asking
            what it already knows (it confirms rather than re-collects)
```

**Key behavior change:** for returning patients, the `intake` and `history_collection` nodes **confirm** known facts ("I have you on Lisinopril and with a penicillin allergy — still accurate?") instead of collecting from scratch. New patients keep the full intake.

---

## 4. Maya's Personality & Conversation Style (redesign)

**Problem today:** Maya opens replies with "Thank you for sharing…", "Great, thanks…" — repetitive and chatbot-like.

**New voice:** a calm, competent triage nurse — professional, direct, empathetic, efficient. **No gratitude filler.**

| ❌ Avoid (filler) | ✅ Use (nurse-like) |
|---|---|
| "Thank you for sharing that." | "I understand." / "Got it." |
| "Great, thanks for the info." | "When did this begin?" |
| "Thanks for providing that." | "Let's talk more about that symptom." |
| "I appreciate you telling me." | "Can you describe the pain more specifically?" |

**Prompt-strategy changes (design — applied on approval):**
- A `CONVERSATION STYLE` block in the system prompt: *"You are a professional triage nurse. Do not thank the patient or use filler. Acknowledge briefly and only when natural, then move forward with the next clinically relevant question. Vary acknowledgments. Use the patient's name sparingly."*
- A short **banned-phrase list** ("thank you for", "thanks for", "I appreciate", "great,") the model is told to avoid.
- Empathy is reserved for moments that warrant it (pain, fear), not every turn.
- One question at a time; concrete, specific follow-ups.

> This single prompt change is **non-migration and low-risk** — say the word and I'll apply it immediately, separately from the schema work.

---

## 5. Voice-First Patient Experience

Voice is a **first-class input**, designed in two phases.

### 5.1 Voice-to-Text (v1 — ship first) [surfaces Maya]
```
patient taps 🎤 in Maya chat
  → browser Web Speech API (on-device STT, zero infra, instant)
  → live transcript appears in the input box
  → patient reviews/edits → sends to Maya as a normal message
  fallback: if unsupported (some browsers) → server STT (5.2)
```
Pros: free, ~instant, private. Cons: browser-dependent accuracy → we add server STT as fallback + upgrade.

### 5.2 Server STT + Voice Notes (v2) [feeds + surfaces Maya]
```
record / upload audio  →  store to private bucket (S3/R2)
   → transcribe (Whisper / OpenAI audio) 
   → voice_notes row { audio_url, transcript, duration, status }
   → optional symptom extraction → clinical_facts / timeline / memory
   → transcript flows into the assessment exactly like typed text
```
```
voice_notes
  id, patient_id, assessment_id NULL, audio_url, duration_sec,
  transcript TEXT, language, status ENUM(uploaded,transcribing,done,failed),
  created_at, processed_at
```
**AI integration:** transcripts are treated as first-class patient utterances — fed to the Conversation Orchestrator and (for standalone notes) summarized into memory. **Targets:** live STT partial < 300 ms; full note transcription < 3 s (§10).

---

## 6. Document Intelligence (detailed per type)

Pipeline: `upload → store → OCR/parse → type-specific extraction → structure → write to memory + timeline`.

```
documents                         document_extractions
  id, patient_id, uploaded_by       id, document_id, patient_id
  kind ENUM(lab,prescription,        extraction_type ENUM(lab_value, medication,
       imaging, clinical_note,            finding, impression, diagnosis,
       referral, photo, other)            recommendation, problem)
  file_url, mime, size, ocr_text     name, value, unit, reference_range,
  ai_summary, status                 flag ENUM(normal,high,low,critical),
  created_at, processed_at           observed_date, raw JSONB
```

### Lab reports
- **Extract** each analyte → name, value, unit, reference range.
- **Abnormal detection** → flag high/low/critical vs. range.
- **Trend comparison** → compare to prior `lab_value` extractions (e.g., HbA1c 7.4 → 8.1 → "worsening").
- **Timeline** → `timeline_events(lab_result)`; abnormal values → `clinical_facts` + Maya context.

### Prescriptions
- **Extract** medication, dose, frequency, prescriber, date.
- **Interaction checks** → cross-reference active meds (rules/drug DB) → flag interactions for Maya to raise.
- **Medication timeline** → upsert `clinical_facts(medication)`, transition superseded meds to historical.

### Imaging reports
- **Findings** + **Impression** extraction (the radiologist's conclusion).
- **Timeline** → `timeline_events(document)`; significant impressions → memory. (Image *pixels* are described with an explicit "informational, not a diagnosis" guardrail.)

### Clinical notes
- **Diagnoses**, **recommendations**, **problems** extraction → `clinical_facts(diagnosis)` + `timeline_events` + memory.

**Net effect:** every uploaded document becomes structured facts Maya can quote in the next conversation ("Your April labs showed HbA1c at 8.1%, up from 7.4% — has anything changed with your diet or medication?").

---

## 7. Patient Onboarding (redesigned)

```
Register (name,email,password)              [creates patient + user link]
  └─► Step 1  Profile        DOB, sex, pregnancy, contact, emergency contact
  └─► Step 2  Medical history chronic conditions  → clinical_facts
  └─► Step 3  Allergies                          → clinical_facts
  └─► Step 4  Medications     name/dose/frequency → clinical_facts (+timeline)
  └─► Step 5  Documents (optional) labs/scripts   → document pipeline (§6)
  └─► Step 6  Maya introduction  Maya greets using everything above
  └─► Step 7  First assessment   already context-rich (never a cold start)
```
Each step is skippable but **every field feeds Maya**. Progress is saved per step so patients can resume. The payoff: even the *first* assessment has meaningful context.

---

## 8. Patient Dashboard — the "Maya Center" (premium, wireframes)

Not a CRUD grid. The home screen **is** Maya; everything else is a glanceable health surface.

```
┌──────────────────────────────────────────────────────────────┐
│  Good morning, John            🔔 2 follow-ups   [profile ▾]  │
├──────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────┐  ┌────────────────────────┐ │
│  │            MAYA              │  │   HEALTH OVERVIEW       │ │
│  │  "Welcome back. How are you  │  │  Active conditions  2   │ │
│  │   feeling today?"            │  │  • Hypertension         │ │
│  │                              │  │  • Type 2 Diabetes      │ │
│  │  [ 🎤  Talk to Maya       ]  │  │  Medications        3   │ │
│  │  [ ⌨   Start assessment   ]  │  │  Last assessment 12 d   │ │
│  │                              │  │  Risk indicator  🟠 Mod │ │
│  │  Continue last conversation →│  └────────────────────────┘ │
│  └──────────────────────────────┘                            │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  HEALTH TIMELINE                                         ││
│  │  May 20  Follow-up assessment → improving                ││
│  │  Apr 11  Lab: HbA1c 8.1% (high)                          ││
│  │  Mar 02  Started Lisinopril 10mg                         ││
│  │  Feb 15  Chest pain assessment → L2 Urgent               ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │ RECOMMEND-   │ │ MEDICAL      │ │ FOLLOW-UP REMINDERS   │ │
│  │ ATIONS       │ │ RECORDS      │ │ • Recheck BP (Jun 5)  │ │
│  │ from Maya    │ │ reports/Rx   │ │ • Maya check-in (Jun) │ │
│  └──────────────┘ └──────────────┘ └───────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```
**Pages:** `Maya Center (home)` · `Health Overview` · `Medical Records` (reports/prescriptions/documents) · `Health Timeline` · `Assessments & Reports` · `Profile`. Every surface has a one-tap "Ask Maya about this."

---

## 9. Admin Dashboard (clinical)

```
┌──────────────────────────────────────────────────────────────┐
│ OPERATIONAL            CLINICAL              PATIENT MONITORING│
│ Assessments today 24   Top symptoms         🔴 High-risk (5)  │
│ Emergency flags    2   • chest pain  18%    • J. Doe  L1 2h ago│
│ Active patients  312   • headache    12%    • R. Lee  L2 today │
│ Risk distribution      Triage outcomes      Escalated cases 2 │
│  L1▕▏ L2▕▎ L3▕▍ L4▕▋   completion 86%       Frequent users    │
│  L5▕█                  follow-up rate 61%   • 3+ visits/30d (8)│
└──────────────────────────────────────────────────────────────┘
```
- **Operational:** assessments today, risk distribution, emergency flags, active patients.
- **Clinical:** common symptoms, triage-outcome mix, follow-up trends.
- **Patient monitoring:** high-risk list, escalated cases, frequent-assessment patients — all drillable to the patient's Maya timeline.

---

## 10. Performance Targets

| Workflow | Target | Today (measured) | Lever |
|---|---|---|---|
| Homepage load | **< 2.0 s** | ~3.4 s (dev) | prod build, code-split |
| Patient/admin dashboard | **< 1.0 s** | ~3.2 s (analytics) | pooler, caching, fewer queries |
| Maya response start | **< 2.0 s** | n/a | streaming, prompt caching |
| Maya context assembly | **< 800 ms** | n/a | indexed reads, budgeted pack |
| Voice transcription (note) | **< 3.0 s** | n/a | Whisper async |
| Live voice-to-text partial | **< 300 ms** | n/a | on-device STT |
| File upload feedback | **< 1.0 s** | n/a | optimistic UI, async processing |
| Document analysis (full) | **< 30 s async** | n/a | background worker |
| Assessment report generation | **< 5.0 s** | varies | streaming + caching |
| API query (single) | **< 150 ms** | ~1,000 ms | **Supabase pooler + region** |

The single highest-leverage fix remains the **Supabase connection pooler + closer region** (turns ~1 s/query into ~50 ms).

---

## 11. Database Schema (Version 2, full)

All additions are **additive & nullable** → zero risk to existing rows. `pgvector` is optional (v1 ranks by importance+recency; v2 adds embeddings).

```
EXISTING (✅)  organizations, users, patients, providers, assessments,
              conversations, symptoms, risk_factors, risk_scores,
              triage_reports, audit_logs, notifications

EXTEND patients
  + user_id FK→users (NULL), emergency_contact_name/phone (NULL)
  + organization_id made NULLABLE (self-served patients)

NEW (🔲, for approval)
  clinical_facts          §2.1  medical memory
  assessment_memory       §2.2  conversational memory
  patient_insights        §2.3  behavioral memory
  timeline_events         §2.4  clinical timeline
  documents               §6    uploaded files
  document_extractions    §6    structured findings per document
  voice_notes             §5.2  audio + transcripts
  memory_index (optional) §1    pgvector semantic recall
  onboarding_progress     §7    resumable onboarding state
  follow_up_reminders     §8    scheduled nudges
```

---

## 12. Roadmap (Maya-first sequencing)

| Phase | What | Unlocks |
|---|---|---|
| **0** (no migration) | Maya personality/prompt redesign (§4) + voice-to-text v1 (§5.1) | Immediate UX wins, zero schema |
| **1** | Approve schema (§11) → additive migration (reviewed first) | foundation |
| **2** | Patient↔user link + redesigned onboarding (§7) | context from day one |
| **3** | Memory write-back + Context Assembly Engine + greetings (§1–3) | "Maya knows you" |
| **4** | Document intelligence (§6) | docs → memory |
| **5** | Patient "Maya Center" dashboard (§8) | premium surface |
| **6** | Voice notes + server STT (§5.2); clinical admin dashboard (§9) | depth |
| **7** | Performance targets (§10) + hardening (verification, password reset) | production |

**Phase 0 is build-ready with no schema change** — I can apply Maya's new personality and add voice-to-text the moment you say go, while you review the schema for Phase 1+.

---

*Nothing in Phases 1–7 runs until you approve this document and the schema in §11.*
