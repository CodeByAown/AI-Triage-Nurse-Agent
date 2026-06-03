"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { voiceApi, getErrorMessage } from "@/lib/api";

export type RecorderStatus = "idle" | "recording" | "processing" | "error";

interface UseVoiceRecorderOptions {
  /** Called with the transcribed text once a recording is successfully processed. */
  onTranscript: (text: string) => void;
  /** Auto-stop after this many seconds to avoid oversized uploads. */
  maxDurationSec?: number;
}

// MediaRecorder mime types we try, in order of preference. The first the browser
// supports wins. Whisper accepts all of these container/codec combinations.
const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4", // iOS / Safari
  "audio/ogg;codecs=opus",
  "audio/ogg",
];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  for (const type of PREFERRED_MIME_TYPES) {
    try {
      if (MediaRecorder.isTypeSupported(type)) return type;
    } catch {
      // isTypeSupported can throw on some engines — ignore and continue.
    }
  }
  return undefined; // let the browser choose its default
}

function extensionFor(mime: string | undefined): string {
  if (!mime) return "webm";
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

export function useVoiceRecorder({ onTranscript, maxDurationSec = 120 }: UseVoiceRecorderOptions) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeRef = useRef<string | undefined>(undefined);
  const lastBlobRef = useRef<Blob | null>(null); // kept so the user can retry
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const supported =
    typeof window !== "undefined" &&
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoStopRef.current) clearTimeout(autoStopRef.current);
    timerRef.current = null;
    autoStopRef.current = null;
  }, []);

  const transcribe = useCallback(
    async (blob: Blob) => {
      setStatus("processing");
      setError(null);
      try {
        const filename = `recording.${extensionFor(mimeRef.current)}`;
        const text = await voiceApi.transcribe(blob, filename);
        const cleaned = text.trim();
        if (!cleaned) {
          setError("No speech detected. Please try again.");
          setStatus("error");
          return;
        }
        onTranscript(cleaned);
        setStatus("idle");
      } catch (err) {
        setError(getErrorMessage(err, "We couldn't transcribe that audio. Please try again."));
        setStatus("error");
      }
    },
    [onTranscript]
  );

  const start = useCallback(async () => {
    if (!supported) {
      setError("Voice input isn't supported in this browser. Please type your message.");
      setStatus("error");
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      mimeRef.current = mimeType;
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        cleanupStream();
        const blob = new Blob(chunksRef.current, { type: mimeRef.current || "audio/webm" });
        lastBlobRef.current = blob;
        if (blob.size === 0) {
          setError("We didn't capture any audio. Please try again.");
          setStatus("error");
          return;
        }
        void transcribe(blob);
      };

      recorder.start();
      setStatus("recording");
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
      autoStopRef.current = setTimeout(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      }, maxDurationSec * 1000);
    } catch (err) {
      cleanupStream();
      const e = err as DOMException;
      if (e?.name === "NotAllowedError" || e?.name === "SecurityError") {
        setError("Microphone access was blocked. Enable it in your browser settings and try again.");
      } else if (e?.name === "NotFoundError") {
        setError("No microphone was found. Please connect one and try again.");
      } else {
        setError("We couldn't access your microphone. Please try again.");
      }
      setStatus("error");
    }
  }, [supported, maxDurationSec, transcribe, cleanupStream]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop(); // fires onstop → transcribe
    }
  }, []);

  const cancel = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    cleanupStream();
    chunksRef.current = [];
    setStatus("idle");
    setError(null);
  }, [cleanupStream]);

  const retry = useCallback(() => {
    if (lastBlobRef.current && lastBlobRef.current.size > 0) {
      void transcribe(lastBlobRef.current);
    } else {
      void start();
    }
  }, [transcribe, start]);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  // Clean up on unmount so a dangling stream never keeps the mic active.
  useEffect(() => cleanupStream, [cleanupStream]);

  return { status, error, elapsed, supported, start, stop, cancel, retry, reset };
}
