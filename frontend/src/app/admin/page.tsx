"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ClipboardList, Shield, UserCheck, Users } from "lucide-react";
import { toast } from "sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, authApi, getErrorMessage } from "@/lib/api";
import { cn, formatRelative, initials } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { User, UserRole } from "@/types";

const ROLE_COLORS: Record<UserRole, string> = {
  super_admin: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  admin: "bg-brand-500/10 text-brand-600 dark:text-brand-400",
  provider: "bg-green-500/10 text-green-600 dark:text-green-400",
  patient: "bg-muted text-muted-foreground",
  viewer: "bg-muted text-muted-foreground",
};

export default function AdminPage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Gate the page on an admin role before rendering anything sensitive.
  // The backend still enforces this; this just avoids a broken/empty panel
  // for users who shouldn't be here.
  useEffect(() => {
    authApi
      .me()
      .then((me) => {
        if (me.role === "admin" || me.role === "super_admin") {
          setAuthorized(true);
        } else {
          toast.error("You don't have permission to access the admin panel.");
          router.replace("/dashboard");
        }
      })
      .catch(() => router.replace("/auth/signin"));
  }, [router]);

  useEffect(() => {
    if (!authorized) return;
    adminApi.getOverview().then(setOverview).catch(() => {});
  }, [authorized]);

  useEffect(() => {
    if (!authorized) return;
    setLoading(true);
    const timer = setTimeout(() => {
      adminApi
        .listUsers({ page, size: 20, search: search || undefined })
        .then((data) => {
          setUsers(data.items ?? []);
          setTotalPages(data.pages || 1);
        })
        .catch((err) => {
          setUsers([]);
          toast.error(getErrorMessage(err, "Failed to load users"));
        })
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [authorized, page, search]);

  const updateRole = async (userId: string, role: string) => {
    try {
      await adminApi.updateUserRole(userId, role);
      toast.success("Role updated");
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: role as UserRole } : u))
      );
    } catch {
      toast.error("Failed to update role");
    }
  };

  const deactivateUser = async (userId: string) => {
    if (!confirm("Are you sure you want to deactivate this user?")) return;
    try {
      await adminApi.deactivateUser(userId);
      toast.success("User deactivated");
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u))
      );
    } catch {
      toast.error("Failed to deactivate user");
    }
  };

  if (!authorized) {
    return (
      <AppLayout>
        <div className="space-y-2 p-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-lg" />
          ))}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Shield className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Admin Panel</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage users, roles, and organization settings
          </p>
        </div>

        {/* Overview Cards */}
        {overview && (
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card>
              <CardContent className="flex items-center gap-4 p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                  <Users className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{overview.total_users}</p>
                  <p className="text-xs text-muted-foreground">Total users</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-4 p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-500/10">
                  <ClipboardList className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{overview.total_assessments}</p>
                  <p className="text-xs text-muted-foreground">Total assessments</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* User Management */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <CardTitle className="text-base">User Management</CardTitle>
            <div className="w-64">
              <Input
                placeholder="Search users…"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="h-8 text-sm"
              />
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="skeleton h-14 rounded-lg" />
                ))}
              </div>
            ) : (
              <div className="divide-y divide-border">
                {users.map((user, i) => (
                  <motion.div
                    key={user.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="flex items-center justify-between gap-4 px-6 py-4"
                  >
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className="bg-primary/10 text-primary text-xs">
                          {initials(user.full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">{user.full_name}</p>
                        <p className="text-xs text-muted-foreground">{user.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge className={cn("text-[10px]", ROLE_COLORS[user.role])}>
                        {user.role.replace("_", " ")}
                      </Badge>
                      {!user.is_active && (
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          Inactive
                        </Badge>
                      )}
                      <div className="flex items-center gap-1">
                        <select
                          value={user.role}
                          onChange={(e) => updateRole(user.id, e.target.value)}
                          className="h-7 rounded border border-input bg-background px-2 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                        >
                          {["patient", "viewer", "provider", "admin"].map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                        {user.is_active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-[11px] text-destructive hover:bg-destructive/10"
                            onClick={() => deactivateUser(user.id)}
                          >
                            Deactivate
                          </Button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
