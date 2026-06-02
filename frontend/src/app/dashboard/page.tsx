"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Clock,
  Shield,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { analyticsApi, getErrorMessage } from "@/lib/api";
import { cn, formatDuration, formatDate } from "@/lib/utils";
import type { DashboardStats } from "@/types";

const LEVEL_COLORS: Record<string, string> = {
  L1_EMERGENCY: "#ef4444",
  L2_URGENT: "#f97316",
  L3_MODERATE: "#eab308",
  L4_LOW_RISK: "#22c55e",
  L5_SELF_CARE: "#3b82f6",
};

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = "text-primary",
  bg = "bg-primary/10",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: number;
  color?: string;
  bg?: string;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>
            {subtitle && <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", bg)}>
            <Icon className={cn("h-5 w-5", color)} />
          </div>
        </div>
        {trend !== undefined && (
          <div className="mt-3 flex items-center gap-1 text-xs">
            <TrendingUp className="h-3.5 w-3.5 text-green-500" />
            <span className="text-green-600 dark:text-green-400">{trend}% from last period</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    analyticsApi
      .getDashboard(days)
      .then(setStats)
      .catch((err) => toast.error(getErrorMessage(err, "Couldn't load dashboard analytics")))
      .finally(() => setLoading(false));
  }, [days]);

  const pieData = stats
    ? Object.entries(stats.level_distribution).map(([key, value]) => ({
        name: key.replace("_", " ").replace("_", " "),
        value,
        color: LEVEL_COLORS[key] || "#888",
      }))
    : [];

  return (
    <AppLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Overview of triage activity and patient assessments
            </p>
          </div>
          <div className="flex items-center gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="skeleton h-32 rounded-xl" />
            ))}
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* Stat cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="Total Assessments"
                value={stats?.total_assessments ?? 0}
                subtitle={`Last ${days} days`}
                icon={Activity}
              />
              <StatCard
                title="Emergency Cases"
                value={stats?.emergency_cases ?? 0}
                subtitle="L1 Emergency"
                icon={AlertTriangle}
                color="text-red-500"
                bg="bg-red-500/10"
              />
              <StatCard
                title="High Risk Rate"
                value={`${stats?.high_risk_rate ?? 0}%`}
                subtitle="L1 + L2 combined"
                icon={Shield}
                color="text-orange-500"
                bg="bg-orange-500/10"
              />
              <StatCard
                title="Avg Triage Time"
                value={formatDuration(stats?.avg_triage_time_seconds ?? 0)}
                subtitle="From start to report"
                icon={Clock}
                color="text-brand-500"
                bg="bg-brand-500/10"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="Completed"
                value={stats?.completed_assessments ?? 0}
                subtitle={`${stats?.completion_rate ?? 0}% completion rate`}
                icon={CheckCircle}
                color="text-green-500"
                bg="bg-green-500/10"
              />
              <StatCard
                title="Escalated"
                value={stats?.escalated_assessments ?? 0}
                subtitle="Required emergency escalation"
                icon={Zap}
                color="text-red-500"
                bg="bg-red-500/10"
              />
              <StatCard
                title="Urgent Cases"
                value={stats?.urgent_cases ?? 0}
                subtitle="L2 Urgent"
                icon={TrendingUp}
                color="text-orange-500"
                bg="bg-orange-500/10"
              />
              <StatCard
                title="High Risk Cases"
                value={stats?.high_risk_cases ?? 0}
                subtitle="Emergency + Urgent"
                icon={Users}
                color="text-purple-500"
                bg="bg-purple-500/10"
              />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Daily trend */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base">Assessment Volume</CardTitle>
                  <CardDescription>Daily triage assessments over the selected period</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={stats?.daily_trend ?? []}>
                      <defs>
                        <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b5a44" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#3b5a44" stopOpacity={0} />
                        </linearGradient>
                      </defs>
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
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#3b5a44"
                        strokeWidth={2}
                        fill="url(#gradient)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Triage distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Triage Distribution</CardTitle>
                  <CardDescription>Breakdown by urgency level</CardDescription>
                </CardHeader>
                <CardContent>
                  {pieData.length > 0 ? (
                    <>
                      <ResponsiveContainer width="100%" height={140}>
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={65}
                            dataKey="value"
                            strokeWidth={0}
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={index} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "8px",
                              fontSize: "12px",
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="mt-3 space-y-2">
                        {pieData.map((item) => (
                          <div key={item.name} className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: item.color }}
                              />
                              <span className="text-muted-foreground capitalize">{item.name}</span>
                            </div>
                            <span className="font-medium">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      <div className="text-center">
                        <BarChart3 className="mx-auto mb-2 h-8 w-8 opacity-30" />
                        <p>No assessment data yet</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}
      </div>
    </AppLayout>
  );
}
