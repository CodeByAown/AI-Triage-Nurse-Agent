"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  ClipboardList,
  History,
  Home,
  LogOut,
  Settings,
  Shield,
  Stethoscope,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { initials } from "@/lib/utils";
import { authApi } from "@/lib/api";
import type { User } from "@/types";

interface SidebarProps {
  user: User | null;
  onSignOut: () => void;
}

type NavItem = { href: Route; label: string; icon: LucideIcon };

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/triage/start", label: "New Triage", icon: Activity },
  { href: "/history", label: "History", icon: History },
  { href: "/patients", label: "Patients", icon: Users },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const adminItems: NavItem[] = [
  { href: "/admin", label: "Admin", icon: Shield },
  { href: "/admin/audit-logs", label: "Audit Logs", icon: ClipboardList },
];

export function Sidebar({ user, onSignOut }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const handleSignOut = async () => {
    await authApi.logout().catch(() => {}); // fire-and-forget
    onSignOut();
  };

  const isActive = (href: string) =>
    pathname === href || (href !== "/dashboard" && pathname.startsWith(href));

  return (
    <div className="flex h-full w-64 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 shadow-sm">
          <Stethoscope className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight">Neural Hub</p>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Triage Nurse
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-1">
          {navItems.map((item) => {
            const active = isActive(item.href);
            return (
              <Link key={item.href} href={item.href}>
                <motion.div
                  whileHover={{ x: 2 }}
                  className={cn(
                    "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )}
                >
                  <item.icon
                    className={cn(
                      "h-4 w-4 transition-colors",
                      active ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                    )}
                  />
                  {item.label}
                  {active && (
                    <motion.div
                      layoutId="activeIndicator"
                      className="ml-auto h-1.5 w-1.5 rounded-full bg-primary"
                    />
                  )}
                </motion.div>
              </Link>
            );
          })}
        </div>

        {/* Admin section */}
        {user?.role && ["admin", "super_admin"].includes(user.role) && (
          <div className="mt-6">
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Administration
            </p>
            <div className="space-y-1">
              {adminItems.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link key={item.href} href={item.href}>
                    <motion.div
                      whileHover={{ x: 2 }}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
                        active
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground"
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </motion.div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </nav>

      {/* User footer */}
      <div className="border-t border-border p-3">
        <Link href="/settings">
          <div className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-accent">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="bg-primary/10 text-primary text-[10px]">
                {user ? initials(user.full_name) : "?"}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 overflow-hidden">
              <p className="truncate text-xs font-medium">{user?.full_name ?? "Loading…"}</p>
              <p className="truncate text-[10px] text-muted-foreground">{user?.email}</p>
            </div>
            <Settings className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </Link>
        <button
          onClick={handleSignOut}
          className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </div>
  );
}
