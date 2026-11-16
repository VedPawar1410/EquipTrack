"use client";

import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { hasRole, useMe, type Role } from "@/lib/auth";

/**
 * Hides a page from roles that can't use it. This is a courtesy for the UI only: the API checks the
 * role on every request, so bypassing this component still gets a 403 for every call.
 */
export function RequireRole({ minimum, children }: { minimum: Role; children: React.ReactNode }) {
  const { data: me, isPending } = useMe();
  if (isPending) return <Skeleton className="h-40 w-full" />;
  if (!hasRole(me?.role, minimum)) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-xl border bg-card p-8 text-center shadow-sm">
        <ShieldAlert className="mx-auto size-10 text-muted-foreground" />
        <h2 className="mt-4 text-lg font-semibold">You don&apos;t have access to this page</h2>
        <p className="mt-1 text-sm text-muted-foreground">It needs the {minimum} role. Ask an administrator if you need it.</p>
        <Button asChild variant="outline" className="mt-6">
          <Link href="/">Back to dashboard</Link>
        </Button>
      </div>
    );
  }
  return <>{children}</>;
}
