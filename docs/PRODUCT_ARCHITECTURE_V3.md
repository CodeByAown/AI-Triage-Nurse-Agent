# Neural Hub — Maya as a Digital Nurse (Version 3)

> **Final design for approval before any migration or implementation.** Design only.
> Builds on V2. Legend: ✅ exists · 🟡 partial · 🔲 to build

**Thesis:** we are not building an AI chatbot with memory. We are building a **digital nurse who develops an ongoing healthcare relationship with every patient** — who remembers, reasons about, proactively follows up on, and cares for each person across months and years.

The leap from V2 → V3 is four new intelligence layers:

```
        TEXT · VOICE · IMAGES · PDFs · LABS · PRESCRIPTIONS
                              │
                 ┌────────────▼─────────────┐
                 │  UNIFIED PATIENT CONTEXT  │  (§4) every modality → one understanding
                 └────────────┬─────────────┘
                 ┌────────────▼─────────────┐
                 │  CLINICAL REASONING LAYER │  (§5) relationships between events
                 └────────────┬─────────────┘
                 ┌────────────▼─────────────┐
                 │  CONTINUITY OF CARE       │  (§2) open threads, open loops, recall
                 └────────────┬─────────────┘
   ┌──────────────┐ ┌─────────▼──────────┐ ┌──────────────────┐
   │ FOLLOW-UP    │ │       MAYA         │ │ CONVERSATION     │
   │ ENGINE (§3)  │►│  (assess · advise · │◄│ QUALITY SPEC (§6)│
   │ proactive    │ │  escalate · recall) │ │ nurse, not bot   │
   └──────────────┘ └────────────────────┘ └──────────────────┘
```

---

## 1. Maya Intelligence Architecture (recap + what's new)

V2 established the **Context Assembly Engine → Greeting → Orchestrator → Memory write-back** loop. V3 inserts three layers *between* memory and Maya so she doesn't just *recall* — she *understands* and *acts*:

```
memory stores (V2: medical, conversational, behavioral, timeline)
   ▼
UNIFIED PATIENT CONTEXT LAYER  — fuse all modalities into one object   (§4)
   ▼
CLINICAL REASONING LAYER       — connect events into causal chains     (§5)
   ▼
CONTINUITY OF CARE LAYER       — surface open threads & open loops      (§2)
   ▼
MAYA  — greets with continuity, reasons with chains, follows up         (§6 tone)
```

