# Neural Hub — Production-Readiness Architecture (Version 4)

> **Final approval package before any database migration or implementation.** Design only.
> Builds on V3 (Maya as a Digital Nurse). Legend: ✅ exists · 🟡 partial · 🔲 to build
> All new tables/columns are **additive & nullable** — zero risk to existing rows.

**Purpose of V4:** V3 designed *what Maya is*. V4 designs *what it takes to run her safely in production* — escalation, governance, explainability, cost, compliance, tenancy, learning, and reliability. Nothing here changes the Maya vision; it makes that vision operable, auditable, and legally defensible from day one.

```
                 ┌─────────────────────────────────────────────┐
                 │                    MAYA (V3)                 │
                 └───────────────────┬─────────────────────────┘
   ┌──────────────┬──────────────┬───┴───────┬──────────────┬──────────────┐
   ▼              ▼              ▼           ▼              ▼              ▼
ESCALATION    GOVERNANCE   EXPLAINABILITY  COMPLIANCE   RELIABILITY    LEARNING
human in the  conflicts &   every claim     HIPAA, audit  graceful       safe self-
loop (§1)     decay (§2)    has evidence(§3) consent (§5)  degradation(§8) improvement(§7)
        SCALABILITY (§4)  ─────────────────  MULTI-TENANCY (§6)
        cost & limits at 100→100k patients   isolation & roles across clinics/hospitals
```

---

## 1. Human Escalation & Clinical Oversight Architecture

**Principle:** Maya is decision-*support*. A human must own every high-acuity outcome. Maya never silently "handles" an emergency — she advises the patient **and** creates an auditable escalation that a human can see and act on.

### 1.1 The two independent paths (both always fire on a red flag)
```
RED FLAG DETECTED (chest pain / stroke FAST / SI / anaphylaxis / resp. distress)
        │
        ├──► PATIENT PATH  (immediate, deterministic, never LLM-gated)
        │      • Maya stops triage questioning
        │      • shows unambiguous emergency directive ("Call 911 / go to ER now")
        │      • surfaces crisis resources (e.g., 988 for suicidal ideation)
        │      • offers to stay with the patient while they arrange care
        │
        └──► OVERSIGHT PATH  (creates a durable record + alerts humans)
               • create escalations row (severity, reason, snapshot)
               • notify org's on-call / admins (in-app + email/SMS per config)
               • surface on Clinician Oversight queue (real-time)
               • write audit_log entry
```
The patient path is **deterministic** (regex/rule pre-check already exists ✅) so it works even if the LLM is down. The oversight path is **asynchronous** so a slow notification never delays the patient's safety message.

### 1.2 Escalation tiers
| Tier | Examples | Patient sees | Oversight |
|---|---|---|---|
| **E1 Critical** | Stroke signs, active chest pain, anaphylaxis, suicidal ideation w/ plan | Call 911 now + crisis line | Immediate alert (in-app + SMS to on-call), top of queue, no auto-close |
| **E2 Urgent** | Severe but not immediately life-threatening (high fever + rigidity, severe dehydration) | Seek emergency/urgent care today | Alert within minutes, queue, 24h SLA |
| **E3 Concerning** | Worrying trend, repeated symptom, declined prior referral | Strong recommendation + warning signs | Queued for review, daily digest |

### 1.3 Data
```
escalations
  id, patient_id, assessment_id, organization_id
  tier ENUM(E1, E2, E3)
  reason_code        -- 'stroke_fast', 'cardiac_chest_pain', 'suicidal_ideation', ...
  trigger_source ENUM(rule, llm, both)
  context_snapshot JSONB   -- frozen copy of what Maya knew at escalation time (§3 evidence)
  status ENUM(open, acknowledged, in_review, resolved, auto_expired)
  acknowledged_by (user_id NULL), acknowledged_at
  resolved_by (user_id NULL), resolved_at, resolution_note
  created_at

escalation_events           -- immutable audit trail of every state change
  id, escalation_id, actor_user_id (NULL=system), action, note, created_at
```

