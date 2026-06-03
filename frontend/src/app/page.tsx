"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  CheckCircle,
  Clock,
  Lock,
  Shield,
  TrendingUp,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Logo, LogoMark } from "@/components/ui/logo";
import { authApi, loadStoredToken } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { User } from "@/types";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

const staggerContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const FEATURES = [
  {
    icon: Brain,
    title: "Adaptive AI Questioning",
    description:
      "Adaptive AI conversations that respond to symptoms, age, sex, history, and risk factors — just like speaking to a real nurse.",
    color: "text-brand-500",
    bg: "bg-brand-500/10",
  },
  {
    icon: AlertTriangle,
    title: "Real-Time Risk Detection",
    description:
      "Pattern-matching engine detects cardiac, stroke, sepsis, and mental health emergencies in real time and escalates immediately.",
    color: "text-red-500",
    bg: "bg-red-500/10",
  },
  {
    icon: Activity,
    title: "5-Level Triage System",
    description:
      "Clinical triage from L1 Emergency to L5 Self-Care with urgency scores, confidence levels, and care pathway recommendations.",
    color: "text-mint-500",
    bg: "bg-mint-500/10",
  },
  {
    icon: Shield,
    title: "Clinical-Grade Reports",
    description:
      "Structured triage reports ready for healthcare providers: patient summary, risk assessment, clinical concerns, and escalation notes.",
    color: "text-purple-500",
    bg: "bg-purple-500/10",
  },
  {
    icon: TrendingUp,
    title: "Analytics Dashboard",
    description:
      "Real-time visibility into assessment volumes, risk distributions, triage trends, and average response times.",
    color: "text-orange-500",
    bg: "bg-orange-500/10",
  },
  {
    icon: Lock,
    title: "HIPAA-Ready",
    description:
      "Audit logs, role-based access, encrypted storage. Built for deployment in healthcare environments from day one.",
    color: "text-yellow-500",
    bg: "bg-yellow-500/10",
  },
];

const TRIAGE_LEVELS = [
  { level: "L1", label: "Emergency", color: "bg-red-500", action: "Call 911 / ED Now", example: "Chest pain, stroke, severe bleeding" },
  { level: "L2", label: "Urgent", color: "bg-orange-500", action: "Same-Day Visit", example: "High fever, severe infection" },
  { level: "L3", label: "Moderate", color: "bg-yellow-500", action: "24–72 Hours", example: "Worsening symptoms, UTI" },
  { level: "L4", label: "Low Risk", color: "bg-green-500", action: "Routine Appt", example: "Minor illness, mild pain" },
  { level: "L5", label: "Self-Care", color: "bg-blue-500", action: "Home Care", example: "Cold, mild GI symptoms" },
];

const STATS = [
  { value: "< 8 min", label: "Average triage time" },
  { value: "99.2%", label: "Emergency detection rate" },
  { value: "5 levels", label: "Clinical triage pathways" },
  { value: "24/7", label: "Always available" },
];

