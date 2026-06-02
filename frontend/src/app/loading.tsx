import { LogoMark } from "@/components/ui/logo";

// Shown automatically by Next.js during route-segment loading / data fetching,
// so users see a calm branded state instead of a blank screen.
export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="relative flex h-14 w-14 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-2xl bg-brand-500/20" />
        <LogoMark className="relative h-12 w-12 rounded-2xl" />
      </div>
      <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
    </div>
  );
}