### 1.4 Clinician Oversight queue (new admin/provider surface)
```
┌──────────── CLINICIAN OVERSIGHT ─────────────────────────────┐
│ 🔴 E1  John D.  Cardiac chest pain        2m ago  [Acknowledge]│
│ 🟠 E2  Mary S.  Severe dehydration       14m ago  [Open]      │
│ 🟡 E3  Sam P.   3rd chest-pain in 90d     1h ago  [Review]    │
│  Filters: tier · status · age of alert · assigned-to          │
└───────────────────────────────────────────────────────────────┘
```
- **Acknowledge → in_review → resolve**, each transition writes `escalation_events` (who/when/why).
- **No auto-resolution for E1/E2** — only a human closes them. E3 may auto-expire after a configured window with an audit note.
- **On-call routing** per org (`escalation_policy` in org config, §6.4): who is alerted, channel, quiet-hours override (safety alerts ignore quiet hours).

### 1.5 Safety guarantees
- Red-flag detection is **rule-first**; the LLM can *raise* but never *lower* a rule-determined emergency.
- The patient's emergency directive renders **before** any network call to oversight — safety messaging is never blocked on a notification.
- Every escalation is immutable + fully audited (legal defensibility, §5).

---

## 2. Maya Memory Governance Architecture

**Problem:** over years, memory grows, goes stale, and contradicts itself (patient says "hypertension"; later a clinician note says none). Governance keeps memory **bounded, current, and trustworthy**.

### 2.1 Four governance functions
```
1. RETENTION     keep what matters, age out the rest
2. COMPRESSION   summarize old detail into durable narrative, drop raw bulk
3. RECONCILIATION resolve contradictions by source authority + recency
4. LIFECYCLE     facts move active → superseded/resolved, never silently deleted
```

### 2.2 Fact lifecycle & provenance (extends V3 `clinical_facts`)
```
clinical_facts  (extend)
  + source ENUM(patient_reported, document_extracted, clinician_entered, maya_inferred)
  + source_confidence            -- 0–1
  + status ENUM(active, superseded, resolved, refuted)
  + effective_from, effective_to (NULL = ongoing)
  + superseded_by_fact_id (NULL FK self)
  + last_confirmed_at
```
A fact is never hard-deleted; it transitions. "Hypertension (patient_reported)" becomes `refuted` and points to the clinician fact that overrode it — history stays auditable, but Maya only *reasons* on `active` facts.

### 2.3 Reconciliation rule (source authority ladder)
```
when two facts conflict on the same clinical concept:
   authority:  clinician_entered  >  document_extracted  >  patient_reported  >  maya_inferred
   tie-break:  more recent effective_from wins
   action:     lower-authority fact → status=refuted, superseded_by = winner
               Maya may *gently* surface the discrepancy, never argue:
               "Your records don't show a hypertension diagnosis — has a provider
                ever diagnosed you with high blood pressure?"
```
Reconciliation runs on every new fact write; conflicts above a confidence threshold are logged for clinician review rather than auto-resolved when authority is equal.

### 2.4 Compression & retention
- **Tiered memory:** *Hot* (last 90 days, full detail) → *Warm* (Maya-summarized per `care_thread`) → *Cold* (archived raw, retrievable on demand / for audit).
- **Thread summaries** (V3 `care_threads.summary`) are the durable compressed narrative; raw conversational turns older than the hot window are summarized then their bulk is archived, not loaded into context.
- **Resolved conditions** stay queryable ("history of…") but are excluded from the active context pack unless relevant.
- Retention windows are **org-configurable** but floored by the compliance retention policy (§5.4).

### 2.5 Outdated medications / resolved conditions
- Medications carry `effective_to`; when a patient or document indicates a stop, the med fact is closed and a `timeline_event` records the change. Maya stops treating it as current and the reasoning layer (V3 §5) can attribute symptom changes to the med stop.

---

## 3. Explainability & Evidence Architecture

