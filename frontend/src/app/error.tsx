"use client";

// Route-level error boundary. Catches any uncaught error thrown while rendering
// a page (or in its data fetching) and shows a calm, professional fallback
// instead of the raw Next.js error overlay / stack trace.

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/ui/logo";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to logging/monitoring without ever showing internals to the user.
    // eslint-disable-next-line no-console
    console.error("Unhandled UI error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="w-full max-w-md text-center">
        <LogoMark className="mx-auto mb-6 h-16 w-16 rounded-2xl" />

        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-5 w-5 text-red-500" />
        </div>

        <h1 className="mb-3 text-2xl font-bold">Something went wrong</h1>
        <p className="mb-8 text-muted-foreground">
          We hit an unexpected problem while loading this page. This has been
          logged for our team. You can try again, and if it keeps happening
          please head back to a safe page.
        </p>

        <div className="flex items-center justify-center gap-3">
          <Button variant="brand" onClick={() => reset()}>
            <RefreshCw className="h-4 w-4" />
            Try again
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard">Go to dashboard</Link>
          </Button>
        </div>

        {error?.digest && (
          <p className="mt-6 font-mono text-[11px] text-muted-foreground/50">
            Reference: {error.digest}
          </p>
        )}
      </div>
    </div>
  );
}
