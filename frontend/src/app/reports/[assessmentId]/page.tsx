"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  ChevronRight,
  ClipboardList,
  Download,
  Heart,
  Info,
  Leaf,
  ListChecks,
  Pill,
  Shield,
  ShieldAlert,
  Stethoscope,
  TrendingUp,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { triageApi } from "@/lib/api";
import { cn, formatDateTime, getTriageLevelLabel } from "@/lib/utils";
import { TRIAGE_LEVEL_CONFIG, type TriageReport, type TriageLevel } from "@/types";

const CARE_PATHWAY_LABELS: Record<string, string> = {
  emergency_services: "Emergency Services (911)",
  emergency_department: "Emergency Department",
  urgent_care: "Urgent Care Center",
  primary_care: "Primary Care Provider",
  telehealth: "Telehealth Consultation",
  home_care: "Home Self-Care",
};

function RiskGauge({ score, label }: { score: number; label: string }) {
  const percent = Math.round(score * 100);
  const color =
    score >= 0.75 ? "bg-red-500" : score >= 0.5 ? "bg-orange-500" : score >= 0.25 ? "bg-yellow-500" : "bg-green-500";

  if (percent < 2) return null;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground capitalize">{label.replace("_", " ")}</span>
        <span className={cn("font-mono font-semibold", percent >= 75 ? "text-red-500" : percent >= 50 ? "text-orange-500" : "text-muted-foreground")}>
          {percent}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
          className={cn("h-full rounded-full", color)}
        />
      </div>
    </div>
  );
}

