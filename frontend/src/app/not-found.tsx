import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Stethoscope } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-lg">
          <Stethoscope className="h-8 w-8 text-white" />
        </div>
        <p className="mb-2 font-mono text-6xl font-bold tracking-tight text-muted-foreground/30">
          404
        </p>
        <h1 className="mb-3 text-2xl font-bold">Page not found</h1>
        <p className="mb-8 text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button variant="brand" asChild>
            <Link href="/">Go home</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard">Dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
