"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  ChevronRight,
  Clock,
  FileText,
  Heart,
  Pill,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { patientsApi, triageApi } from "@/lib/api";
import {
  cn,
  formatDate,
  formatRelative,
  formatDuration,
  initials,
} from "@/lib/utils";
import { TRIAGE_LEVEL_CONFIG, type Assessment, type Patient, type TriageLevel } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  escalated: "Escalated",
  abandoned: "Abandoned",
};

export default function PatientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.patientId as string;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [startingTriage, setStartingTriage] = useState(false);

  useEffect(() => {
    if (!patientId) return;
    Promise.all([
      patientsApi.get(patientId),
      triageApi.listAssessments({ size: 50 }),
    ])
      .then(([p, a]) => {
        setPatient(p);
        // Filter assessments for this patient
        setAssessments(a.items.filter((x) => x.patient_id === patientId));
      })
      .catch(() => {
        toast.error("Failed to load patient");
        router.push("/patients");
      })
      .finally(() => setLoading(false));
  }, [patientId, router]);

  const startTriage = async () => {
    if (!patient) return;
    setStartingTriage(true);
    try {
      const assessment = await triageApi.startSession(patient.id);
      router.push(`/triage/${assessment.session_token}?assessment=${assessment.id}`);
    } catch {
      toast.error("Failed to start triage session");
      setStartingTriage(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6 space-y-4">
          <div className="skeleton h-8 w-48 rounded-lg" />
          <div className="skeleton h-40 rounded-xl" />
          <div className="skeleton h-60 rounded-xl" />
        </div>
      </AppLayout>
    );
  }

  if (!patient) return null;

  const completedAssessments = assessments.filter(
    (a) => a.status === "completed" || a.status === "escalated"
  );
  const hasEmergency = assessments.some((a) => a.triage_level === "L1_EMERGENCY");

  return (
    <AppLayout>
      <div className="p-6">
        {/* Back */}
        <div className="mb-6 flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => router.push("/patients")}>
            <ArrowLeft className="h-4 w-4" />
            Back to Patients
          </Button>
          <Button variant="brand" size="sm" loading={startingTriage} onClick={startTriage}>
            <Activity className="h-4 w-4" />
            Start New Triage
          </Button>
        </div>

        {/* Patient Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <Card className={cn(hasEmergency && "border-red-500/30 bg-red-500/5")}>
            <CardContent className="p-6">
              <div className="flex items-start gap-5">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-xl font-bold text-primary">
                  {initials(patient.full_name)}
                </div>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <h1 className="text-2xl font-bold tracking-tight">{patient.full_name}</h1>
                    {hasEmergency && (
                      <Badge className="border-red-500/30 bg-red-500/15 text-red-600 dark:text-red-400">
                        <AlertTriangle className="mr-1 h-3 w-3" />
                        Emergency History
                      </Badge>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-4 text-sm text-muted-foreground">
                    {patient.age && (
                      <span className="flex items-center gap-1">
                        <User className="h-3.5 w-3.5" />
                        {patient.age} years old
                      </span>
                    )}
                    {patient.biological_sex && (
                      <span className="capitalize">{patient.biological_sex}</span>
                    )}
                    {patient.date_of_birth && (
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        DOB: {formatDate(patient.date_of_birth)}
                      </span>
                    )}
                    {patient.email && <span>{patient.email}</span>}
                    {patient.phone && <span>{patient.phone}</span>}
                    {patient.mrn && <span className="font-mono text-xs">MRN: {patient.mrn}</span>}
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-muted-foreground">
                  <p>Patient since</p>
                  <p className="font-medium">{formatDate(patient.created_at)}</p>
                  <p className="mt-1">{completedAssessments.length} assessment{completedAssessments.length !== 1 ? "s" : ""}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Left col — clinical info */}
          <div className="space-y-5 lg:col-span-1">
            {/* Conditions */}
            <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Heart className="h-4 w-4 text-red-500" />
                    Chronic Conditions
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(patient.chronic_conditions as string[]).length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {(patient.chronic_conditions as string[]).map((c) => (
                        <Badge key={c} variant="secondary" className="text-xs">
                          {c}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">None recorded</p>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            {/* Medications */}
            <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Pill className="h-4 w-4 text-blue-500" />
                    Current Medications
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(patient.current_medications as Array<{ name?: string; dosage?: string } | string>).length > 0 ? (
                    <ul className="space-y-1">
                      {(patient.current_medications as Array<{ name?: string; dosage?: string } | string>).map((med, i) => (
                        <li key={i} className="text-sm text-muted-foreground">
                          {typeof med === "string" ? med : `${med.name}${med.dosage ? ` — ${med.dosage}` : ""}`}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">None recorded</p>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            {/* Allergies */}
            <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <AlertTriangle className="h-4 w-4 text-orange-500" />
                    Allergies
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {patient.allergies.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {patient.allergies.map((a) => (
                        <Badge key={a as string} className="border-orange-500/30 bg-orange-500/10 text-orange-600 dark:text-orange-400 text-xs">
                          {a as string}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">None recorded</p>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {/* Right col — assessments */}
          <div className="lg:col-span-2">
            <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <CardTitle className="text-base">Assessment History</CardTitle>
                  <span className="text-xs text-muted-foreground">{assessments.length} total</span>
                </CardHeader>
                <CardContent className="p-0">
                  {assessments.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10">
                      <FileText className="mb-3 h-8 w-8 text-muted-foreground/30" />
                      <p className="text-sm text-muted-foreground">No assessments yet</p>
                      <Button size="sm" variant="brand" className="mt-3" onClick={startTriage}>
                        <Activity className="h-4 w-4" />
                        Start First Triage
                      </Button>
                    </div>
                  ) : (
                    <div className="divide-y divide-border">
                      {assessments.map((assessment) => {
                        const levelConfig = assessment.triage_level
                          ? TRIAGE_LEVEL_CONFIG[assessment.triage_level as TriageLevel]
                          : null;
                        const canView = assessment.status === "completed" || assessment.status === "escalated";

                        return (
                          <div key={assessment.id} className="flex items-center gap-4 px-6 py-4">
                            <div
                              className={cn(
                                "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm",
                                levelConfig?.bgColor || "bg-muted"
                              )}
                            >
                              {levelConfig?.icon ?? <Activity className="h-4 w-4 text-muted-foreground" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                {levelConfig ? (
                                  <span className={cn("text-sm font-medium", levelConfig.color)}>
                                    {levelConfig.label}
                                  </span>
                                ) : (
                                  <span className="text-sm text-muted-foreground">No level</span>
                                )}
                                <Badge variant="outline" className="text-[10px]">
                                  {STATUS_LABELS[assessment.status] ?? assessment.status}
                                </Badge>
                              </div>
                              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                {assessment.chief_complaint || "No complaint recorded"}
                              </p>
                              <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatRelative(assessment.created_at)}
                                </span>
                                {assessment.completed_at && (
                                  <span>
                                    ·{" "}
                                    {formatDuration(
                                      Math.round(
                                        (new Date(assessment.completed_at).getTime() -
                                          new Date(assessment.started_at).getTime()) /
                                          1000
                                      )
                                    )}
                                  </span>
                                )}
                              </div>
                            </div>
                            {canView ? (
                              <Link
                                href={`/reports/${assessment.id}`}
                                className="flex shrink-0 items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
                              >
                                <FileText className="h-3.5 w-3.5" />
                                Report
                                <ChevronRight className="h-3.5 w-3.5" />
                              </Link>
                            ) : (
                              <span className="shrink-0 text-xs text-muted-foreground">
                                {assessment.status === "in_progress" ? "Live…" : "—"}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
