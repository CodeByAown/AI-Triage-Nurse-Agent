"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { authApi, loadStoredToken } from "@/lib/api";
import type { User } from "@/types";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    loadStoredToken();
    authApi.me().then(setUser).catch(() => {
      router.push("/auth/signin");
    });
  }, [router]);

  const handleSignOut = () => {
    router.push("/auth/signin");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar user={user} onSignOut={handleSignOut} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
