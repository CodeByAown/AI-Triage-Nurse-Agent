"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  CalendarClock,
  FileText,
  HeartPulse,
  Pill,
  ShieldAlert,
  Stethoscope,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Logo, LogoMark } from "@/components/ui/logo";
import {
  authApi,
  getErrorMessage,
  loadStoredToken,
  patientApi,
  triageApi,
  type PatientDashboard,
  type PatientFact,
} from "@/lib/api";

const LEVEL_TONE: Record<string, string> = {
  L1_EMERGENCY: "bg-red-500/15 text-red-600 dark:text-red-400",
  L2_URGENT: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
  L3_MODERATE: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  L4_LOW_RISK: "bg-green-500/15 text-green-600 dark:text-green-400",
  L5_SELF_CARE: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

function groupFacts(facts: PatientFact[]) {
  const byCat: Record<string, PatientFact[]> = {};
  for (const f of facts) (byCat[f.category] ??= []).push(f);
  return byCat;
}

export default function PatientDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<PatientDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    loadStoredToken();
    const token =
      typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (!token) {
      router.replace("/auth/signin");
      return;
    }
    (async () => {
      const me = await authApi.me().catch(() => null);
      if (!me) {
        router.replace("/auth/signin");
        return;
      }
      if (me.role !== "patient") {
        router.replace("/dashboard");
        return;
      }
      try {
        setData(await patientApi.mySummary());
      } catch (err) {
        toast.error(getErrorMessage(err, "Couldn't load your health summary."));
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  const startNew = async () => {
    setStarting(true);
    try {
      const { session_token, assessment_id } = await triageApi.startAnonymousSession();
      router.push(`/triage/${session_token}?assessment=${assessment_id}`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Couldn't start a new assessment."));
      setStarting(false);
    }
  };

  const firstName = data?.patient?.first_name?.trim() || "there";

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Activity className="h-5 w-5 animate-pulse text-brand-500" />
          Loading your health summary…
        </div>
      </div>
    );
  }

  const facts = data?.facts ?? [];
  const grouped = groupFacts(facts);
  const conditions = grouped["condition"] ?? [];
  const medications = grouped["medication"] ?? [];
  const allergies = grouped["allergy"] ?? [];
  const labs = grouped["lab"] ?? [];
  const assessments = data?.assessments ?? [];
  const documents = data?.documents ?? [];
  const openActions = data?.open_actions ?? [];

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
          <a
            href="https://neuralhub.us"
            target="_blank"
            rel="noopener noreferrer"
            className="flex shrink-0 items-center gap-2.5"
            aria-label="Neural Hub"
          >
            <LogoMark className="h-7 w-7 sm:hidden" />
            <Logo className="hidden h-5 w-auto sm:block" />
          </a>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await authApi.logout().catch(() => null);
              if (typeof window !== "undefined") {
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
              }
              router.replace("/");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* Welcome + primary action */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 flex flex-col gap-4 rounded-2xl border border-border bg-gradient-to-br from-sage-100/60 to-card p-6 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Welcome back, {firstName}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Maya remembers your history. Start a new check-in or continue where you left off.
            </p>
          </div>
          <Button onClick={startNew} loading={starting} variant="brand" size="lg" className="shrink-0">
            <Stethoscope className="h-5 w-5" />
            New assessment with Maya
            <ArrowRight className="h-4 w-4" />
          </Button>
        </motion.div>

        {/* Follow-ups */}
        {openActions.length > 0 && (
          <Card className="mb-6 border-brand-500/30">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarClock className="h-4 w-4 text-brand-500" />
                Follow-up recommendations
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {openActions.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-3 text-sm">
                  <span>{a.description}</span>
                  {a.due_at && (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      due {fmtDate(a.due_at)}
                    </span>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          {/* Medical history */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <HeartPulse className="h-4 w-4 text-brand-500" />
                Medical history
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {facts.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Nothing recorded yet. As you talk with Maya, she&apos;ll remember your
                  conditions, medications, and allergies here.
                </p>
              )}
              {conditions.length > 0 && (
                <FactGroup icon={<HeartPulse className="h-3.5 w-3.5" />} title="Conditions" facts={conditions} />
              )}
              {medications.length > 0 && (
                <FactGroup icon={<Pill className="h-3.5 w-3.5" />} title="Medications" facts={medications} />
              )}
              {allergies.length > 0 && (
                <FactGroup
                  icon={<ShieldAlert className="h-3.5 w-3.5" />}
                  title="Allergies"
                  facts={allergies}
                  tone="text-red-600 dark:text-red-400"
                />
              )}
              {labs.length > 0 && (
                <FactGroup icon={<Activity className="h-3.5 w-3.5" />} title="Recent labs" facts={labs} />
              )}
            </CardContent>
          </Card>

          {/* Uploaded reports */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText className="h-4 w-4 text-brand-500" />
                Uploaded reports
              </CardTitle>
            </CardHeader>
            <CardContent>
              {documents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No documents yet. You can upload lab reports or records during a chat with
                  Maya and she&apos;ll read them.
                </p>
              ) : (
                <ul className="space-y-2">
                  {documents.map((d) => (
                    <li key={d.id} className="flex items-center justify-between gap-3 text-sm">
                      <span className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{d.original_filename}</span>
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {fmtDate(d.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Previous assessments */}
        <Card className="mt-6">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Stethoscope className="h-4 w-4 text-brand-500" />
              Previous assessments
            </CardTitle>
          </CardHeader>
          <CardContent>
            {assessments.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                You haven&apos;t completed an assessment yet.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {assessments.map((a) => {
                  const inProgress = a.status === "in_progress";
                  return (
                    <li key={a.id} className="flex items-center justify-between gap-3 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {a.chief_complaint || "Triage assessment"}
                        </p>
                        <p className="text-xs text-muted-foreground">{fmtDate(a.created_at)}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {a.triage_level && (
                          <Badge
                            className={LEVEL_TONE[a.triage_level] ?? "bg-muted text-foreground"}
                          >
                            {a.triage_level.replace("L", "L").replace("_", " ")}
                          </Badge>
                        )}
                        <Button asChild variant="ghost" size="sm">
                          <Link href={`/triage/${a.session_token}?assessment=${a.id}`}>
                            {inProgress ? "Continue" : "View"}
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <p className="mt-8 text-center text-xs text-muted-foreground">
          ⚕️ Maya provides triage guidance, not a diagnosis. In an emergency, call 911.
        </p>
      </main>
    </div>
  );
}

function FactGroup({
  icon,
  title,
  facts,
  tone,
}: {
  icon: React.ReactNode;
  title: string;
  facts: PatientFact[];
  tone?: string;
}) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {facts.map((f) => (
          <span
            key={f.id}
            className={`rounded-md bg-muted px-2 py-1 text-sm ${tone ?? ""}`}
          >
            {f.label}
            {f.value ? `: ${f.value}${f.unit ? ` ${f.unit}` : ""}` : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