**Principle:** every claim Maya makes about the past must be **traceable to its sources** with a confidence. No unprovenanced assertions like "you reported chest pain three times" — that statement must resolve to three specific assessments.

### 3.1 Evidence model
```
maya_claims                       -- a statement Maya surfaced that references history
  id, patient_id, assessment_id
  claim_text                      -- "You reported chest discomfort 3 times in 90 days"
  claim_type ENUM(recall, trend, recommendation, reasoning)
  confidence                      -- aggregate, 0–1
  created_at

claim_evidence                    -- many-to-one: what backs the claim
  id, claim_id
  source_type ENUM(assessment, document, observation, clinical_fact, event_relationship)
  source_id
  contribution                    -- weight / note ("chest pain symptom on 2026-02-15")
```
Most claims are assembled deterministically (the Unified Context already holds the source IDs), so evidence is captured **at assembly time**, not reconstructed later.

### 3.2 Patient-facing transparency
Any Maya statement that references history is expandable:
```
"You've reported chest discomfort 3 times in the last 90 days."   [ Why does Maya know this? ▾ ]
   • Feb 15 assessment — chest pain (L2 Urgent)
   • Mar 22 assessment — chest tightness
   • May 03 follow-up — "mild chest discomfort"
   Confidence: high · Sources: 3 assessments
```
This drives the patient dashboard's "Ask Maya about this" and the timeline's connection lines (V3 §8).

### 3.3 Confidence semantics
- Confidence is shown as **High / Moderate / Low**, mapped from a numeric score (source authority × recency × corroboration count).
- Reasoning-layer hypotheses (V3 §5) **always** display confidence and are labeled as observations, never diagnoses.
- Low-confidence recall is phrased tentatively ("I think you mentioned…") or withheld.

---

## 4. AI Cost & Scalability Architecture

**Goal:** know the unit economics before scaling, and where the architecture bends.

### 4.1 Cost drivers per active patient (typical month)
| Driver | Unit assumption | Notes |
|---|---|---|
| Assessment conversation | ~8–15 LLM calls, ~6–12k tokens total | dominant cost |
| Context assembly | token-budgeted pack (~2–4k in) per turn | capped by §4.3 budget |
| Embeddings (memory_index) | ~1 embed per new fact/observation | cheap, batched |
| Document extraction | OCR + 1–2 LLM calls per upload | per-upload, not per-turn |
| Voice transcription | Whisper ~$0.006/min | only if voice used |
| Storage | rows + documents + audio | grows linearly, see §4.4 |

### 4.2 Scale tiers (order-of-magnitude planning, not a quote)
```
              LLM load          Bottleneck appears at        Mitigation
100 pts       trivial           none                         single instance, direct DB
1,000 pts     light             DB round-trips (remote)       connection pooler (6543), caching
10,000 pts    moderate          LLM rate limits, embed cost   request queue, batch embeds, cache
                                                              context packs, cheaper model tier
100,000 pts   heavy             LLM spend, doc/voice pipeline  async worker fleet, model routing
                                  storage, vector search       (cheap model for simple turns),
                                                              pgvector → dedicated vector store,
                                                              tiered storage, regional read replicas
```

