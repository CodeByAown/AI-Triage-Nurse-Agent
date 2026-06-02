"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ClipboardList, RefreshCw } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { adminApi } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";

interface AuditLogEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  user_id: string | null;
  ip_address: string | null;
  status: string;
  created_at: string;
  metadata: Record<string, any>;
}

const ACTION_COLORS: Record<string, string> = {
  login: "bg-green-500/10 text-green-600 dark:text-green-400",
  register: "bg-brand-500/10 text-brand-600 dark:text-brand-400",
  triage_started: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  triage_completed: "bg-mint-500/10 text-mint-600 dark:text-mint-400",
  emergency_escalated: "bg-red-500/10 text-red-600 dark:text-red-400",
  user_deactivated: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
};

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getAuditLogs({ page, size: 50 });
      setLogs(data.items);
      setTotalPages(data.pages || 1);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLogs(); }, [page]);

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardList className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Audit Logs</h1>
              <p className="text-sm text-muted-foreground">
                Complete audit trail of all system actions
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={fetchLogs}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="skeleton h-12 rounded-lg" />
                ))}
              </div>
            ) : logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16">
                <ClipboardList className="mb-3 h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No audit logs found</p>
              </div>
            ) : (
              <div>
                {/* Table header */}
                <div className="grid grid-cols-[1fr_1fr_120px_120px_160px] gap-4 border-b border-border bg-muted/50 px-6 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <span>Action</span>
                  <span>Resource</span>
                  <span>Status</span>
                  <span>IP Address</span>
                  <span>Timestamp</span>
                </div>
                <div className="divide-y divide-border">
                  {logs.map((log, i) => (
                    <motion.div
                      key={log.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.02 }}
                      className="grid grid-cols-[1fr_1fr_120px_120px_160px] items-center gap-4 px-6 py-3 text-sm hover:bg-muted/30"
                    >
                      <div>
                        <Badge
                          className={cn(
                            "text-[10px]",
                            ACTION_COLORS[log.action] || "bg-muted text-muted-foreground"
                          )}
                        >
                          {log.action.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">{log.resource_type}</span>
                        {log.resource_id && (
                          <span className="ml-2 font-mono text-xs text-muted-foreground/60">
                            {log.resource_id.slice(0, 8)}…
                          </span>
                        )}
                      </div>
                      <div>
                        <Badge
                          variant={log.status === "success" ? "success" : "destructive"}
                          className="text-[10px]"
                        >
                          {log.status}
                        </Badge>
                      </div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {log.ip_address || "—"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatDateTime(log.created_at)}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