Maya now operates in **two modes**:
- **Reactive** — patient starts a conversation (today's flow, now context-rich).
- **Proactive** — the Follow-Up Engine starts the conversation (§3).

---

## 2. Continuity of Care Architecture

Continuity = Maya treats every visit as part of an **ongoing relationship**, not an isolated transaction. Two concepts make this concrete:

### 2.1 Care Threads — *persistent concerns that span visits*
```
care_threads
  id, patient_id
  title                  -- "Hypertension management", "Recurring chest pain"
  status ENUM(open, monitoring, resolved)
  severity, opened_at, last_touched_at, resolved_at
  summary TEXT           -- Maya's evolving narrative of this thread
```
Every assessment links to one or more threads (`assessment.thread_id`). When John returns, Maya finds his **open threads**, picks the most relevant to today's complaint, and opens with it.

### 2.2 Open Loops — *unfinished care actions Maya tracks*
```
care_actions
  id, patient_id, thread_id, assessment_id
  type ENUM(recommendation, referral, self_monitoring, medication, lab_order, follow_up)
  description            -- "Monitor glucose daily", "See PCP within 1 week"
  status ENUM(open, in_progress, completed, declined, expired)
  due_at, closed_at, closed_via ENUM(patient_report, document, assessment, timeout)
```
This is what powers *"Have you been able to monitor your glucose since then?"* — Maya checks **open loops** and asks about them.

### 2.3 Continuity generation (exactly how the greeting is produced)
```
on session start:
  1. UPCL assembles the patient (§4)
  2. select continuity hook:
        a. open care_actions due/overdue   → "Were you able to … ?"
        b. most-relevant open care_thread   → "Last time we discussed …"
        c. recent significant timeline event→ "Since your April labs …"
        d. else (new patient)               → standard warm intake
  3. Greeting Generator (LLM) renders one natural, specific opener that:
        • names the patient sparingly
        • references ONE concrete prior fact (not a data dump)
        • bridges to today ("…is today related to that, or something new?")
```
Example produced: *"Welcome back, John. Last time we discussed your elevated HbA1c and blood pressure. Have you been able to monitor your glucose since then?"*

**Closing loops:** when the patient answers ("yes, it's been around 130"), Maya updates the `care_action` (closed_via=patient_report) and writes a new `timeline_event` + memory — so the relationship visibly progresses.

---

## 3. Maya Follow-Up Engine (proactive monitoring)

Maya initiates contact. The engine is **event-driven + rule-configurable**.

```
                 ┌──────────────── TRIGGERS ─────────────────┐
   assessment completes ─┐                                    │
   recommendation issued ─┤                                   │
   high-risk (L1/L2) flag ─┤   ┌─────────────────────────┐    │
   medication started ─────┼──►│  FOLLOW-UP RULES (org-    │    │
   abnormal lab extracted ─┤   │  configurable)           │    │
   N days of inactivity ───┤   └───────────┬─────────────┘    │
   care_action due ────────┘               ▼                  │
                              creates follow_ups (scheduled)   │
                                            ▼                  │
                    SCHEDULER (background job, runs hourly)    │
                       evaluates due follow_ups →              │
                       generates Maya-initiated message →      │
                       delivers via notification/email/SMS →   │
                       patient taps in → context-rich session  │
                 └────────────────────────────────────────────┘
```

### 3.1 What triggers a follow-up
| Trigger | Default rule | Maya opener |
|---|---|---|
| L2 Urgent outcome | check-in in 3 days | "How are you feeling since our last assessment?" |
| Recommendation "see provider" | confirm in 7 days | "Were you able to see a healthcare provider?" |
| Medication started | tolerance check in 14 days | "How are you tolerating the new medication?" |
| BP/glucose self-monitoring | check-in in 30 days | "It's been 30 days — want a quick BP check-in?" |
| High-risk patient | weekly monitoring | "Just checking in on your symptoms this week." |
| Inactivity ≥ 60 days | re-engagement | "It's been a while — how have you been feeling?" |
| Abnormal lab uploaded | review in 3 days | "I noticed your recent labs — let's review together." |

### 3.2 Data stored
```
follow_up_rules                    follow_ups
  id, organization_id                id, patient_id, rule_id, thread_id, care_action_id
  trigger_type                       status ENUM(scheduled, sent, engaged, completed,
  condition JSONB                              dismissed, expired)
  delay_days, channel                scheduled_for, sent_at, engaged_at, completed_at
  message_template                   generated_message TEXT
  is_active, priority                channel ENUM(in_app, email, sms)
```

### 3.3 How reminders work
- Scheduler picks due `follow_ups` → Greeting Generator personalizes the message from the patient's current context → delivered to the **patient dashboard "From Maya" inbox** + optional email/SMS.
- Engagement is tracked end-to-end (`scheduled → sent → engaged → completed`) → feeds the admin **follow-up completion rate** (§8).

### 3.4 Admin configuration
Admins manage `follow_up_rules` per org: enable/disable triggers, tune delays, edit message templates, set channels and quiet hours, and define high-risk monitoring cadence. Safe defaults ship out of the box.

---

## 4. Unified Patient Context Layer (multi-modal fusion)

Every modality is normalized into one representation **before Maya responds**, so text, voice, an X-ray, and a lab PDF all contribute to a single understanding.

```
INPUTS                        NORMALIZE                 UNIFIED OBJECT
typed text      ─┐
voice transcript ┤            each becomes a
uploaded PDF     ┼──► patient_observation ──►  ┌───────────────────────────┐
lab report       ┤   {modality, type,         │  UNIFIED PATIENT CONTEXT  │
prescription     ┤    content, value,          │  • demographics            │
imaging report   ┤    observed_at,             │  • active clinical facts   │
photo            ┘    provenance, confidence}   │  • open threads + loops    │
                                                │  • reasoning chains (§5)   │
                                                │  • behavioral insights     │
                                                │  • recent observations     │
                                                │  • risk snapshot           │
                                                └───────────┬───────────────┘
                                                            ▼ token-budgeted pack → Maya
```
```
patient_observations          -- the common substrate for ALL modalities
  id, patient_id, source_modality ENUM(text, voice, image, pdf, lab, rx, imaging, note)
  source_id, observation_type, content TEXT, structured JSONB,
  observed_at, confidence, created_at
```
**Voice == text:** a voice transcript creates `patient_observations` exactly like typed text, so spoken symptoms enter memory identically (your requirement #4).

---

## 5. Clinical Reasoning Layer (relationships, not lists)

Maya understands that events **connect**. A reasoning pass builds a graph over the timeline.

```
event_relationships
  id, patient_id, from_event_id, to_event_id
  relation ENUM(caused_by, treats, improved_by, worsened_by,
                follow_up_of, ruled_out, related_to, side_effect_of)
  confidence, rationale TEXT, created_by ENUM(rule, llm), created_at
```

```
TIMELINE                          REASONING GRAPH                 MAYA UNDERSTANDS
Jan  Hypertension diagnosed  ─┐    diagnosed ──treats──► Lisinopril   "Your blood pressure
Feb  Lisinopril started      ─┼─►  Lisinopril ─improved─► BP April    improved after starting
Apr  BP improved             ─┘                                       Lisinopril in February."
```

**How it's built:** after each new event, a lightweight reasoning step (rules first, LLM for nuance) proposes edges among recent related events; edges are stored with confidence + rationale. Maya consumes the **chains** (not raw lists) so she can explain *why* things happened and spot patterns (e.g., a symptom that recurs after a medication change → flag a possible side effect).

**Safety:** reasoning is decision-*support*, surfaced as hypotheses with confidence, never as definitive diagnosis; red-flag rules always override.

---

## 6. Voice & Multi-Modal Architecture (voice as a primary interface)

```
PHASE A (v1)  Voice-to-text     on-device STT → editable transcript → Maya
PHASE B (v2)  Voice notes       record/upload → Whisper → transcript + memory
PHASE C (v3)  Voice conversation full-duplex: STT ⇄ Maya ⇄ TTS, barge-in,
                                  streaming — voice becomes the primary UI
```
- **Storage:** audio in a private bucket; `voice_notes` holds audio_url + transcript + status.
- **Processing:** async transcription; partials < 300 ms, full note < 3 s (§ targets).
- **AI integration:** every transcript → `patient_observations` (§4) → identical memory contribution as text.
- **Multi-modal:** images/PDFs/labs/prescriptions all run the §V2-document pipeline, emit `patient_observations` + `document_extractions`, and join the Unified Context. Maya can therefore reason across a spoken symptom + an uploaded lab + a prior assessment in a single reply.

---

## 7. Maya Conversation Quality Specification

A complete style guide so Maya sounds like an **experienced triage nurse**, never an AI.

### 7.1 Identity
Maya is a seasoned triage nurse: calm, competent, warm but efficient, unhurried yet focused. She listens, confirms, and guides.

### 7.2 Core principles
1. **No gratitude filler.** Never open with thanks/great/appreciation.
2. **Acknowledge briefly, then advance.** "I understand." → next question.
3. **One question at a time**, specific and purposeful.
4. **Confirm, don't re-collect** known facts for returning patients.
5. **Empathy when warranted** (pain, fear, bad news), not every turn.
6. **Plain language**, no jargon unless the patient uses it.
7. **Safety first** — no diagnosis, no prescription dosing; escalate red flags immediately.

### 7.3 Banned phrases → replacements
| ❌ Never | ✅ Instead |
|---|---|
| "Thank you for sharing." | "I understand." / "Okay." |
| "Great, thanks!" | "When did this start?" |
| "Thanks for letting me know." | "Let's look at that more closely." |
| "I appreciate the details." | "Can you describe it more specifically?" |
| "I'm sorry to hear that" (overused) | (reserve for genuinely distressing news) |

### 7.4 Questioning strategy
- Funnel: **open → focused → specific** (OPQRST/SOCRATES for pain: Onset, Provocation, Quality, Region/Radiation, Severity, Timing).
- Adapt to answers; never ask what's already in memory — **confirm** it.
- Surface red flags early; if any emergency criterion is met, stop questioning and escalate.

### 7.5 Tone by situation
- **Emergency:** calm authority, unambiguous directive. *"This needs emergency care now. Please call 911 or go to the nearest ER — I'll stay with you while you arrange that."* No hedging, no false reassurance.
- **Follow-up (proactive):** caring, low-pressure, specific. *"It's been two weeks since you started Lisinopril — how are you tolerating it?"*
- **Routine:** efficient and reassuring without dismissing.
- **Bad news / worry:** brief genuine empathy, then a concrete next step.

### 7.6 Healthcare communication standards
- Always include a clear next step and warning signs.
- Never promise outcomes; never diagnose; always note Maya supports, not replaces, a clinician.
- Respect privacy and dignity; trauma-informed phrasing.

### 7.7 Implementation note
This becomes the new `TRIAGE_SYSTEM_PROMPT` + a `CONVERSATION_STYLE` block + a runtime banned-phrase check. **It is non-migration and can ship in Phase 0** independently of the schema.

---

## 8. Maya Experience Dashboard (patient) — "my relationship with Maya"

Every element is framed as Maya's, not a portal's.

```
┌──────────────────────────────────────────────────────────────┐
│  Maya                                  🔔 From Maya (2)        │
│  "Welcome back, John. How are you feeling today?"             │
│  [ 🎤 Talk to Maya ]   [ Continue our last conversation → ]   │
├───────────────────────────┬──────────────────────────────────┤
│  FROM MAYA (proactive)    │  MAYA'S RECOMMENDATIONS           │
│  • BP check-in due (Jun 5)│  • Monitor glucose daily          │
│  • "How's the new med?"   │  • Recheck BP in 2 weeks          │
├───────────────────────────┼──────────────────────────────────┤
│  MAYA'S HEALTH INSIGHTS   │  OUR CONVERSATIONS (history)      │
│  • BP improving since Feb │  May 20 · Follow-up → improving   │
│  • 3rd chest-pain report  │  Apr 11 · Lab review              │
│    in 90 days             │  Feb 15 · Chest pain → L2 Urgent  │
├───────────────────────────┴──────────────────────────────────┤
│  MAYA'S SUMMARY OF YOU                                        │
│  "John, 54. Managing hypertension and type 2 diabetes.       │
│   BP improving on Lisinopril. Watching recurring chest        │
│   discomfort and an elevated HbA1c trend."                    │
├──────────────────────────────────────────────────────────────┤
│  HEALTH TIMELINE (with connections) ─ see §5 reasoning chains │
└──────────────────────────────────────────────────────────────┘
```
Surfaces: **From Maya** (follow-ups/reminders) · **Maya's Recommendations** · **Maya's Health Insights** · **Our Conversations** · **Maya's Summary** · **Health Timeline**. Medical records/documents live one tap away, each with "Ask Maya about this."

---

## 9. Maya Intelligence Admin Dashboard

Measures **operational performance** *and* **Maya's effectiveness**.

```
┌──────────────── MAYA INTELLIGENCE ───────────────────────────┐
│ ENGAGEMENT                 FOLLOW-UPS            QUALITY       │
│ Active patients   312      Sent        140      Avg confidence │
│ Conversations/wk  480      Completed   86 (61%) 0.82          │
│ Voice usage       38%      Dismissed   12        Escalation    │
│ Return rate (30d) 54%      Overdue      9        accuracy 94%  │
├───────────────────────────────────────────────────────────────┤
│ OPERATIONAL                CLINICAL                            │
│ Assessments today 24       Top symptoms: chest pain, headache │
│ Emergency flags    2       Triage mix: L1 2 · L2 7 · L3 …      │
│ Risk distribution ▕█▎▍▋    Common recommendations (ranked)    │
├───────────────────────────────────────────────────────────────┤
│ PATIENT MONITORING (drill → patient's Maya timeline)          │
│ 🔴 High-risk (5) · Escalated (2) · Frequent users 3+/30d (8)  │
│ Follow-up non-compliant (9) · Inactive high-risk (3)          │
└───────────────────────────────────────────────────────────────┘
```
**Maya effectiveness metrics:** usage, follow-up completion rate, patient engagement/return rate, escalation statistics + accuracy, common recommendations, and AI assessment-quality signals (confidence distribution, completion rate, time-to-report, override/escalation correctness).

---

## 10. Final Database Schema (Version 3)

All additive & nullable → zero risk to existing rows. Adds the V3 intelligence tables on top of V2.

```
EXISTING (✅)  organizations, users, patients, providers, assessments,
              conversations, symptoms, risk_factors, risk_scores,
              triage_reports, audit_logs, notifications

EXTEND patients  + user_id, emergency_contact_*, organization_id NULLABLE
EXTEND assessments + thread_id (NULL FK → care_threads)

MEMORY (V2)          clinical_facts · assessment_memory · patient_insights · timeline_events
MULTI-MODAL (V3)     patient_observations · documents · document_extractions · voice_notes
REASONING (V3)       event_relationships
CONTINUITY (V3)      care_threads · care_actions
FOLLOW-UP (V3)       follow_up_rules · follow_ups
ONBOARDING/UX        onboarding_progress · follow_up_reminders(→ folded into follow_ups)
OPTIONAL             memory_index (pgvector semantic recall)
```
*(Full column definitions for each table appear in §2–§6 above. The migration will be presented table-by-table for your line-by-line approval before anything touches Supabase.)*

---

## 11. End-to-End Patient Journey (the relationship over time)

```
DAY 0   Register → onboarding (profile, conditions, allergies, meds, optional labs)
        → Maya intro greets using onboarding data → first assessment is context-rich
        → memory written: clinical_facts, assessment_memory, timeline_event, thread opened
        → care_action created ("recheck BP in 2 weeks") → follow_up scheduled

DAY 14  Follow-Up Engine fires → "From Maya: how are you tolerating Lisinopril?"
        → patient engages by voice → transcript → observations → memory updated
        → care_action closed, thread summary updated

WEEK 4  Patient uploads a lab PDF → pipeline extracts HbA1c 8.1% (high)
        → document_extraction + timeline_event + clinical_fact
        → reasoning layer links it to the diabetes thread → insight: "worsening trend"

MONTH 1 Patient returns with new symptom → UPCL fuses everything →
        Maya: "Welcome back, John. Your April HbA1c was up to 8.1%. Is today
        related to your diabetes, or something new?" → reasons over the chain

MONTH 3 Proactive medication check-in; behavioral memory notes 3rd chest-pain
        report in 90 days → Maya escalates monitoring, flags to admin high-risk list

MONTH 6+ Maya speaks from a rich, connected history — recommendations build on
        outcomes, follow-ups are timely, the relationship compounds.
```

---

## 12. Roadmap (unchanged sequencing, Maya-first)

| Phase | Scope | Migration? |
|---|---|---|
| **0** | Conversation Quality Spec (§7) + voice-to-text v1 (§6 Phase A) | **No** — ship anytime |
| 1 | Approve §10 schema → additive migration (reviewed table-by-table) | Yes |
| 2 | Patient↔user link + redesigned onboarding + Unified Context skeleton | Yes |
| 3 | Memory write-back + Context Assembly + Continuity (threads/loops) + greetings | — |
| 4 | Follow-Up Engine + scheduler + admin rules | — |
| 5 | Clinical Reasoning Layer (relationships) | — |
| 6 | Document intelligence + voice notes (server STT) | — |
| 7 | Maya Experience dashboard + Maya Intelligence admin dashboard | — |
| 8 | Performance targets + hardening | — |
| 9 (later) | Full-duplex voice conversation (§6 Phase C) | — |

**Phase 0 needs no schema change** — Maya's nurse personality and tap-to-speak can ship immediately while you review §10.

---

*Nothing in Phases 1–9 runs until you approve this document and the §10 schema.*