### 4.3 Cost-control levers (designed in, not bolted on)
- **Token budgeting:** the Unified Context pack is hard-capped; memory is tiered (§2.4) so context size is ~constant regardless of history length — **this is the key scalability lever** (history grows, prompt size doesn't).
- **Model routing:** cheap/fast model for simple turns and classification; premium model for risk assessment and reasoning. Config-driven per org.
- **Caching:** assembled context packs cached per session; embeddings computed once per fact.
- **Batching:** embeddings and reasoning passes batched off the hot path (async workers).
- **Rate limiting & quotas:** per-org request quotas; backpressure queue protects the LLM budget and the provider rate limits.

### 4.4 Storage growth
- Structured rows: linear, cheap. Documents & audio dominate — store in object storage (not DB), lifecycle-tier cold media, and keep only extractions/transcripts hot. Audit logs are append-only and archived on the compliance schedule (§5.4).

### 4.5 Observability for cost
- Per-org, per-feature token & cost metering (folds into the analytics layer, §7) so admins see spend and we can alert on anomalies. This is the input to org-level quotas and pricing.

---

## 5. Healthcare Compliance & Legal Safety Architecture

**Principle:** compliance is designed in from day one, not retrofitted. Target posture: **HIPAA-ready** (PHI handled as protected from the first migration).

> Engineering posture, not legal advice — final HIPAA validation requires counsel + a signed BAA with each subprocessor (LLM provider, hosting, STT). The architecture is built so that validation is achievable, not blocked.

### 5.1 HIPAA technical safeguards (mapped to this platform)
| Safeguard | Implementation |
|---|---|
| Access control | RBAC (✅ `require_role`), org isolation (§6), capability tokens for anonymous flow |
| Audit controls | append-only `audit_logs` (✅) extended to **every PHI read/write/export** (§5.3) |
| Integrity | immutable escalation/audit trails; memory transitions never hard-delete clinical data |
| Transmission security | TLS everywhere (✅ SSL to Supabase), encrypted object storage |
| Encryption at rest | DB + bucket encryption; secrets never in repo (✅ gitignored `.env`) |
| Minimum necessary | context packs include only what Maya needs; role-scoped API responses |
| BAA chain | requires signed BAAs: LLM provider, hosting/DB, STT, email/SMS — tracked as a launch gate |

### 5.2 Consent management
```
consents
  id, patient_id, organization_id
  type ENUM(treatment_triage, data_processing, ai_use, document_storage,
            voice_recording, marketing_followups, research_analytics)
  status ENUM(granted, denied, withdrawn)
  version            -- which policy version was agreed
  granted_at, withdrawn_at, evidence JSONB (IP, UA, method)
```
- Consent is **versioned** and **withdrawable**; withdrawal flips downstream behavior (e.g., withdraw `voice_recording` → STT disabled, existing audio honored per retention).
- Maya gates features on consent (no voice capture without `voice_recording`; analytics/learning use requires `research_analytics`, §7.1).

### 5.3 Audit logging (PHI access tracking)
- Every PHI **read** (who viewed which patient), **write**, **export/print**, and **document download** writes an `audit_logs` row: `actor, action, resource_type, resource_id, patient_id, org_id, ip, ua, timestamp, purpose`.
- Document access specifically tracked (`document_access_log` view over audit_logs) so an org can answer "who saw this lab report and when."
- Audit logs are append-only and retained per §5.4.

### 5.4 Data retention & deletion
- **Configurable retention** per org, floored by jurisdictional minimums (clinical records often 6–10 yrs).
- **Patient rights:** export (machine-readable bundle) and deletion request → soft-delete + scheduled purge of PHI while retaining de-identified audit metadata where law requires.
- **De-identification** path for analytics/learning (§7) so model-improvement never uses raw PHI without consent.

### 5.5 AI disclaimer strategy
- Maya states, at first contact and in reports: she provides **triage guidance, not a diagnosis**, and does not replace a clinician.
- Emergency directives are unambiguous and never hedged.
- Reports carry a standardized disclaimer + the evidence/confidence (§3) behind recommendations.

### 5.6 Privacy controls
- Patients see what Maya knows (§3 transparency), can correct facts (feeds §2 reconciliation as `patient_reported`), and manage consents from the dashboard.

---

## 6. Multi-Tenant Organization Architecture

**Principle:** strict isolation between organizations, with flexible roles inside one. Supports the spectrum: solo patient → clinic → medical group → hospital.

### 6.1 Tenancy model
```
organizations (✅)  ── every PHI-bearing row carries organization_id
   │
   ├─ users (✅, role-scoped)        super_admin · admin · provider · patient · viewer
   ├─ patients (✅, org_id NULLABLE) -- self-registered patient may be org-less until linked
   ├─ providers (✅)
   └─ all V3/V4 tables               carry organization_id for isolation
```
- **Row-level isolation:** every query is org-scoped by a mandatory filter in the data layer; the IDOR fix pattern (capability-or-org check, ✅) is the template. Optionally enforce with Postgres RLS as defense-in-depth.
- **The org-less patient:** a self-registered patient (V3) has `organization_id = NULL` and a private capability scope until they join/are claimed by an org (e.g., a clinic invites them) — then their records are linked, with consent.

### 6.2 Roles & permissions (matrix)
| Capability | super_admin | admin | provider | patient | viewer |
|---|---|---|---|---|---|
| Manage org config / rules | ✅ (any org) | ✅ (own org) | — | — | — |
| View all org patients | ✅ | ✅ | assigned only | self only | read-only scope |
| Acknowledge/resolve escalations | ✅ | ✅ | ✅ | — | — |
| Configure follow-up rules | ✅ | ✅ | — | — | — |
| Talk to Maya / own records | — | — | — | ✅ | — |
| Cross-org access | ✅ only | — | — | — | — |

### 6.3 Cross-organization protection
- **No cross-org reads** except `super_admin` (platform operator). Provider access is further scoped to **assigned** patients within their org (assignment table), not the whole org by default.
- Capability tokens (anonymous flow) are single-resource scoped — never widen to an org.

### 6.4 Organization-level configuration
```
organization_settings
  id, organization_id
  follow_up_rules (→ V3), escalation_policy JSONB (on-call, channels, quiet hours),
  retention_policy JSONB, consent_policy_version, enabled_features JSONB,
  model_routing JSONB (which model tier), branding JSONB
```
Safe defaults ship; large orgs (hospitals) can tune cadence, on-call routing, retention, and which Maya features are enabled.

---

## 7. AI Analytics & Continuous Improvement Architecture

**Principle:** Maya improves over time **without** compromising safety or privacy. Improvement is measured, versioned, and de-identified.

### 7.1 What is stored for improvement (consent-gated)
- Only patients with `research_analytics` consent (§5.2) contribute to improvement datasets, and contributions are **de-identified** (PHI stripped/tokenized).
- Stored: prompt version, model, inputs (de-identified), Maya output, triage level, confidence, and **outcome signals** (escalation correctness, follow-up completion, patient correction of a fact, clinician override).

### 7.2 Prompt versioning
```
prompt_versions
  id, name (e.g. 'triage_system', 'greeting', 'reasoning')
  version, content_hash, body, model_target, created_by, created_at, is_active

assessment_runs (extend assessments)
  + prompt_version_id, model_used, token_usage JSONB, latency_ms
```
Every assessment records exactly which prompt version + model produced it → reproducibility and A/B attribution.

### 7.3 Outcome measurement & comparison
```
SIGNALS                                  → METRICS
escalation later confirmed/overturned    → escalation accuracy / false-positive rate
follow-up completed                      → engagement & adherence
patient corrected a Maya fact            → recall precision
clinician override of triage level       → triage calibration
time-to-report, confidence distribution  → quality & efficiency
```
- **A/B / shadow eval:** new prompt versions can run in shadow (logged, not shown) or as a guarded % rollout per org; metrics compared version-vs-version.
- **Poor-assessment detection:** low confidence + override + patient correction flags an assessment for human review and into the improvement backlog.

### 7.4 Safety guardrails on learning
- No automated prompt changes in production — version promotion is a **human decision** gated on metrics.
- Red-flag/escalation rules are **never** learned away; they are deterministic and versioned separately.
- This feeds the admin **Maya effectiveness** dashboard (V3 §9).

---

## 8. Reliability & Failure Recovery Architecture

**Principle:** degrade gracefully, never unsafely. Safety-critical paths must work even when AI/infra is down.

### 8.1 Failure modes & responses
| Failure | Detection | Response | Patient experience |
|---|---|---|---|
| **OpenAI unavailable** | timeout / 5xx | fail over to Anthropic (✅ fallback); if both down → **rule-only safe mode** | "I'm having a brief issue — if this is an emergency, call 911. Otherwise let's continue." Red-flag rules still fire. |
| **Both LLMs down** | health check | safe mode: deterministic intake + emergency rules only; queue full assessment | basic triage + clear emergency guidance preserved |
| **Speech-to-text fails** | job error | fall back to typing; keep audio, retry async | "I couldn't process the audio — could you type it, or try again?" |
| **Document extraction fails** | pipeline error | store file, mark `extraction_failed`, retry w/ backoff, flag for manual review | upload succeeds; "I'll review this and follow up." |
| **Follow-up scheduler fails** | missed-run monitor | idempotent catch-up on next run; no duplicate sends (dedupe key) | follow-ups arrive late, never doubled or lost |
| **DB latency spike** | slow-query metric | timeouts + retries, serve cached context, shed non-critical writes to queue | slightly slower; safety messaging unaffected |
| **Supabase unavailable** | connection error | read cache for context; **buffer writes to a durable queue**, replay on recovery; safety path uses last-known + rules | "I'm reconnecting — if urgent, call 911." No data loss on recovery. |

### 8.2 Core reliability patterns
```
• Deterministic safety core   — emergency detection is rule-based, no external dep
• Provider failover           — OpenAI → Anthropic → safe mode (✅ partial today)
• Idempotency                 — follow-ups & escalations use dedupe keys (no dup alerts/sends)
• Async + retry w/ backoff    — doc/voice/embed/reasoning off the hot path, retried
• Durable write queue         — buffer on DB outage, replay on recovery (no lost PHI writes)
• Circuit breakers + timeouts — every external call bounded; cached fallbacks where safe
• Health checks + alerting    — LLM, DB, scheduler, STT monitored; ops alerted
• Graceful UI degradation     — error boundaries (✅) + calm getErrorMessage (✅), never raw errors
```

### 8.3 Recovery guarantees
- **No lost clinical writes:** buffered + replayed on recovery.
- **No duplicate safety alerts:** idempotent escalation/follow-up creation.
- **No blocked emergencies:** the patient safety path never depends on the LLM or a successful notification.

---

## 9. Updated Database Schema (Version 4)

All additive & nullable. V4 adds the production-readiness tables on top of V3.

```
EXISTING (✅)   organizations, users, patients, providers, assessments,
               conversations, symptoms, risk_factors, risk_scores,
               triage_reports, audit_logs, notifications

V2 MEMORY       clinical_facts · assessment_memory · patient_insights · timeline_events
V3 MULTI-MODAL  patient_observations · documents · document_extractions · voice_notes
V3 REASONING    event_relationships
V3 CONTINUITY   care_threads · care_actions
V3 FOLLOW-UP    follow_up_rules · follow_ups

── V4 ADDITIONS ───────────────────────────────────────────────────────────
ESCALATION (§1)   escalations · escalation_events
GOVERNANCE (§2)   EXTEND clinical_facts (+source, +status, +effective_*, +superseded_by,
                  +source_confidence, +last_confirmed_at)
EXPLAINABILITY(§3) maya_claims · claim_evidence
COMPLIANCE (§5)   consents · (audit_logs extended: +purpose, +ip, +ua, +resource fields;
                  document_access_log = view over audit_logs)
MULTI-TENANT (§6) organization_settings · provider_patient_assignments
                  (+organization_id on every V3/V4 PHI table that lacks it)
ANALYTICS (§7)    prompt_versions · improvement_samples (de-identified)
                  EXTEND assessments (+prompt_version_id, +model_used, +token_usage, +latency_ms)
RELIABILITY (§8)  no schema (queue/cache/circuit-breakers are infra) ·
                  EXTEND documents (+extraction_status); follow_ups already has dedupe via status
OPTIONAL          memory_index (pgvector semantic recall, from V3)
```
*(Column definitions live inline in §1–§7. Migration is presented table-by-table for line-by-line approval before anything touches Supabase.)*

**Migration safety properties:** every addition is a new table or a NULLABLE column with a default; no existing column is renamed, retyped, or dropped; backfills are optional and run after deploy. The platform runs unchanged the moment before and after each step.

---

## 10. Updated End-to-End Patient Journey (with production safety)

```
DAY 0   Register → consents captured (treatment_triage, ai_use, data_processing; voice optional)
        → onboarding → first assessment (records prompt_version + model + tokens)
        → memory written with source=patient_reported + confidence
        → audit_log: every PHI write recorded

DAY 0+  Patient describes crushing chest pain →
        RULE pre-check fires → PATIENT PATH: "Call 911 now, I'll stay with you"
        → OVERSIGHT PATH: escalation(E1) created → on-call provider alerted (SMS+in-app)
        → Clinician Oversight queue shows it → provider acknowledges → resolves w/ note
        → escalation_events + audit_logs capture the whole chain

DAY 14  Follow-Up Engine fires (idempotent) → "How are you tolerating Lisinopril?"
        → patient answers by voice (consent present) → transcript → observation → memory
        → care_action closed; thread summary compressed (governance §2.4)

WEEK 4  Lab PDF uploaded → extraction (retry-safe) → HbA1c 8.1% (high)
        → clinical_fact(source=document_extracted) → reconciliation vs prior patient-reported
        → reasoning links to diabetes thread → maya_claim "worsening trend" + claim_evidence

MONTH 1 Returns → Unified Context (token-budgeted, ~constant size despite history)
        → Maya: "Your April HbA1c was up to 8.1%… related to your diabetes, or new?"
        → patient taps "Why does Maya know this?" → sees the 3 source assessments + confidence

MONTH 3 Clinician note contradicts a patient-reported fact → reconciliation:
        clinician > patient → old fact refuted (kept for audit), Maya updates gently
        → improvement_sample (de-identified, consented) logs the correction signal

— Through all of this: org isolation holds, every read/write is audited, consent gates
  features, costs are metered per org, and if OpenAI/Supabase hiccup, safety still works. —
```

---

## 11. Production-Readiness Checklist (what V4 unlocks before launch)

| Area | Gate before go-live |
|---|---|
| Escalation | Oversight queue live, on-call routing tested, E1 never auto-closes |
| Governance | Reconciliation + lifecycle active; no hard-deletes of clinical facts |
| Explainability | Every history claim resolves to evidence + confidence |
| Cost | Per-org metering + quotas; context pack capped; model routing on |
| Compliance | BAAs signed (LLM/host/STT/SMS), audit on all PHI access, consents enforced |
| Multi-tenant | Org isolation verified (RLS or data-layer), cross-org read blocked |
| Analytics | Prompt versioning + outcome signals; human-gated promotion |
| Reliability | Failover + safe mode + durable write queue tested; no blocked emergencies |

---

## 12. Roadmap (V4 sequencing, layered onto V3)

| Phase | Scope | Migration? |
|---|---|---|
| **0** | Conversation Quality Spec + voice-to-text v1 (V3 §7/§6) + **AI disclaimer copy** (§5.5) | **No** |
| 1 | Approve schema → additive migration, table-by-table | Yes |
| 2 | Multi-tenant hardening (org_id everywhere, assignments, RLS) + consents (§5,§6) | Yes |
| 3 | **Escalation + Clinician Oversight queue** (§1) — highest safety priority | Yes |
| 4 | Memory governance (lifecycle, reconciliation, compression) (§2) | Yes |
| 5 | Explainability/evidence capture at assembly (§3) | Yes |
| 6 | Follow-Up Engine + reasoning + multi-modal (V3 §3/§5/§4) | Yes |
| 7 | Analytics, prompt versioning, improvement loop (§7) | Yes |
| 8 | Reliability hardening: failover, safe mode, write queue (§8) + cost metering (§4) | partial |
| 9 | Dashboards (patient + admin), perf targets (V3 §8/§9) | — |

**Phase 0 still needs no schema change.** Escalation (§3 of roadmap) is intentionally sequenced **early** — it is the most safety-critical addition.

---

*Nothing in Phases 1–9 runs until you approve this document and the §9 schema. Design only — no migration has been performed.*
