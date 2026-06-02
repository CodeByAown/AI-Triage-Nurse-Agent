import Image from "next/image";
import { cn } from "@/lib/utils";

// The full Neural Hub wordmark. Intrinsic 4500×273 (~16.48:1), transparent PNG
// with dark-green letterforms — only render it on light surfaces.
//
// Sizing rules:
//  • Callers control DISPLAY size via the className height (e.g. `h-7`); width
//    follows automatically and `object-contain` guarantees it is never stretched.
//  • `sizes` is capped so the image optimizer never ships the 3840px variant for
//    a small wordmark (a real performance fix).
export function Logo({
  className,
  priority = true,
}: {
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      src="/neuralhub-wordmark.png"
      alt="Neural Hub — AI Triage Nurse"
      width={4442}
      height={257}
      priority={priority}
      sizes="(max-width: 640px) 280px, (max-width: 1024px) 360px, 460px"
      className={cn("h-7 w-auto object-contain select-none", className)}
    />
  );
}

// Compact square brand mark for tight spots (sidebar, mobile nav, avatars,
// error/loading/404). Echoes the logo: forest-green tile with the signature
// terracotta dot. Self-contained — safe on any background.
export function LogoMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-700 to-brand-900 shadow-sm",
        className
      )}
      aria-hidden
    >
      <span className="text-[13px] font-bold leading-none text-sage-200">N</span>
      <span className="absolute bottom-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-terracotta-500" />
    </div>
  );
}
