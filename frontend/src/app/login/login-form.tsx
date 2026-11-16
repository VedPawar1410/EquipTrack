"use client";

import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DEMO_ACCOUNTS } from "@/lib/demo";
import { cn } from "@/lib/utils";

type ServerState = "waking" | "ready" | "down";

const SERVER_STATUS: Record<ServerState, { dot: string; text: string }> = {
  waking: { dot: "bg-warning animate-pulse", text: "Waking the server. The first sign-in after a quiet spell can take ~30 s." },
  ready: { dot: "bg-success", text: "Server ready" },
  down: { dot: "bg-danger", text: "Server unreachable right now. You can still try to sign in." },
};

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [server, setServer] = useState<ServerState>("waking");
  const username = useRef<HTMLInputElement>(null);
  const password = useRef<HTMLInputElement>(null);

  // The API scales to zero when idle. Start waking it the moment this page opens,
  // so the boot overlaps with the visitor typing instead of following "Sign in".
  useEffect(() => {
    let cancelled = false;
    fetch("/api/warmup", { method: "POST" })
      .then((r) => r.json())
      .then((body: { ready: boolean }) => !cancelled && setServer(body.ready ? "ready" : "down"))
      .catch(() => !cancelled && setServer("down"));
    return () => {
      cancelled = true;
    };
  }, []);

  function fill(account: (typeof DEMO_ACCOUNTS)[number]) {
    if (username.current && password.current) {
      username.current.value = account.username;
      password.current.value = account.password;
    }
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
    }).catch(() => null);
    if (response?.ok) {
      const next = params.get("next");
      // Only same-site paths: never redirect to another origin from a query parameter.
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
      router.refresh();
      return;
    }
    const body = await response?.json().catch(() => null);
    setError(body?.detail ?? "Could not reach EquipTrack. Try again.");
    setPending(false);
  }

  const status = SERVER_STATUS[server];
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="username">Username or email</Label>
        <Input id="username" name="username" ref={username} autoComplete="username" required autoFocus />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input id="password" name="password" ref={password} type="password" autoComplete="current-password" required />
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <Loader2 className="size-4 animate-spin" />}
        {pending && server === "waking" ? "Signing in (server is starting)…" : "Sign in"}
      </Button>
      <p role="status" className="flex items-start gap-2 text-xs text-muted-foreground">
        <span aria-hidden className={cn("mt-1 size-2 shrink-0 rounded-full", status.dot)} />
        {status.text}
      </p>

      <div className="rounded-lg border border-dashed p-3">
        <p className="text-xs font-medium">Try the demo (sample data only)</p>
        <div className="mt-2 grid gap-2">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.username}
              type="button"
              onClick={() => fill(account)}
              className="flex items-center justify-between rounded-md bg-muted px-3 py-2 text-left text-xs transition-colors hover:bg-accent"
            >
              <span className="font-medium">{account.role}</span>
              <span className="font-mono text-muted-foreground">
                {account.username} / {account.password}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Click one to fill the form.</p>
      </div>
    </form>
  );
}