export default function ReportPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const assessmentId = params.assessmentId as string;
  // Present for anonymous viewers (passed from the triage chat). Authenticated
  // clinic users won't have it and are authorized via their session instead.
  const sessionToken = searchParams.get("token") ?? undefined;

  const [report, setReport] = useState<TriageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [pollAttempts, setPollAttempts] = useState(0);

  useEffect(() => {
    if (!assessmentId) return;
    fetchReport();
  }, [assessmentId]);

  const fetchReport = async () => {
    try {
      const data = await triageApi.getReport(assessmentId, sessionToken);
      setReport(data);
      setLoading(false);
    } catch {
      // Report may not be generated yet — poll up to 10 times
      if (pollAttempts < 10) {
        setTimeout(() => {
          setPollAttempts((p) => p + 1);
          fetchReport();
        }, 2000);
      } else {
        toast.error("Report not available yet. Please try again.");
        setLoading(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 animate-spin items-center justify-center rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Generating your triage report…</p>
          <p className="mt-1 text-xs text-muted-foreground">This may take a moment</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Info className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">Report not found</p>
          <Button className="mt-4" onClick={() => router.push("/")} variant="outline">
            Return Home
          </Button>
        </div>
      </div>
    );
  }

  const levelConfig = TRIAGE_LEVEL_CONFIG[report.urgency_level as TriageLevel];
  const isEmergency = report.urgency_level === "L1_EMERGENCY";
  const isUrgent = report.urgency_level === "L2_URGENT";
  // Null-safe views of optional/array fields so a sparse report can never crash render.
  const clinicalConcerns = report.clinical_concerns ?? [];
  const confidenceBreakdown = report.confidence_breakdown ?? {};
  const urgencyLevelLabel = (report.urgency_level ?? "").replace("_", " ");
  const whatToDoNow = report.what_to_do_now ?? [];
  const medicationGuidance = (report.medication_guidance ?? []).filter(
    (m) => (m?.name || m?.purpose || m?.how_to_take || m?.cautions)
  );
  const selfCareMeasures = report.self_care_measures ?? [];
  const warningSigns = report.warning_signs ?? [];

  return (
    <div className="min-h-screen bg-background">
      {/* Emergency Banner */}
      {(isEmergency || isUrgent) && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "px-6 py-4",
            isEmergency
              ? "bg-red-500 emergency-card"
              : "bg-orange-500"
          )}
        >
          <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 shrink-0 text-white" />
              <div>
                <p className="font-bold text-white">
                  {isEmergency ? "🚨 EMERGENCY — Call 911 Immediately" : "⚠️ Urgent Care Required — Today"}
                </p>
                <p className="text-sm text-white/90">
                  {isEmergency
                    ? "Do not delay. Go to the nearest emergency room or call 911 now."
                    : "Please contact your doctor or go to an urgent care center today."}
                </p>
              </div>
            </div>
            {isEmergency && (
              <a href="tel:911">
                <Button variant="outline" size="sm" className="shrink-0 border-white text-white hover:bg-white hover:text-red-600">
                  📞 Call 911
                </Button>
              </a>
            )}
          </div>
        </motion.div>
      )}

      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Back + actions */}
        <div className="mb-6 flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => router.push("/")}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <div className="flex items-center gap-2">
            {report.report_pdf_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={report.report_pdf_url} download>
                  <Download className="h-4 w-4" />
                  Download PDF
                </a>
              </Button>
            )}
          </div>
        </div>

        {/* Report Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700">
              <Stethoscope className="h-6 w-6 text-white" />
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight">Triage Assessment Report</h1>
                <Badge
                  className={cn(
                    "border text-sm px-3 py-1",
                    levelConfig?.bgColor,
                    levelConfig?.color,
                    levelConfig?.borderColor
                  )}
                >
                  {levelConfig?.icon} {levelConfig?.label}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Generated {formatDateTime(report.generated_at)} · Neural Hub AI Triage System
              </p>
            </div>
          </div>
        </motion.div>

        {/* Recommended Action — PRIMARY CTA */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className={cn(
            "mb-6 rounded-2xl border p-6",
            levelConfig?.bgColor,
            levelConfig?.borderColor
          )}
        >
          <div className="flex items-start gap-4">
            <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg", levelConfig?.bgColor)}>
              {levelConfig?.icon}
            </div>
            <div className="flex-1">
              <p className={cn("mb-1 text-sm font-semibold uppercase tracking-wide", levelConfig?.color)}>
                Recommended Next Step
              </p>
              <p className="text-lg font-bold">{report.recommended_next_step}</p>
              <p className={cn("mt-2 text-sm", levelConfig?.color, "opacity-80")}>
                Care pathway: {CARE_PATHWAY_LABELS[report.care_pathway] || report.care_pathway}
              </p>
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Main column */}
          <div className="space-y-6 lg:col-span-2">
            {/* Patient Summary */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <User className="h-4 w-4 text-primary" />
                    Patient Summary
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {report.patient_summary}
                  </p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Symptoms Summary */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Heart className="h-4 w-4 text-primary" />
                    Symptoms Summary
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {report.symptoms_summary}
                  </p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Risk Assessment */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="h-4 w-4 text-primary" />
                    Risk Assessment
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {report.risk_assessment}
                  </p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Clinical Concerns */}
            {clinicalConcerns.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ClipboardList className="h-4 w-4 text-primary" />
                      Clinical Concerns
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {clinicalConcerns.map((concern, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                          {concern}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* What To Do Now */}
            {whatToDoNow.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.32 }}>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ListChecks className="h-4 w-4 text-primary" />
                      What To Do Now
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ol className="space-y-2.5">
                      {whatToDoNow.map((step, i) => (
                        <li key={i} className="flex items-start gap-3 text-sm text-muted-foreground">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                            {i + 1}
                          </span>
                          <span className="leading-relaxed">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Medication Guidance */}
            {medicationGuidance.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.34 }}>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Pill className="h-4 w-4 text-primary" />
                      Medication Guidance
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {medicationGuidance.map((med, i) => (
                      <div key={i} className="rounded-lg border border-border bg-muted/40 p-3">
                        {med.name && <p className="text-sm font-semibold">{med.name}</p>}
                        {med.purpose && (
                          <p className="mt-0.5 text-sm text-muted-foreground">{med.purpose}</p>
                        )}
                        {med.how_to_take && (
                          <p className="mt-2 text-sm text-muted-foreground">
                            <span className="font-medium text-foreground">How to take: </span>
                            {med.how_to_take}
                          </p>
                        )}
                        {med.cautions && (
                          <p className="mt-1 text-sm text-orange-600 dark:text-orange-400">
                            <span className="font-medium">Caution: </span>
                            {med.cautions}
                          </p>
                        )}
                      </div>
                    ))}
                    <p className="text-xs text-muted-foreground">
                      This is general information, not a prescription. Keep taking your prescribed
                      medications as directed, and confirm any over-the-counter choice with a
                      pharmacist or provider — especially given your allergies and current medications.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Self-Care Measures */}
            {selfCareMeasures.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.36 }}>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Leaf className="h-4 w-4 text-primary" />
                      Self-Care &amp; Comfort Measures
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {selfCareMeasures.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-mint-500" />
                          <span className="leading-relaxed">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Warning Signs */}
            {warningSigns.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.38 }}>
                <Card className="border-red-500/30 bg-red-500/5">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base text-red-600 dark:text-red-400">
                      <ShieldAlert className="h-4 w-4" />
                      Seek Emergency Care If You Experience
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {warningSigns.map((sign, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                          <span className="leading-relaxed">{sign}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Follow-up */}
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <CheckCircle className="h-4 w-4 text-primary" />
                    Follow-Up Recommendation
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {report.followup_recommendation}
                  </p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Escalation Notes */}
            {report.escalation_notes && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
                <Card className="border-orange-500/30 bg-orange-500/5">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base text-orange-600 dark:text-orange-400">
                      <AlertTriangle className="h-4 w-4" />
                      Escalation Notes
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {report.escalation_notes}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-6">
            {/* Urgency */}
            <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Shield className="h-4 w-4 text-primary" />
                    Urgency Level
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className={cn("rounded-lg border p-3 text-center", levelConfig?.bgColor, levelConfig?.borderColor)}>
                    <p className={cn("text-2xl font-bold", levelConfig?.color)}>
                      {urgencyLevelLabel}
                    </p>
                    <p className={cn("text-sm", levelConfig?.color, "opacity-80")}>
                      {levelConfig?.action}
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">{report.urgency_rationale}</p>
                </CardContent>
              </Card>
            </motion.div>

            {/* Confidence breakdown */}
            {Object.keys(confidenceBreakdown).length > 0 && (
              <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <TrendingUp className="h-4 w-4 text-primary" />
                      Risk Scores
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {Object.entries(report.confidence_breakdown).map(([key, score]) => (
                      <RiskGauge
                        key={key}
                        label={key.replace("_risk", "").replace("_", " ")}
                        score={Number(score)}
                      />
                    ))}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-8 rounded-xl border border-border bg-muted/50 p-4"
        >
          <p className="text-center text-xs text-muted-foreground">
            ⚕️ <strong>Important Medical Disclaimer:</strong> This report was generated by an AI
            triage system and is NOT a medical diagnosis. It is for informational purposes only and
            must be evaluated by a licensed healthcare professional. If your condition worsens before
            receiving care, call 911 immediately. Neural Hub AI Triage Nurse · {formatDateTime(report.generated_at)}
          </p>
        </motion.div>
      </div>
    </div>
  );
}
