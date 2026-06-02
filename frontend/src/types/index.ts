// ── Auth ──────────────────────────────────────────────────────────────────
export type UserRole = "super_admin" | "admin" | "provider" | "patient" | "viewer";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  avatar_url: string | null;
  phone: string | null;
  organization_id: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ── Patient ───────────────────────────────────────────────────────────────
export type BiologicalSex = "male" | "female" | "other" | "prefer_not_to_say";

export interface Patient {
  id: string;
  mrn: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  age: number | null;
  date_of_birth: string | null;
  biological_sex: BiologicalSex | null;
  email: string | null;
  phone: string | null;
  allergies: string[];
  chronic_conditions: string[];
  current_medications: object[];
  is_active: boolean;
  organization_id: string;
  created_at: string;
}

// ── Triage ────────────────────────────────────────────────────────────────
export type TriageLevel =
  | "L1_EMERGENCY"
  | "L2_URGENT"
  | "L3_MODERATE"
  | "L4_LOW_RISK"
  | "L5_SELF_CARE";

export type AssessmentStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "escalated"
  | "abandoned";

export interface Assessment {
  id: string;
  patient_id: string;
  session_token: string;
  status: AssessmentStatus;
  triage_level: TriageLevel | null;
  urgency_score: number | null;
  confidence_score: number | null;
  chief_complaint: string | null;
  ai_model_used: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  node_name: string | null;
  created_at: string;
}

export interface TriageMessageResponse {
  message: string;
  node: string;
  is_complete: boolean;
  requires_escalation: boolean;
  triage_level: TriageLevel | null;
}

export interface TriageReport {
  id: string;
  assessment_id: string;
  patient_summary: string;
  symptoms_summary: string;
  risk_assessment: string;
  clinical_concerns: string[];
  recommended_next_step: string;
  urgency_level: TriageLevel;
  urgency_rationale: string;
  followup_recommendation: string;
  escalation_notes: string | null;
  care_pathway: string;
  reasoning_chain: string[];
  confidence_breakdown: Record<string, number>;
  report_pdf_url: string | null;
  generated_at: string;
}

export interface RiskScore {
  id: string;
  assessment_id: string;
  cardiac_risk: number;
  stroke_risk: number;
  sepsis_risk: number;
  respiratory_risk: number;
  mental_health_risk: number;
  anaphylaxis_risk: number;
  pregnancy_risk: number;
  medication_risk: number;
  overall_score: number;
  highest_risk_category: string | null;
}

// ── Analytics ─────────────────────────────────────────────────────────────
export interface DashboardStats {
  period_days: number;
  total_assessments: number;
  completed_assessments: number;
  escalated_assessments: number;
  emergency_cases: number;
  urgent_cases: number;
  high_risk_cases: number;
  high_risk_rate: number;
  avg_triage_time_seconds: number;
  avg_triage_time_minutes: number;
  level_distribution: Record<string, number>;
  daily_trend: { date: string; count: number }[];
  completion_rate: number;
}

// ── UI Helpers ────────────────────────────────────────────────────────────
export const TRIAGE_LEVEL_CONFIG: Record<
  TriageLevel,
  { label: string; color: string; bgColor: string; borderColor: string; icon: string; action: string }
> = {
  L1_EMERGENCY: {
    label: "Emergency",
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
    icon: "🚨",
    action: "Call 911 / Go to ED Now",
  },
  L2_URGENT: {
    label: "Urgent",
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
    icon: "⚠️",
    action: "Same-Day Provider Visit",
  },
  L3_MODERATE: {
    label: "Moderate",
    color: "text-yellow-700 dark:text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
    icon: "🟡",
    action: "Visit Within 24-72 Hours",
  },
  L4_LOW_RISK: {
    label: "Low Risk",
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/30",
    icon: "🟢",
    action: "Routine Appointment",
  },
  L5_SELF_CARE: {
    label: "Self-Care",
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
    icon: "✅",
    action: "Home Care Appropriate",
  },
};
