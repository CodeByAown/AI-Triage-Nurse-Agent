"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Eye, EyeOff } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi, getErrorMessage, setAuthToken } from "@/lib/api";
import { Logo } from "@/components/ui/logo";

const schema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export default function SignInPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormValues) => {
    try {
      const tokens = await authApi.login(data.email, data.password);
      setAuthToken(tokens.access_token);
      if (typeof window !== "undefined") {
        localStorage.setItem("refresh_token", tokens.refresh_token);
      }
      toast.success("Welcome back!");
      // Route by role: patients go to their own dashboard (where Maya remembers
      // them); clinic staff/admins to the operational dashboard.
      const me = await authApi.me().catch(() => null);
      router.push(me?.role === "patient" ? "/patient" : "/dashboard");
    } catch (err) {
      toast.error(getErrorMessage(err, "Invalid email or password"));
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="absolute inset-0 bg-grid-pattern opacity-60" />
      <div className="absolute inset-0 bg-gradient-to-b from-sage-100/60 via-background/30 to-background" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-md"
      >
        {/* Logo */}
        <div className="mb-8 text-center">
          <Logo className="mx-auto h-auto w-[300px] max-w-[85vw] sm:w-[360px]" />
          <p className="mt-3 text-sm text-muted-foreground">AI Triage Nurse Platform</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border bg-card p-8 shadow-xl">
          <div className="mb-6">
            <h2 className="text-xl font-semibold">Sign in to your account</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link href="/auth/signup" className="text-primary hover:underline">
                Create one
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Email address</label>
              <Input
                type="email"
                placeholder="you@clinic.com"
                autoComplete="email"
                {...register("email")}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium">Password</label>
              </div>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-destructive">{errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full"
              variant="brand"
              size="lg"
              loading={isSubmitting}
            >
              Sign in
            </Button>
          </form>

          <div className="mt-6 rounded-lg border border-border bg-muted/50 p-3">
            <p className="text-center text-[11px] text-muted-foreground">
              ⚕️ For authorized healthcare professionals only. All access is logged and audited.
            </p>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          This platform does not provide medical diagnoses.{" "}
          <Link href="/" className="hover:underline">
            Learn more
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
