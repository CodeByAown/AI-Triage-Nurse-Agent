"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  ArrowUp,
  CheckCircle,
  Loader2,
  Mic,
  RotateCcw,
  Square,
  Stethoscope,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { triageApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { TRIAGE_LEVEL_CONFIG, type TriageLevel } from "@/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TriageChatPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionToken = params.sessionToken as string;
  const assessmentId = searchParams.get("assessment");

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [requiresEscalation, setRequiresEscalation] = useState(false);
  const [triageLevel, setTriageLevel] = useState<TriageLevel | null>(null);
  const [turnCount, setTurnCount] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(false);

  // Voice-to-text: transcript is appended to the input so the patient can edit
  // it before sending through the normal chat flow.
  const handleTranscript = useCallback((text: string) => {
    setInput((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text));
    // Focus the textarea so the user can immediately edit the transcript.
    requestAnimationFrame(() => textareaRef.current?.focus());
  }, []);

  const voice = useVoiceRecorder({ onTranscript: handleTranscript });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Kick off the session with an empty message to get Maya's greeting.
  // Guard against React Strict Mode / re-mounts firing this twice (which
  // previously produced duplicate [SESSION_START] greetings).
  useEffect(() => {
    if (!sessionToken || startedRef.current) return;
    startedRef.current = true;
    startSession();
  }, [sessionToken]);

  const startSession = async () => {
    setIsLoading(true);
    try {
      const response = await triageApi.sendAnonymousMessage(sessionToken, "[SESSION_START]");
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.message,
          timestamp: new Date(),
        },
      ]);
      if (response.is_complete) handleCompletion(response);
    } catch {
      toast.error("Failed to start session");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCompletion = (response: { triage_level: TriageLevel | null; requires_escalation: boolean }) => {
    setIsComplete(true);
    setRequiresEscalation(response.requires_escalation);
    setTriageLevel(response.triage_level);
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading || isComplete) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setTurnCount((c) => c + 1);

    try {
      const response = await triageApi.sendAnonymousMessage(sessionToken, userMessage.content);

      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.message,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);

      if (response.triage_level) setTriageLevel(response.triage_level);

      if (response.is_complete) {
        handleCompletion(response);
      }

      if (response.requires_escalation) {
        setRequiresEscalation(true);
      }
    } catch (err) {
      toast.error("Failed to send message. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const viewReport = () => {
    if (assessmentId) {
      // Pass the session token so the (anonymous) viewer is authorized to read
      // their own report under the new capability-based access control.
      router.push(`/reports/${assessmentId}?token=${encodeURIComponent(sessionToken)}`);
    }
  };

  const progressPercent = Math.min((turnCount / 15) * 100, 90);
  const levelConfig = triageLevel ? TRIAGE_LEVEL_CONFIG[triageLevel] : null;

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <div
        className={cn(
          "border-b border-border bg-card px-6 py-3 transition-colors",
          requiresEscalation && "border-red-500/50 bg-red-500/5"
        )}
      >
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-full",
                requiresEscalation
                  ? "bg-red-500 animate-emergency-pulse"
                  : "bg-gradient-to-br from-brand-500 to-brand-700"
              )}
            >
              <Stethoscope className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold">Maya — AI Triage Nurse</p>
              <p className="text-xs text-muted-foreground">
                {isComplete ? "Assessment complete" : "Assessing your symptoms…"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {triageLevel && levelConfig && (
              <Badge
                className={cn(
                  "border font-medium",
                  levelConfig.bgColor,
                  levelConfig.color,
                  levelConfig.borderColor
                )}
              >
                {levelConfig.icon} {levelConfig.label}
              </Badge>
            )}
            {!isComplete && (
              <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    className="h-full rounded-full bg-primary"
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPercent}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
                <span>{Math.round(progressPercent)}%</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Emergency Banner */}
      <AnimatePresence>
        {requiresEscalation && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-b border-red-500/30 bg-red-500/10 emergency-card"
          >
            <div className="mx-auto flex max-w-2xl items-center gap-3 px-6 py-3">
              <AlertTriangle className="h-5 w-5 shrink-0 text-red-500" />
              <p className="text-sm font-semibold text-red-600 dark:text-red-400">
                🚨 EMERGENCY DETECTED — Call 911 immediately or go to your nearest emergency room.
                Do not wait.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-6 px-4 py-6">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className={cn(
                  "flex gap-3",
                  msg.role === "user" && "flex-row-reverse"
                )}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    "mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    msg.role === "assistant"
                      ? "bg-gradient-to-br from-brand-500 to-brand-700 text-white"
                      : "bg-secondary text-secondary-foreground"
                  )}
                >
                  {msg.role === "assistant" ? "M" : "You"}
                </div>

                {/* Bubble */}
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                    msg.role === "assistant"
                      ? "rounded-tl-sm bg-card border border-border shadow-sm"
                      : "rounded-tr-sm bg-primary text-primary-foreground"
                  )}
                >
                  <div className="chat-prose">
                    {msg.role === "assistant" ? (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    ) : (
                      <p>{msg.content}</p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700">
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-muted-foreground"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Completion card */}
          {isComplete && !isLoading && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-2xl border border-border bg-card p-6 text-center shadow-sm"
            >
              <CheckCircle className="mx-auto mb-3 h-10 w-10 text-primary" />
              <h3 className="mb-1 text-lg font-semibold">Assessment Complete</h3>
              {levelConfig && (
                <p className={cn("mb-3 text-sm font-medium", levelConfig.color)}>
                  {levelConfig.icon} {levelConfig.label} — {levelConfig.action}
                </p>
              )}
              <p className="mb-4 text-sm text-muted-foreground">
                Your triage report has been generated with a full clinical assessment and care recommendations.
              </p>
              {assessmentId && (
                <Button onClick={viewReport} variant="brand" size="lg">
                  View Full Triage Report
                </Button>
              )}
              <p className="mt-4 text-xs text-muted-foreground">
                ⚕️ This assessment does not replace professional medical advice. Always consult a licensed healthcare provider.
              </p>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      {!isComplete && (
        <div className="border-t border-border bg-card px-4 py-4">
          <div className="mx-auto max-w-2xl">
            {/* Recording / processing / error status strip */}
            <AnimatePresence>
              {(voice.status === "recording" ||
                voice.status === "processing" ||
                voice.status === "error") && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  className={cn(
                    "mb-2 flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-xs",
                    voice.status === "error"
                      ? "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400"
                      : "border-border bg-muted/60 text-muted-foreground"
                  )}
                >
                  {voice.status === "recording" && (
                    <>
                      <span className="flex items-center gap-2 font-medium">
                        <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
                        Recording… {formatElapsed(voice.elapsed)}
                      </span>
                      <button
                        type="button"
                        onClick={voice.cancel}
                        className="font-medium underline-offset-2 hover:underline"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                  {voice.status === "processing" && (
                    <span className="flex items-center gap-2 font-medium">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Transcribing your recording…
                    </span>
                  )}
                  {voice.status === "error" && (
                    <>
                      <span className="font-medium">{voice.error}</span>
                      <button
                        type="button"
                        onClick={voice.retry}
                        className="flex shrink-0 items-center gap-1 font-semibold underline-offset-2 hover:underline"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Retry
                      </button>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex items-end gap-2 sm:gap-3">
              {/* Microphone button */}
              <Button
                type="button"
                onClick={voice.status === "recording" ? voice.stop : voice.start}
                disabled={
                  isLoading ||
                  voice.status === "processing" ||
                  !voice.supported
                }
                size="icon"
                variant={voice.status === "recording" ? "destructive" : "outline"}
                className="h-[52px] w-[52px] shrink-0 rounded-xl"
                title={
                  !voice.supported
                    ? "Voice input isn't supported in this browser"
                    : voice.status === "recording"
                      ? "Stop recording"
                      : "Record a voice message"
                }
                aria-label={
                  voice.status === "recording" ? "Stop recording" : "Record a voice message"
                }
              >
                {voice.status === "processing" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : voice.status === "recording" ? (
                  <Square className="h-4 w-4 fill-current" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </Button>

              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your symptoms, or tap the mic to speak…"
                className="min-h-[52px] max-h-36 resize-none text-sm"
                disabled={isLoading}
                rows={2}
              />
              <Button
                onClick={sendMessage}
                disabled={!input.trim() || isLoading}
                size="icon"
                variant="brand"
                className="h-[52px] w-[52px] shrink-0 rounded-xl"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              Press Enter to send · Shift+Enter for new line · This is not a substitute for emergency care
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
