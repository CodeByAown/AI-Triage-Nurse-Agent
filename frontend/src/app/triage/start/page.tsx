"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, ArrowRight, Stethoscope } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { triageApi } from "@/lib/api";

export default function TriageStartPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const startAnonymous = async () => {
    setLoading(true);
    try {
      const { session_token, assessment_id } = await triageApi.startAnonymousSession();
      router.push(`/triage/${session_token}?assessment=${assessment_id}`);
    } catch {
      toast.error("Failed to start session. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="absolute inset-0 bg-grid-pattern opacity-40" />
      <div className="absolute inset-0 bg-gradient-to-b from-brand-950/70 via-background/50 to-background" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-lg"
      >
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-xl shadow-brand-500/40">
            <Stethoscope className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">AI Triage Assessment</h1>
          <p className="mt-2 text-muted-foreground">
            Describe your symptoms and Maya, our AI nurse, will assess your urgency level
            and recommend the right care.
          </p>
        </div>

        {/* Info Card */}
        <div className="mb-6 rounded-2xl border border-border bg-card p-6">
          <h2 className="mb-4 font-semibold">What to expect</h2>
          <div className="space-y-3">
            {[
              { icon: "💬", text: "A conversational assessment (typically 5–10 minutes)" },
              { icon: "🔍", text: "Adaptive questions based on your specific symptoms" },
              { icon: "⚡", text: "Immediate escalation if emergency symptoms are detected" },
              { icon: "📋", text: "A structured triage report with care recommendations" },
            ].map((item) => (
              <div key={item.text} className="flex items-start gap-3">
                <span className="mt-0.5 text-base">{item.icon}</span>
                <p className="text-sm text-muted-foreground">{item.text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Emergency callout */}
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <div className="flex items-start gap-3">
            <Activity className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
            <div>
              <p className="font-semibold text-red-600 dark:text-red-400">
                If you believe this is a life-threatening emergency:
              </p>
              <p className="mt-1 text-sm text-red-600/80 dark:text-red-400/80">
                <strong>Call 911 immediately.</strong> Do not wait for this assessment.
                This tool is for non-emergency triage.
              </p>
            </div>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="mb-6 rounded-lg border border-border bg-muted/50 p-4">
          <p className="text-center text-xs text-muted-foreground">
            ⚕️ <strong>Medical Disclaimer:</strong> This AI triage tool does not provide medical
            diagnoses and does not replace a licensed healthcare professional. All
            recommendations are informational only.
          </p>
        </div>

        <Button
          onClick={startAnonymous}
          loading={loading}
          size="xl"
          variant="brand"
          className="w-full"
        >
          Begin Assessment with Maya
          <ArrowRight className="h-5 w-5" />
        </Button>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          No account required · Your conversation is private · End anytime
        </p>
      </motion.div>
    </div>
  );
}
