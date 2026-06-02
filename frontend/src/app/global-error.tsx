"use client";

// Last-resort error boundary. `error.tsx` cannot catch errors thrown in the
// root layout itself; `global-error.tsx` replaces the entire document when
// that happens, so the user still sees a styled page rather than a white
// screen with a stack trace. It must render its own <html>/<body>.

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("Fatal application error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#fcfbf7",
          color: "#22332b",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          padding: "1rem",
        }}
      >
        <div style={{ maxWidth: "28rem", textAlign: "center" }}>
          <div
            style={{
              margin: "0 auto 1.5rem",
              height: "4rem",
              width: "4rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "1rem",
              background: "linear-gradient(135deg, #2f4838, #27392f)",
              position: "relative",
            }}
          >
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#fff"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
              <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
              <circle cx="20" cy="10" r="2" />
            </svg>
            <span
              style={{
                position: "absolute",
                bottom: "0.5rem",
                right: "0.5rem",
                height: "0.4rem",
                width: "0.4rem",
                borderRadius: "9999px",
                backgroundColor: "#c16a4f",
              }}
            />
          </div>

          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0 0 0.75rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#94a3b8", margin: "0 0 2rem", lineHeight: 1.6 }}>
            The application ran into an unexpected problem. Please try again. If
            this continues, please contact your administrator.
          </p>

          <button
            onClick={() => reset()}
            style={{
              cursor: "pointer",
              border: "none",
              borderRadius: "0.5rem",
              padding: "0.625rem 1.5rem",
              fontSize: "0.875rem",
              fontWeight: 600,
              color: "#fff",
              background: "linear-gradient(90deg, #2f4838, #3b5a44)",
            }}
          >
            Try again
          </button>

          {error?.digest && (
            <p
              style={{
                marginTop: "1.5rem",
                fontSize: "0.6875rem",
                color: "rgba(148,163,184,0.5)",
                fontFamily: "ui-monospace, monospace",
              }}
            >
              Reference: {error.digest}
            </p>
          )}
        </div>
      </body>
    </html>
  );
}