export default function LandingPage() {
  // Reflect the real auth state in the nav so a signed-in user never sees
  // "Sign in" on the homepage.
  const [user, setUser] = useState<User | null>(null);
  // Optimistically treat a stored token as authenticated so a logged-in user
  // never flashes "Sign in" while the soft check resolves.
  const [hasToken, setHasToken] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    loadStoredToken();
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    setHasToken(!!token);
    if (token) {
      authApi
        .meSoft()
        .then((u) => {
          setUser(u);
          setHasToken(true);
        })
        .catch(() => {
          // Token is invalid/expired and couldn't be refreshed → truly signed out.
          setUser(null);
          setHasToken(false);
        });
    }
  }, []);

  const isAuthenticated = !!user || hasToken;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header
        className={cn(
          "sticky top-0 z-50 border-b backdrop-blur-md transition-all duration-200",
          scrolled
            ? "border-border/70 bg-background/90 shadow-sm"
            : "border-transparent bg-background/70"
        )}
      >
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <a
            href="https://neuralhub.us"
            target="_blank"
            rel="noopener noreferrer"
            className="flex shrink-0 items-center gap-2.5"
            aria-label="Neural Hub — neuralhub.us"
          >
            <LogoMark className="h-7 w-7 sm:hidden" />
            <Logo className="hidden h-5 w-auto sm:block" />
          </a>
          <nav className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex">
            <a href="#triage" className="transition-colors hover:text-foreground">Triage Levels</a>
            <a href="#features" className="transition-colors hover:text-foreground">Features</a>
            <a href="#how-it-works" className="transition-colors hover:text-foreground">How It Works</a>
          </nav>
          <div className="flex shrink-0 items-center gap-2">
            {isAuthenticated ? (
              <Button size="sm" variant="brand" asChild>
                <Link href={user?.role === "patient" ? "/patient" : "/dashboard"}>
                  Go to Dashboard
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/auth/signin">Sign in</Link>
                </Button>
                <Button size="sm" variant="brand" asChild>
                  <Link href="/triage/start">
                    Start Triage
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Background grid */}
        <div className="absolute inset-0 bg-grid-pattern opacity-100" />
        <div className="absolute inset-0 bg-gradient-to-b from-sage-100/70 via-background/40 to-background" />
        <div className="absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-terracotta-500/10 blur-3xl" />

        <div className="relative mx-auto max-w-7xl px-6 pt-24 pb-32 text-center">
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="mx-auto max-w-4xl"
          >
            <motion.h1
              variants={fadeUp}
              className="mb-6 text-5xl font-bold leading-tight tracking-tight text-foreground sm:text-6xl lg:text-7xl"
            >
              AI Triage Nurse for{" "}
              <span className="gradient-text">Modern Healthcare</span>
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground"
            >
              Intelligent patient triage that adapts to every symptom, identifies emergencies
              in real time, and routes patients to the right level of care — before they speak
              to a provider.
            </motion.p>

            <motion.div
              variants={fadeUp}
              className="flex flex-col items-center justify-center gap-4 sm:flex-row"
            >
              <Button size="xl" variant="brand" asChild>
                <Link href="/triage/start">
                  Start a Triage Assessment
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button size="xl" variant="outline" asChild>
                <Link href="/auth/signup">
                  Create Organization Account
                </Link>
              </Button>
            </motion.div>

            {/* Medical disclaimer */}
            <motion.p
              variants={fadeUp}
              className="mt-8 text-xs text-muted-foreground/70"
            >
              ⚕️ This tool does not replace a licensed healthcare professional. Always seek
              professional medical care for health concerns. In emergencies, call 911.
            </motion.p>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.5 }}
            className="mx-auto mt-20 grid max-w-3xl grid-cols-2 gap-8 md:grid-cols-4"
          >
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="text-3xl font-bold tracking-tight text-foreground">{stat.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{stat.label}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Triage Level Visualization */}
      <section id="triage" className="border-y border-border bg-muted/30 py-20">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-12 text-center">
            <Badge className="mb-4" variant="secondary">5-Level Clinical Triage</Badge>
            <h2 className="text-3xl font-bold tracking-tight">Every Patient Gets the Right Care</h2>
            <p className="mt-3 text-muted-foreground">
              Clear urgency levels that route every patient to the right level of care
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            {TRIAGE_LEVELS.map((t, i) => (
              <motion.div
                key={t.level}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border border-border bg-card p-5 text-center"
              >
                <div
                  className={`mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full ${t.color} text-white`}
                >
                  <span className="text-sm font-bold">{t.level}</span>
                </div>
                <p className="mb-1 font-semibold">{t.label}</p>
                <p className="mb-2 text-xs font-medium text-muted-foreground">{t.action}</p>
                <p className="text-[11px] text-muted-foreground/70">{t.example}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-16 text-center">
            <Badge className="mb-4" variant="secondary">Platform Features</Badge>
            <h2 className="text-3xl font-bold tracking-tight">
              Built for Real Healthcare Deployments
            </h2>
            <p className="mt-3 max-w-2xl mx-auto text-muted-foreground">
              Neural Hub combines adaptive AI questioning, clinical risk detection, and
              enterprise-grade infrastructure in one platform.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="rounded-xl border border-border bg-card p-6"
              >
                <div
                  className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg ${feature.bg}`}
                >
                  <feature.icon className={`h-5 w-5 ${feature.color}`} />
                </div>
                <h3 className="mb-2 font-semibold">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="border-y border-border bg-muted/30 py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-16 text-center">
            <Badge className="mb-4" variant="secondary">Workflow</Badge>
            <h2 className="text-3xl font-bold tracking-tight">From Symptom to Care Pathway</h2>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[
              { step: "01", title: "Patient Enters Symptoms", desc: "Natural language input — no forms to fill out", icon: Users },
              { step: "02", title: "Adaptive Follow-Up", desc: "AI asks clinically relevant questions based on responses", icon: Brain },
              { step: "03", title: "Risk Assessment", desc: "Real-time detection of emergency patterns and risk scores", icon: Activity },
              { step: "04", title: "Triage Report", desc: "Structured clinical report with care pathway and urgency level", icon: FileTextIcon },
            ].map((item, i) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.12 }}
                className="relative rounded-xl border border-border bg-card p-6"
              >
                <span className="mb-4 block font-mono text-3xl font-bold text-border">
                  {item.step}
                </span>
                <item.icon className="mb-3 h-5 w-5 text-primary" />
                <h3 className="mb-2 font-semibold">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-brand-500/30 bg-gradient-to-b from-brand-500/10 to-brand-500/5 p-12"
          >
            <LogoMark className="mx-auto mb-4 h-12 w-12 rounded-2xl" />
            <h2 className="mb-4 text-3xl font-bold">Ready to Deploy Neural Hub?</h2>
            <p className="mb-8 text-muted-foreground">
              Set up your organization, configure your AI triage agent, and start
              improving patient care pathways today.
            </p>
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Button size="lg" variant="brand" asChild>
                <Link href="/auth/signup">
                  Create Organization Account
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/triage/start">Try Anonymous Triage</Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex flex-col items-center justify-between gap-4 text-sm text-muted-foreground md:flex-row">
            <div className="flex items-center gap-2">
              <LogoMark className="h-6 w-6 rounded-md" />
              <span className="font-semibold text-foreground">Neural Hub</span>
              <span>— AI Triage Nurse</span>
            </div>
            <p className="text-center text-xs">
              ⚕️ This platform does not provide medical diagnoses. Always consult a licensed
              healthcare professional. For emergencies, call 911.
            </p>
            <p>© 2025 Neural Hub. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Inline icon to avoid import conflict
function FileTextIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}
