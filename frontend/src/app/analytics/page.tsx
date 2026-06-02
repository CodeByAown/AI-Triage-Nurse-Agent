"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
} from "recharts";
import { BarChart3 } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { analyticsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function AnalyticsPage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [riskBreakdown, setRiskBreakdown] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      analyticsApi.getDashboard(days),
      analyticsApi.getRiskBreakdown(days),
    ])
      .then(([d, r]) => {
        setDashboard(d);
        setRiskBreakdown(r);
      })
      .finally(() => setLoading(false));
  }, [days]);

  const radarData = riskBreakdown
    ? [
        { subject: "Cardiac", value: Math.round(riskBreakdown.cardiac_avg * 100) },
        { subject: "Stroke", value: Math.round(riskBreakdown.stroke_avg * 100) },
        { subject: "Sepsis", value: Math.round(riskBreakdown.sepsis_avg * 100) },
        { subject: "Respiratory", value: Math.round(riskBreakdown.respiratory_avg * 100) },
        { subject: "Mental Health", value: Math.round(riskBreakdown.mental_health_avg * 100) },
        { subject: "Anaphylaxis", value: Math.round(riskBreakdown.anaphylaxis_avg * 100) },
      ]
    : [];

  const levelBarData = dashboard
    ? Object.entries(dashboard.level_distribution ?? {}).map(([key, count]) => ({
        level: key.replace("_", " "),
        count,
      }))
    : [];

  const LEVEL_COLORS: Record<string, string> = {
    "L1 EMERGENCY": "#ef4444",
    "L2 URGENT": "#f97316",
    "L3 MODERATE": "#eab308",
    "L4 LOW RISK": "#22c55e",
    "L5 SELF CARE": "#3b82f6",
  };

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Detailed analysis of triage patterns and risk distributions
            </p>
          </div>
          <div className="flex items-center gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton h-72 rounded-xl" />
            ))}
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 gap-6 lg:grid-cols-2"
          >
            {/* Daily Volume */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Daily Assessment Volume</CardTitle>
                <CardDescription>
                  Number of triage assessments completed per day over the last {days} days
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dashboard?.daily_trend ?? []}>
                    <XAxis
                      dataKey="date"
                      tickFormatter={(v) => formatDate(v).slice(0, 6)}
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      formatter={(v) => [v, "Assessments"]}
                      labelFormatter={(l) => formatDate(l)}
                    />
                    <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Triage Level Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Triage Level Distribution</CardTitle>
                <CardDescription>Assessments by urgency level</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={levelBarData} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis
                      dataKey="level"
                      type="category"
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      width={90}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar
                      dataKey="count"
                      radius={[0, 4, 4, 0]}
                      fill="#3b82f6"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Risk Radar */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Average Risk Profile</CardTitle>
                <CardDescription>
                  Mean risk scores across all assessed categories (%)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {radarData.every((d) => d.value === 0) ? (
                  <div className="flex h-[220px] items-center justify-center">
                    <div className="text-center">
                      <BarChart3 className="mx-auto mb-2 h-8 w-8 text-muted-foreground/30" />
                      <p className="text-sm text-muted-foreground">No risk data yet</p>
                    </div>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="hsl(var(--border))" />
                      <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                      <Radar
                        dataKey="value"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.2}
                        strokeWidth={2}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                        formatter={(v) => [`${v}%`, "Avg Risk"]}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </AppLayout>
  );
}
