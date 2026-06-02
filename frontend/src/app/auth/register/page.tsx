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

// Patient self-registration. No organization → the API assigns the PATIENT role.
const schema = z
  .object({
    first_name: z.string().min(1, "First name is required"),
    last_name: z.string().min(1, "Last name is required"),
    email: z.string().email("Please enter a valid email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof schema>;

export default function PatientRegisterPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormValues) => {
    try {
      const tokens = await authApi.register({
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
        // no organization_name → registers as a patient
      });
      setAuthToken(tokens.access_token);
      if (typeof window !== "undefined") {
        localStorage.setItem("refresh_token", tokens.refresh_token);
      }
      toast.success("Welcome to Neural Hub!");
      router.push("/triage/start");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to create account"));
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
        <div className="mb-8 text-center">
          <Logo className="mx-auto mb-5 h-auto w-[300px] max-w-[85vw] sm:w-[340px]" />
          <h1 className="text-2xl font-bold tracking-tight">Create your patient account</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track your symptoms, history, and triage assessments in one place
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-8 shadow-xl">
          <div className="mb-6">
            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link href="/auth/signin" className="text-primary hover:underline">
                Sign in
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-sm font-medium">First name</label>
                <Input placeholder="Your first name" {...register("first_name")} />
                {errors.first_name && (
                  <p className="mt-1 text-xs text-destructive">{errors.first_name.message}</p>
                )}
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">Last name</label>
                <Input placeholder="Your last name" {...register("last_name")} />
                {errors.last_name && (
                  <p className="mt-1 text-xs text-destructive">{errors.last_name.message}</p>
                )}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium">Email address</label>
              <Input type="email" placeholder="you@email.com" autoComplete="email" {...register("email")} />
              {errors.email && (
                <p className="mt-1 text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium">Password</label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="Min 8 characters"
                  autoComplete="new-password"
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

            <div>
              <label className="mb-1.5 block text-sm font-medium">Confirm password</label>
              <Input type="password" placeholder="••••••••" {...register("confirm_password")} />
              {errors.confirm_password && (
                <p className="mt-1 text-xs text-destructive">{errors.confirm_password.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" variant="brand" size="lg" loading={isSubmitting}>
              Create account
            </Button>
          </form>

          <div className="mt-6 rounded-lg border border-border bg-muted/50 p-3">
            <p className="text-center text-[11px] text-muted-foreground">
              Are you a clinic or health system?{" "}
              <Link href="/auth/signup" className="text-primary hover:underline">
                Create an organization account
              </Link>
            </p>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          This platform does not provide medical diagnoses. In an emergency, call 911.
        </p>
      </motion.div>
    </div>
  );
}
