import type { Metadata } from "next";
import { Suspense } from "react";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      {/* Soft indigo glow behind the card */}
      <div aria-hidden className="login-glow pointer-events-none absolute inset-0" />
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="relative w-full max-w-sm">
        <Logo className="mb-8 justify-center" />
        <div className="rounded-2xl border bg-card p-8 shadow-xl shadow-slate-900/5">
          <h1 className="text-xl font-semibold tracking-tight">Sign in to your plant</h1>
          <p className="mt-1 mb-6 text-sm text-muted-foreground">Use your EquipTrack username or email.</p>
          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
        <p className="mt-6 text-center text-xs text-muted-foreground">Accounts are created by your administrator.</p>
      </div>
    </div>
  );
}
