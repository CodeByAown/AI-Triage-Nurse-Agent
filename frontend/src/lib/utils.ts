import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";
import type { TriageLevel } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), "MMM d, yyyy");
}

export function formatDateTime(date: string | Date): string {
  return format(new Date(date), "MMM d, yyyy 'at' h:mm a");
}

export function formatRelative(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

export function getTriageLevelColor(level: TriageLevel | null): string {
  switch (level) {
    case "L1_EMERGENCY": return "text-red-600 dark:text-red-400";
    case "L2_URGENT": return "text-orange-600 dark:text-orange-400";
    case "L3_MODERATE": return "text-yellow-700 dark:text-yellow-400";
    case "L4_LOW_RISK": return "text-green-600 dark:text-green-400";
    case "L5_SELF_CARE": return "text-blue-600 dark:text-blue-400";
    default: return "text-muted-foreground";
  }
}

export function getTriageBadgeClass(level: TriageLevel | null): string {
  switch (level) {
    case "L1_EMERGENCY": return "triage-l1";
    case "L2_URGENT": return "triage-l2";
    case "L3_MODERATE": return "triage-l3";
    case "L4_LOW_RISK": return "triage-l4";
    case "L5_SELF_CARE": return "triage-l5";
    default: return "bg-muted text-muted-foreground";
  }
}

export function getTriageLevelLabel(level: TriageLevel | null): string {
  switch (level) {
    case "L1_EMERGENCY": return "Emergency";
    case "L2_URGENT": return "Urgent";
    case "L3_MODERATE": return "Moderate";
    case "L4_LOW_RISK": return "Low Risk";
    case "L5_SELF_CARE": return "Self-Care";
    default: return "Unknown";
  }
}

export function getScoreColor(score: number): string {
  if (score >= 0.75) return "text-red-600 dark:text-red-400";
  if (score >= 0.50) return "text-orange-600 dark:text-orange-400";
  if (score >= 0.25) return "text-yellow-600 dark:text-yellow-400";
  return "text-green-600 dark:text-green-400";
}

export function truncate(str: string, n: number): string {
  return str.length > n ? `${str.slice(0, n - 1)}…` : str;
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}
