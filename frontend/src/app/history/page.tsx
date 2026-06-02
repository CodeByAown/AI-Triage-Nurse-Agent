"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Activity, AlertTriangle, ChevronRight, Clock, FileText, Search } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { triageApi } from "@/lib/api";
import {
  cn,
  formatRelative,
  formatDuration,
  getTriageBadgeClass,
  getTriageLevelLabel,
} from "@/lib/utils";
import { TRIAGE_LEVEL_CONFIG, type Assessment, type TriageLevel } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  pending: "text-muted-foreground",
  in_progress: "text-blue-500",
  completed: "text-green-600 dark:text-green-400",
  escalated: "text-red-600 dark:text-red-400",
  abandoned: "text-muted-foreground",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  escalated: "Escalated",
  abandoned: "Abandoned",
};

const STATUS_FILTERS = ["all", "completed", "escalated", "in_progress", "pending"];

export default function HistoryPage() {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchAssessments = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, size: 20 };
      if (statusFilter !== "all") params.status = statusFilter;

      const data = await triageApi.listAssessments(params as { page: number; size: number; status?: string });
      setAssessments(data.items);
      setTotalPages(data.pages);
      setTotal(data.total);
    } catch {
      // silently fail — user sees empty state
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments]);

  const filtered = search
    ? assessments.filter(
        (a) =>
          a.chief_complaint?.toLowerCase().includes(search.toLowerCase()) ||
          a.triage_level?.toLowerCase().includes(search.toLowerCase()) ||
          a.status.toLowerCase().includes(search.toLowerCase())
      )
    : assessments;

  return (
    <AppLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Assessment History</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {total} total assessments · click any row to view the report
            </p>
          </div>
          <Button variant="brand" size="sm" asChild>
            <Link href="/triage/start">
              <Activity className="h-4 w-4" />
              New Triage
            </Link>
          </Button>
        </div>

        {/* Filters */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search by complaint or triage level…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-1">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s); setPage(1); }}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                  statusFilter === s
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                {s === "all" ? "All" : STATUS_LABELS[s] ?? s}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton h-20 rounded-xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16">
            <FileText className="mb-3 h-10 w-10 text-muted-foreground/40" />
            <p className="font-medium text-muted-foreground">No assessments found</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Complete a triage session to see it here
            </p>
            <Button className="mt-4" asChild variant="brand" size="sm">
              <Link href="/triage/start">Start Triage</Link>
            </Button>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-2"
          >
            {filtered.map((assessment, i) => {
              const levelConfig = assessment.triage_level
                ? TRIAGE_LEVEL_CONFIG[assessment.triage_level as TriageLevel]
                : null;
              const canViewReport =
                assessment.status === "completed" || assessment.status === "escalated";
              const isEmergency = assessment.triage_level === "L1_EMERGENCY";

              return (
                <motion.div
                  key={assessment.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Card
                    className={cn(
                      "transition-all",
                      canViewReport && "cursor-pointer hover:border-primary/40 hover:shadow-md",
                      isEmergency && "border-red-500/30 bg-red-500/5"
                    )}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        {/* Triage level icon */}
                        <div
                          className={cn(
                            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-base",
                            levelConfig?.bgColor || "bg-muted"
                          )}
                        >
                          {levelConfig?.icon ?? <Activity className="h-4 w-4 text-muted-foreground" />}
                        </div>

                        {/* Main content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            {levelConfig ? (
                              <span className={cn("text-sm font-semibold", levelConfig.color)}>
                                {levelConfig.label}
                              </span>
                            ) : (
                              <span className="text-sm font-medium text-muted-foreground">No level assigned</span>
                            )}
                            <Badge
                              variant="outline"
                              className={cn("text-[10px]", STATUS_COLORS[assessment.status])}
                            >
                              {STATUS_LABELS[assessment.status] ?? assessment.status}
                            </Badge>
                            {isEmergency && (
                              <Badge className="bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] border-red-500/30 animate-pulse">
                                <AlertTriangle className="mr-1 h-3 w-3" />
                                Emergency
                              </Badge>
                            )}
                          </div>
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {assessment.chief_complaint || "No chief complaint recorded"}
                          </p>
                          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatRelative(assessment.created_at)}
                            </span>
                            {assessment.completed_at && (
                              <span>
                                Duration:{" "}
                                {formatDuration(
                                  Math.round(
                                    (new Date(assessment.completed_at).getTime() -
                                      new Date(assessment.started_at).getTime()) /
                                      1000
                                  )
                                )}
                              </span>
                            )}
                            {assessment.confidence_score != null && (
                              <span>
                                Confidence: {Math.round(assessment.confidence_score * 100)}%
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Action */}
                        <div className="shrink-0">
                          {canViewReport ? (
                            <Link
                              href={`/reports/${assessment.id}`}
                              className="flex items-center gap-1 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
                            >
                              <FileText className="h-3.5 w-3.5" />
                              View Report
                              <ChevronRight className="h-3.5 w-3.5" />
                            </Link>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              {assessment.status === "in_progress" ? "In progress…" : "No report"}
                            </span>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
